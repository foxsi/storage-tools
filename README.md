# storage-tools

Tooling for serving FOXSI data publicly and moving it around internally.

## [S3](s3/README.md)

We want to make FOXSI flight and calibration data publicly available. We can store our data on the [UMN MSI](https://msi.umn.edu/)'s Tier 2 storage system. We can access that storage through an [S3 API](https://en.wikipedia.org/wiki/Amazon_S3) using the Python [boto3](https://docs.aws.amazon.com/boto3/latest/) package.

See the [S3 README](s3/README.md) for configuration and usage.

## [Google Drive](drive)

We store a lot of project documentation on Google Drive. Sometimes we need to move it around, index it, etc. These tools support those activities.
