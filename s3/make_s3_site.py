import datetime
import json
import mimetypes
import os
import posixpath
import pprint
import tempfile
from collections import deque
from enum import Enum

import boto3
from bs4 import BeautifulSoup

# todo:
#   - add logging
#   - clarify config variables or make them external
#   - at least an option to WIPE the remote site before uploading (to avoid dead links)
#   - replace local_swap_folder with a tempfile.TemporaryDirectory()
#   - actually convert Windows paths, if needed

# CONFIG VARIABLES:
s3_bucket = "foxsi-public"  # the bucket name on S3
s3_site_path = "site"  # path in the bucket to upload HTML to. WILL OVERWRITE!
s3_data_folder = "data"  # a folder in the bucket to search for data
# the path on your local system to store the website on before it is uploaded:
local_swap_folder = os.path.abspath(
    os.path.join(
        "s3",
        "_site",
        s3_site_path,
    )
)  # in the future, I will use tempfiles for this.
dry_run = (
    True  # if True, just print what will be written without actually doing it to S3
)


s3_endpoint = "https://s3.msi.umn.edu"  # host domain for the bucket
do_s3 = not dry_run

mimetypes.init()


class S3File:
    def __init__(self, path, modtime, size, etag):
        self.path = path
        self.modtime = modtime
        self.size = size
        self.etag = etag


class BFSItem:
    def __init__(self, structure: dict, path: str):
        self.structure = structure
        self.path = path


def displaysize(item: S3File):
    if item.size < 0:
        return f"{item.size}"
    if 0 <= item.size and item.size < 1e3:
        return f"{item.size} B"
    if 1e3 <= item.size and item.size < 1e6:
        return f"{int(round(item.size / 1e3))} kB"
    if 1e6 <= item.size and item.size < 1e9:
        return f"{int(round(item.size / 1e6))} MB"
    if 1e9 <= item.size and item.size < 1e12:
        return f"{int(round(item.size / 1e9))} GB"
    if 1e12 <= item.size:
        return f"{int(round(item.size / 1e12))} TB"


def displaydate(item: S3File):
    return item.modtime.strftime("%d%b%Y %H:%M") + " UTC"


class HTMLPage:
    def __init__(
        self,
        relpath: str,
        local_root: str = local_swap_folder,
        s3_root: str = posixpath.join(s3_endpoint, s3_bucket),
    ):
        self.relpath = relpath
        self.local_root = local_root
        self.s3_root = s3_root
        self.contents = []

    def add(self, item: S3File | str):
        # add the item to self.contents
        # should probably do some checks that the paths line up
        self.contents.append(item)

    def tablehead(self):
        # internally use markdown. Will convert at the end.
        return """<table><thead><tr>
            <th class="tname" scope="col">Name</th>
            <th class="tmod" scope="col">Modified</th>
            <th class="tsize" scope="col">Size</th>
        </tr></thead><tbody>
        """

    def tablefoot(self):
        return "</tbody></table>"

    def table(self):
        table = ""
        table += self.tablehead()
        for item in self.contents:
            if type(item) is str:
                # a folder
                basename = os.path.basename(item)
                table += f"""<tr>
                    <td><a href="{os.path.join(basename, "index.html")}">{basename}/</a></td>
                    <td></td>
                    <td></td>
                    </tr>
                """
            else:
                table += f"""<tr>
                    <td><a href="{posixpath.join(self.s3_root, item.path)}">{posixpath.basename(item.path)}</a></td>
                    <td>{displaydate(item)}</td>
                    <td>{displaysize(item)}</td>
                    </tr>
                """
        table += self.tablefoot()
        return table

    def page(self):
        printpath = self.relpath if self.relpath != "" else "FOXSI public data"
        # if building for local display, replace the CSS path:
        #   href="{posixpath.join{self.local_root, "styles.css}}" with
        #   href="{posixpath.join{self.s3_root, s3_site_path, "styles.css}}"
        stylesheet = f"""<link rel="stylesheet" href="{posixpath.join(self.s3_root, s3_site_path, "styles.css")}">"""
        # stylesheet = ""
        page = f"""<!DOCTYPE html>
                <html lang="en" xml:lang="en">
                    <head>
                        <title>Index of {printpath}</title>
                        {stylesheet}
                    </head>
                    <body>
                        <h1>Index of {printpath}</h1>
                        <div><a href="../index.html">parent</a></div>
                        <p></p>
                        <div>
                """
        page += self.table()
        page += "</div></body></html>"

        soup = BeautifulSoup(page, features="html.parser")
        return soup.prettify()

    def write(self):
        # write self.mkpage() to os.join(local_root, relpath, index.html)
        wpath = os.path.join(self.local_root, self.relpath)
        if not os.path.exists(wpath):
            os.makedirs(wpath)
        with open(os.path.join(wpath, "index.html"), "w") as f:
            f.write(self.page())
            print("wrote page to", wpath)


# The FolderItems enum contains flags used when building a dictionary of the filestructure.
class FolderItems(Enum):
    FILES = 1
    VISITED = 2


def pathologize_file(file: S3File):
    """Return the folders along the path, with file at the end"""
    parts = file.path.split("/")
    return parts[0:-1], file


def gen_structure(files: list[S3File]) -> dict:
    """Return the dictionary with the structure described in the file list"""
    root = {}
    for file in files:
        path, file = pathologize_file(file)
        thisfolder = root
        for key in path:
            thisfolder = thisfolder.setdefault(key, {})
        if FolderItems.FILES not in thisfolder.keys():
            thisfolder[FolderItems.FILES] = [file]
        else:
            thisfolder[FolderItems.FILES].append(file)
    return root


def html_tree(structure: dict):
    queue = deque([BFSItem(structure, "")])
    nlayer = 0
    while len(queue) > 0:  # visit the whole tree
        # next layer of folders to visit (to avoid modifying list while looping over it)
        next_layer_down = []
        for item in queue:
            folder = item.structure
            path = item.path
            # make a new HTML page
            this_page = HTMLPage(
                path, local_swap_folder, posixpath.join(s3_endpoint, s3_bucket)
            )
            # this_page = table_page(path)
            for key in folder.keys():
                if type(key) is str:  # i.e. a folder[key] is another folder
                    # put a row in this table for the folder, linking
                    # put this folder in the queue
                    next_layer_down.append(
                        BFSItem(folder[key], posixpath.join(path, key))
                    )

                    this_page.add(posixpath.join(path, key))

                elif type(key) is FolderItems:
                    if key == FolderItems.FILES:  # i.e. a file list
                        for file in folder[key]:
                            # put this file into the table
                            this_page.add(file)

            this_page.write()

        queue.clear()  # just looped over the whole queue, so it should be done
        queue.extend(next_layer_down)  # put any new folders into the queue
        nlayer += 1


def upload_folder(
    client, local_path=local_swap_folder, bucket=s3_bucket, site_path=s3_site_path
):
    for root, dirs, files in os.walk(local_path):
        pathsuffix = os.path.relpath(root, local_path)
        destpath = posixpath.normpath(posixpath.join(site_path, pathsuffix))
        for file in files:
            source_path = os.path.join(root, file)
            print(
                f"uploading {source_path} to {posixpath.join(s3_endpoint, bucket, destpath, file)}"
            )
            mime, enc = mimetypes.guess_type(source_path)
            if mime is None:
                raise ValueError(f"MIME type cannot be found for {source_path}")
            do_s3 and client.upload_file(
                source_path,
                bucket,
                posixpath.join(destpath, file),
                ExtraArgs={"ContentType": mime},
            )
        # NOTE: for this to work, need to set boto3 configurations:
        # request_checksum_calculation = when_required
        # response_checksum_validation = when_required
        # with environmental vars or with config file. See configuration guide
        # here: https://docs.aws.amazon.com/boto3/latest/guide/configuration.html
        #
        # See boto3 issue #4398 on Github.


if __name__ == "__main__":
    """A script to emit a static HTML directory listing based on the index of an S3 bucket.

    THIS SCRIPT WILL MODIFY YOUR BUCKET!

    The steps that run:
        1. List the S3 bucket contents. NOTE: you need a credentials file: $HOME/.aws/credentials which includes your access key and secrets key for this to work. You can also set environmental variables for these. See the [boto3 documentation](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html#guide-credentials) for more information.
        2. Turn the linear file list into a dictionary.
        3. Walk the dictionary (BFS) and generate HTML for each folder.

    """

    client = boto3.client("s3", endpoint_url=s3_endpoint)
    response = client.list_buckets()
    print("found your buckets: ")
    for bucket in response["Buckets"]:
        print(f"  {bucket['Name']}")

    paginator = client.get_paginator("list_objects_v2")

    flist = []
    fnames = []
    for page in paginator.paginate(Bucket=s3_bucket):
        for obj in page.get("Contents", []):
            if obj["Key"].split("/", maxsplit=1)[0] == s3_data_folder:
                this_file = S3File(
                    obj["Key"], obj["LastModified"], obj["Size"], obj["ETag"]
                )
                flist.append(this_file)
                # print(f"{this_file.path:-<32}")
                # print(
                #     "> modtime: ",
                #     obj["LastModified"],
                #     "\n> etag: ",
                #     obj["ETag"],
                #     "\n> size: ",
                #     obj["Size"],
                #     "\n> storageclass> ",
                #     obj["StorageClass"],
                # )
                fnames.append(this_file.path)
            else:
                # print(obj["Key"])
                pass

    # reconstruct the file structure from the linear file list
    print("\nreconsructing folder structure...")
    file_tree = gen_structure(flist)
    # pprint.pprint(file_tree)

    # breadth-first walk the file structure, and emit an HTML page at each layer
    print("\ncreating HTML...")
    html_tree(file_tree)

    # put new HTML in the bucket
    print("\nlocal site root:", local_swap_folder)
    site_dest = posixpath.join(s3_endpoint, s3_bucket, s3_site_path)
    print("\nthe site will be uploaded to", site_dest)
    upload_folder(client)

    print("\ncurrent ACL:")
    result = client.get_bucket_acl(Bucket=s3_bucket)
    print(result)

    print("\nupdating bucket policy...")
    # set bucket permissions
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AddPerm",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": [
                    f"arn:aws:s3:::{s3_bucket}/{s3_site_path}/*",
                    f"arn:aws:s3:::{s3_bucket}/{s3_data_folder}/*",
                ],
            }
        ],
    }
    bucket_policy = json.dumps(bucket_policy)
    print(bucket_policy)
    # # Set the new policy
    do_s3 and client.put_bucket_policy(Bucket=s3_bucket, Policy=bucket_policy)

    # configure the bucket
    # see: https://docs.aws.amazon.com/boto3/latest/guide/s3-example-static-web-host.html
    # website_configuration = {
    #     "ErrorDocument": {"Key": "error.html"},
    #     "IndexDocument": {"Suffix": posixpath.join(s3_site_path, "index.html")},
    # }
    # Set the website configuration
    # client.put_bucket_website(
    #     Bucket=s3_bucket, WebsiteConfiguration=website_configuration
    # )
    #
    # ^ this fails!
