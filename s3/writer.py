import os
import posixpath
import sys
import mimetypes
import boto3

s3_endpoint = "https://s3.msi.umn.edu"  # host domain for the bucket
s3_bucket = "foxsi-public"  # bucket name
s3_site_path = "site"  # path in bucket to put HTML in

if __name__ == "__main__":
    source = os.path.abspath(sys.argv[1])
    destpath = posixpath.normpath(sys.argv[2])
    if len(sys.argv) > 3:
        mime = sys.argv[3]
    else:
        mime, enc = mimetypes.guess_type(source)
        if mime is None:
            mime = "text/html"

    print('using MIME type', mime)

    print(f"uploading {source} to {posixpath.join(s3_endpoint, s3_bucket, destpath, os.path.basename(source))}")
    client = boto3.client("s3", endpoint_url=s3_endpoint)
    s = client.upload_file(source, s3_bucket, os.path.join(destpath, os.path.basename(source)), ExtraArgs={"ContentType": mime})
