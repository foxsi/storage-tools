# What S3 is used for

S3 is an interface to object storage. Object storage just means dumping data somewhere on the internet.

In S3, you put data into _buckets_.

On FOXSI, we can fit all our calibration, test, and flight data in S3 without paying a dime. But S3 makes it tricky to browse that data or get it back out.

The tools in this folder are for working with data on S3 without too much effort. One tool in particular, [`make_s3_site.py`](make_s3_site.py), figures out what is inside a bucket and spits out an HTML site you can use to browse the bucket.

## What [`make_s3_site.py`](make_s3_site.py) is used for

This script:

1. Retrieves a full file listing from an S3 bucket of your choice.
2. Creates a static HTML website you can use to navigate the bucket.
3. Uploads the website back to the same bucket.
4. Updates permissions on the bucket to make it publicly readable.

The site that is created looks like this:
![A picture of a table of files](../assets/site-view.png "Sample listing of an S3 site")

## Using [`make_s3_site.py`](make_s3_site.py)

This script depends on [`boto3`](https://docs.aws.amazon.com/boto3/latest/), a library exposing the S3 API, and you can install it using `pip` (and probably `conda` too).

### Credentials

In order to run this script, [`boto3` needs to see some ID](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html). To find your ID—your access key and secret key—visit the [MSI credentials page](https://msi.umn.edu/storage/data-storage/second-tier-storage/s3-credentials).

On your computer (doesn't need to be on a UMN VPN or anything), create a directory for AWS configuration:

```console
$ mkdir $HOME/.aws/
```

Make a file in the directory:

```console
$ touch $HOME/.aws/credentials
```

Edit the `credentials` file so it looks like this, but with your keys instead:

```ini
[default]
aws_access_key_id = YOURACCESSKEY
aws_secret_access_key = yourVerySecretKeyAndMaybeSomeNumbers
```

> [!CAUTION]
> Don't put this file on Github!

Now when you use `boto3` it will use this file to authenticate you.

### Configuring

Make another file in the `$HOME/.aws` directory:

```console
$ touch $HOME/.aws/config
```

and edit it to contain this info:

```ini
[default]
request_checksum_calculation=when_required
response_checksum_validation=when_required
```

Without these checksum settings, uploads through S3 don't work [for some reason](https://github.com/boto/boto3/issues/4398).

### Permissions

There is a [byzantine system](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-with-s3-policy-actions.html) of [permissions](https://msi.umn.edu/storage/data-storage-faqs/how-do-i-use-s3-buckets-share-data-tier-2-storage-other-users) for users to interact in any way with S3.

Thanasi can provide some canned permissions files if that makes things easier.

### Before you run

Check the file configuration file [`config.toml`](config.toml) that comes with this repository. It has plenty of comments. The script will read this file and prompt you through configuration as you go, but the default values should not be harmful.

There is a helpful flag
```toml
[s3]
dryrun = true
```
you can set to `true` to run the script without actually doing any write operations on the S3 bucket. You'll just see the printout of files and folders that will be modified.

When you run the script, it will prompt you to review the configuration and validate it before actually touching anything in the bucket.


#### Configuration detail

The [`config.toml`](config.toml) file has two headings: `[s3]`, and `[local]`. The former contains variables that affect the S3 site, and the latter contains variables that affect your own computer when you run the script. Below, the syntax `s3.endpoint` refers to the keyword `endpoint` under the header `[s3]` (and so on).

There are some key values to configure:

| Configuration       | Values                   | Description |
|:--------------------|:-------------------------|:------------|
| `s3.dryrun`         | `true`, `false`          | `true` means don't actually modify the S3 bucket, `false` means do make changes |
| `s3.clear_sitepath` | `true`, `false` | `true` means erase the `s3.sitepath` before writing the new site, to get rid of stale info. If `s3.dryrun = true`, this setting is ignored |
| `s3.bucket`         | a string | [A valid S3 bucket name](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html); you should have read and write access to the bucket  |
| `s3.datapath`       | a string | A path to a folder in the bucket which you want to build the index site for. The folder should exist already. Don't put leading or trailing slashes; all slashes should go forward `/`. |
| `s3.sitepath`       | a string | A path to a folder in the bucket where you want to store the website files. If `s3.clear_sitepath` is `true`, this will be wiped. |
| `s3.endpoint`       | a URL    | The host site for your S3 service. |
| `local.path`        | a string or `false` | If `false`, use a temporary directory to save generated HTML files to before the are uploaded to S3. Otherwise provide a path to a local folder for the HTML files (useful for inspection and debugging). **Note that this path will be overwritten.** | 
| `local.interactive` | `true`, `false` | If `true`, the script prompts the user for confirmation, edits, etc. before modifying S3. If `false` it just runs. |
| `local.landingpath` | a string | A path to an HTML landing page, if you want to provide a landing page before the data index on the website. A sample is included in [this repository](static/landing.html). Use the empty string if you don't want a landing page. Note that this will be uploaded directly to the `s3.sitepath` root folder, so if there's another page in there with the same name, this one will be overwritten. |
| `local.auxpath` | an array | Each element in the array should be a local path, or the array should be empty. A given folder `something` will be uploaded verbatim to `s3.sitepath/something/` with the full (recursive) contents of `something` included. This is useful for uploading assets and CSS. |


### Running

> [!CAUTION]
> Running this script will modify the data in the S3 bucket you specify. I don't want you to be unpleasantly surprised. The previous section covers what will change.

To build and upload the index website, just do this (assuming you're in the `storage-tools` root):

```console
$ python s3/make_s3_site.py
```

You should be prompted through the configuration before your script tries to modify data on S3.

_(In the future, I will add some info about interactivity, logging, and daemon execution here.)_
