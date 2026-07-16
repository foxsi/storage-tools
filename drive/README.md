# Tools for FOXSI Google Drive

These are tools for digesting and migrating Google Drive content. The substrate under all this is [`rclone`](https://rclone.org/drive/).

In 2027, Google will start charging universities for storage space. The upshot is we need to move all our bulky raw data off of Google, and move our documents from the current FOXSI drive to a Google Shared Drive. 

### Details

The classical FOXSI Google Drive is a "My Drive", meaning it is owned by an individual Google account and shared with other Google accounts. 

When a user uploads data to a My Drive, it is counted against their account data quota. 

When a user uploads data to a Shared Drive, it is counted against the Shared Drive quota. So an organization can pay for storage, rather than an individual account.

> [!NOTE]
> The Google Drive API does not provide any way to assess the size of Google Docs, Sheets, or Slides. We can download them as their MS Office counterparts, but we still don't know how much of Google's storage they take up. `rclone` gives these files a size of `-1`.

## Scripts

### [`parse_ls.py`](parse_ls.py)

This script ingests the printout from the `rclone lsl endpoint:FOXSI` command run on the root of the FOXSI My Drive.

It categorizes the different file extensions it finds in the drive and makes some plots and summary information about the data stored. 

The categories are:
- Documents
- Images
- Movies
- Code files
- CAD files
- Raw data files
- Other

> [!NOTE]
> I need to make this script reference the `filter*.txt` files, so it works with the same truth data as `rclone` commands.

## `rclone` commands

This is a good one to copy everything. Probably want to add some logging to it.

```console
$ rclone copy --drive-shared-with-me --filter-from drive/filter-drive.txt foxsi4_google:FOXSI/ foxsi_shared: -P
```

## To do for Thanasi

- [ ] Find the `*.img` files. These seem to be raw data from the pixelated attuator tests at SPring-8. Back these up to raw data storage, don't migrate.
- [ ] For `*.txt` files: most of the volume is from FOXSI-3 detector data, particularly at the ALS. Back these up to raw data storage, don't migrate. There are also plenty of terminal printouts and some LISS data stored as `.txt`.
- [ ] For `*.vrd`, `*.vsd` files: these look like vibration test data. I'm not migrating these but they should be referenced somewhere in the new world.
- [ ] For `*.dta` files: these look like launch data from NSROC. Should be put in with data storage.