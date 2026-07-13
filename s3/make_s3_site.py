"""Upload a static HTML file listing for an S3 bucket."""

import json
import tomllib
import mimetypes
import os
import posixpath
import tqdm
import inquirer
import pprint
import tempfile
from collections import deque
from enum import Enum

import boto3
from botocore.exceptions import ClientError
from bs4 import BeautifulSoup

# todo:
#   - add logging
#   - clarify config variables or make them external
#   - at least an option to WIPE the remote site before uploading (to avoid dead links)
#   - replace local_swap_folder with a tempfile.TemporaryDirectory()
#   - actually convert Windows paths, if needed


class S3SiteConfig:
    def __init__(
        self,
        config=None,
        endpoint="https://s3.msi.umn.edu",
        bucket="foxsi-public",
        datapath="data",
        sitepath="site",
        localpath=tempfile.TemporaryDirectory(),
        dryrun=False,
        interactive=True
    ):
        print()
        # if provided, favor the config file passed in
        if config and os.path.exists(config):
            print(f"loading config from {config}...")
            self.load(config)
        # otherwise see if there's a config.toml in this dir:
        elif os.path.exists("config.toml"):
            print("loading config from config.toml...")
            self.load("config.toml")
        # otherwise use the defaults:
        else:
            print("loading config defaults...")
            self.endpoint = endpoint
            self.bucket = bucket
            self.datapath = datapath
            self.sitepath = sitepath
            self.localpath = localpath
            self.do_s3_write = not dryrun
            self.interactive = interactive

        # tempfile.TemporaryDirectory doesn't behave like a
        # usual path when manipulating path strings, so this
        # pulls the string name out of it so I can work with that.
        if isinstance(self.localpath, tempfile.TemporaryDirectory):
            self.localpath = self.localpath.name

    def load(self, file):
        with open(file, "rb") as f:
            d = tomllib.load(f)
            self.endpoint = d["s3"]["endpoint"]
            self.bucket = d["s3"]["bucket"]
            self.datapath = d["s3"]["datapath"]
            self.sitepath = d["s3"]["sitepath"]
            self.do_s3_write = not d["s3"]["dryrun"]
            if not d["local"]["path"]:
                self.localpath = tempfile.TemporaryDirectory()
            else:
                loc = os.path.abspath(d["local"]["path"])
                if not os.path.exists(loc):
                    os.makedirs(loc)
                self.localpath = loc
            self.interactive = d["local"]["interactive"]

    def __str__(self):
        out = "S3SiteConfig:"
        for attribute, value in vars(self).items():
            out += f"\n  .{attribute}: {value}"
        return out

    def validate(self):
        print("\nchecking S3:")
        # def validate self as often as self can.
        # self doing great job and self not give self enough credit.
        # self is not imposter.

        # def validate_config(bucket, site_path, data_folder, local_folder, endpoint=s3_endpoint):
        print("   checking S3 configuration...", end="", flush=True)
        if (
            os.path.exists(os.path.join(os.path.expanduser("~"), ".aws", "credentials"))
            or os.path.exists(os.path.join(os.path.expanduser("~"), ".aws", "config"))
            or (
                "AWS_ACCESS_KEY_ID" in os.environ
                and "AWS_SECRET_ACCESS_KEY" in os.environ
            )
        ):
            printc("done", color="green")
        else:
            printc(
                "couldn't find any source for AWS secret key or access key! See boto3 documentation for adding a config file, credentials file, or using environmental variables.",
                color="red",
            )

        # if local folder doesn't exist or is empty, good.
        print("   checking local HTML folder...", end="", flush=True)
        # print(os.listdir(self.localpath))
        # print(self.islocaltemp())
        if (
            (self.islocaltemp())
            or (not os.path.exists(self.localpath))
            or (not os.listdir(self.localpath))
        ):
            printc("done", color="green")
        else:
            printc(
                f"the local HTML folder {self.localpath} already contains data! It will be overwritten.",
                color="yellow",
            )

        print("   checking S3 communication...", end="", flush=True)
        client = boto3.client("s3", endpoint_url=self.endpoint)
        try:
            result = client.get_bucket_acl(Bucket=self.bucket)
        except Exception as e:
            printc(
                "got exception while checking bucket permissions:", color="red", end=""
            )
            print(e, ".", end="")
            printc(
                "check credentials, boto3 configuration, and S3 endpoint address.",
                color="red",
            )
            return
        printc("done", color="green")

        print("   checking S3 site folder...", end="", flush=True)
        if exists(client, self.bucket, self.sitepath):
            printc(
                f"S3 site folder '{self.sitepath}' already contains data! (Full S3 URL queried: {posixpath.join(self.endpoint, self.bucket, self.sitepath)}). It will be overwritten.",
                color="yellow",
            )
        else:
            printc("done", color="green")

        print("   checking S3 data folder...", end="", flush=True)
        if exists(client, self.bucket, self.datapath):
            printc("done", color="green")
        else:
            printc(
                f"couldn't find S3 data folder '{self.datapath}' in bucket '{self.bucket}' (full S3 URL queried: {posixpath.join(self.endpoint, self.bucket, self.datapath)}).",
                color="red",
            )

    def display(self):
        print("current S3 configuration:")
        print("   S3 endpoint:", end="")
        printc(self.endpoint, color="green")
        print("   S3 bucket name:", end="")
        printc(self.bucket, color="green")
        print("   data folder path in bucket:", end="")
        printc(self.datapath, color="green")
        print("   local folder for HTML:", end="")
        printc(self.localpath, color="green")
        print("   dry run (no S3 modification):", end="")
        printc(not self.do_s3_write, color="green")

    def islocaltemp(self):
        if os.path.dirname(self.localpath) == os.path.dirname(tempfile.gettempdir()):
            return True
        return False

    def dialog(self):
        while True:
            config.display()
            print()
            q = [
                inquirer.List(
                    "do_checks",
                    message="would you like to run checks on the configuration?",
                    choices=["yes", "no"],
                )
            ]
            ans = inquirer.prompt(q)
            if ans["do_checks"] == "yes":
                # validate_config(s3_bucket, s3_site_path, s3_data_folder, local_swap_folder)
                config.validate()
            q = [
                inquirer.List(
                    "do_edit", message="edit this configuration?", choices=["yes", "no"]
                )
            ]
            ans = inquirer.prompt(q)
            if ans["do_edit"] == "no":
                return
            q = [
                inquirer.Text(
                    "in_endpoint",
                    message=f"S3 endpoint URL (leave blank for {config.endpoint})",
                ),
                inquirer.Text(
                    "in_bucket",
                    message=f"S3 bucket name (leave blank for {config.bucket})",
                ),
                inquirer.Text(
                    "in_sitepath",
                    message=f"S3 path to upload website to (leave blank for {config.sitepath}/)",
                ),
                inquirer.Text(
                    "in_datapath",
                    message=f"S3 path to search for data (leave blank for {config.datapath}/)",
                ),
                inquirer.Text(
                    "in_localpath",
                    message=f"local path to save HTML files to (leave blank for {config.localpath}/)",
                ),
                inquirer.List(
                    "dry",
                    message="run as dry run (no uploads to S3)?",
                    choices=["yes", "no"],
                ),
            ]
            ans = inquirer.prompt(q)
            print(ans["in_endpoint"] == "")
            config.endpoint = (
                ans["in_endpoint"] if ans["in_endpoint"] else config.endpoint
            )
            config.bucket = ans["in_bucket"] if ans["in_bucket"] else config.bucket
            config.sitepath = (
                ans["in_sitepath"] if ans["in_sitepath"] else config.sitepath
            )
            config.datapath = (
                ans["in_datapath"] if ans["in_datapath"] else config.datapath
            )
            config.localpath = (
                ans["in_localpath"] if ans["in_localpath"] else config.localpath
            )
            config.do_s3_write = False if ans["dry"] == "yes" else True


ansi = {
    "black": "\x1b[30m",
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "blue": "\x1b[34m",
    "purple": "\x1b[35m",
    "cyan": "\x1b[36m",
    "white": "\x1b[37m",
    "reset": "\x1b[0m",
}


def printc(*args, color=None, end="\n"):
    if color is not None:
        print(ansi[color.lower()], *args, ansi["reset"], end=end)
    else:
        print(*args, end=end)


# CONFIG VARIABLES:
# s3_bucket = "foxsi-public"  # the bucket name on S3
# s3_site_path = "site"  # path in the bucket to upload HTML to. WILL OVERWRITE!
# s3_data_folder = "data"  # a folder in the bucket to search for data
# # the path on your local system to store the website on before it is uploaded:
# local_swap_folder = os.path.abspath(
#     os.path.join(
#         "s3",
#         "_site",
#         s3_site_path,
#     )
# )  # in the future, I will use tempfiles for this.
# dry_run = (
#     False  # if True, just print what will be written without actually doing it to S3
# )


# s3_endpoint = "https://s3.msi.umn.edu"  # host domain for the bucket
# def do_s3():
#     return not dry_run


def exists(client, bucket, filter_path):
    success = False
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            if obj["Key"].startswith(filter_path + "/"):
                success = True
                break
    return success


def ls(client, bucket, filter_path=None):
    flist = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            if filter_path is not None and obj["Key"].startswith(filter_path + "/"):
                flist.append(obj)
    return flist

    # if permissions on posixpath.join(endpoint, bucket) allow writing, good.


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


def total(d: dict):
    count = 0
    for key, value in d.items():
        count += 1
        if isinstance(value, dict):
            count += total(value)
    return count


class HTMLPage:
    def __init__(self, relpath: str, config: S3SiteConfig):
        self.relpath = relpath
        # self.local_root = local_root
        # self.s3_root = s3_root
        self.contents = []
        self.config = config
        # path to root of bucket
        self.s3_root = posixpath.join(config.endpoint, config.bucket)

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
        stylesheet = f"""<link rel="stylesheet" href="{posixpath.join(self.s3_root, self.config.sitepath, "styles.css")}">"""
        favicon = f"""<link rel="icon" type="image/x-icon" href="{posixpath.join(self.s3_root, self.config.sitepath, "foxsi5icon.png")}">"""
        # stylesheet = ""
        page = f"""<!DOCTYPE html>
                <html lang="en" xml:lang="en">
                    <head>
                        <title>Index of {printpath}</title>
                        {stylesheet}
                        {favicon}
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
        wpath = os.path.join(self.config.localpath, self.relpath)
        if not os.path.exists(wpath):
            os.makedirs(wpath)
        with open(os.path.join(wpath, "index.html"), "w") as f:
            f.write(self.page())
            # print("wrote page to", wpath)


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

    for k in tqdm.trange(len(files), desc="Reconstructing folder structure..."):
        path, file = pathologize_file(files[k])
        thisfolder = root
        for key in path:
            thisfolder = thisfolder.setdefault(key, {})
        if FolderItems.FILES not in thisfolder.keys():
            thisfolder[FolderItems.FILES] = [file]
        else:
            thisfolder[FolderItems.FILES].append(file)
    return root


def html_tree(structure: dict, config: S3SiteConfig):
    queue = deque([BFSItem(structure, "")])
    nlayer = 0

    with tqdm.tqdm(total=1, desc="Building HTML tree...") as prog:
        while len(queue) > 0:  # visit the whole tree
            # next layer of folders to visit (to avoid modifying list while looping over it)
            next_layer_down = []
            for item in queue:
                folder = item.structure
                path = item.path
                # make a new HTML page
                this_page = HTMLPage(path, config)
                # this_page = table_page(path)
                for key in folder.keys():
                    if type(key) is str:  # i.e. a folder[key] is another folder
                        # put a row in this table for the folder, linking
                        # put this folder in the queue
                        prog.total += 1

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

            prog.update(len(queue))
            queue.clear()  # just looped over the whole queue, so it should be done
            queue.extend(next_layer_down)  # put any new folders into the queue
            nlayer += 1


def upload_folder(client, config: S3SiteConfig):
    sources = []
    dests = []
    mimes = []
    for root, dirs, files in os.walk(config.localpath):
        pathsuffix = os.path.relpath(root, config.localpath)
        destpath = posixpath.normpath(posixpath.join(config.sitepath, pathsuffix))
        for file in files:
            source_path = os.path.join(root, file)
            mime, enc = mimetypes.guess_type(source_path)

            if mime is None:
                raise ValueError(f"MIME type cannot be found for {source_path}")
            sources.append(source_path)
            dests.append(posixpath.join(destpath, file))
            mimes.append(mime)
    for k in tqdm.trange(len(dests), desc="uploading"):
        tqdm.tqdm.write(f"> uploading {sources[k]} to {dests[k]}")
        config.do_s3_write and client.upload_file(
            sources[k],
            config.bucket,
            dests[k],
            ExtraArgs={"ContentType": mimes[k]},
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

    config = S3SiteConfig("s3/config.toml")

    config.interactive and config.dialog()

    client = boto3.client("s3", endpoint_url=config.endpoint)
    response = client.list_buckets()
    print("found your buckets: ")
    for b in response["Buckets"]:
        print(f"   {b['Name']}")

    paginator = client.get_paginator("list_objects_v2")

    flist = []
    fnames = []
    for page in paginator.paginate(Bucket=config.bucket):
        for obj in page.get("Contents", []):
            if config.datapath is not None and obj["Key"].startswith(
                config.datapath + "/"
            ):
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


    # # if you want to look at the access control list:
    # print("\ncurrent ACL:")
    # result = client.get_bucket_acl(Bucket=config.bucket)
    # pprint.pprint(result)
    # print()

    # reconstruct the file structure from the linear file list
    file_tree = gen_structure(flist)

    # breadth-first walk the file structure, and emit an HTML page at each layer
    html_tree(file_tree, config)

    # put new HTML in the bucket
    print("\nlocal site root:", end="")
    printc(config.localpath, color="green")
    site_dest = posixpath.join(config.endpoint, config.bucket, config.sitepath)
    print("the site will be uploaded to", end="")
    printc(site_dest, color="green")
    print()
    upload_folder(client, config)

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
                    f"arn:aws:s3:::{config.bucket}/{config.sitepath}/*",
                    f"arn:aws:s3:::{config.bucket}/{config.datapath}/*",
                ],
            }
        ],
    }
    bucket_policy = json.dumps(bucket_policy)
    print(bucket_policy)
    # # Set the new policy
    config.do_s3_write and client.put_bucket_policy(
        Bucket=config.bucket, Policy=bucket_policy
    )
