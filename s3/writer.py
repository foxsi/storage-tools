import posixpath
import sys
import mimetypes
import boto3

s3_endpoint = "https://s3.msi.umn.edu"  # host domain for the bucket
s3_bucket = "foxsi-public"  # bucket name
s3_site_path = "site"  # path in bucket to put HTML in

if __name__ == "__main__":
    source = sys.argv[1]
    destpath = sys.argv[2]
    if len(sys.argv) > 3:
        mime = sys.argv[3]
    else:
        mime, enc = mimetypes.guess_type(source)
        if mime is None:
            mime = "text/html"

    print(f"uploading {source} to {posixpath.join(s3_endpoint, s3_bucket, destpath)}")
    client = boto3.client("s3", endpoint_url=s3_endpoint)
    client.upload_file(source, s3_bucket, destpath, ExtraArgs={"ContentType": mime})
