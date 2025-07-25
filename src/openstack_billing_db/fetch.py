from datetime import datetime
import logging
import os
import subprocess

import boto3

logger = logging.getLogger(__name__)


def download_latest_dump_from_s3() -> str:
    """Download the dump of the nova db from S3 storage.

    Returns location of uncompressed, downloaded file.

    NERC dumps are stored at S3 compatible storage located with endpoint
    https://holecs.rc.fas.harvard.edu under the bucket nerc-osp-backups.

    This storage is behind firewall, however it's accessible from
    nerc-shift-0.

    Here's an example query for the database dump of 2024-02-02.

    $ aws --endpoint-url https://holecs.rc.fas.harvard.edu \
        s3api list-objects --bucket nerc-osp-backups \
        --prefix dbs/nerc-ctl-0/nova-20240202

    {
        "Contents": [
            {
                "Key": "dbs/nerc-ctl-0/nova-20240202000002.sql.gz",
                "LastModified": "2024-02-02T05:00:36.823Z",
                [omitted]
                "Size": 15703324,
                "StorageClass": "STANDARD",
                "Owner": [omitted]
            }
        ]
    }

    """
    s3_endpoint = os.getenv(
        "S3_INPUT_ENDPOINT_URL", "https://holecs.rc.fas.harvard.edu"
    )
    s3_bucket = os.getenv("S3_INPUT_BUCKET", "nerc-osp-backups")
    s3_key_id = os.getenv("S3_INPUT_ACCESS_KEY_ID")
    s3_secret = os.getenv("S3_INPUT_SECRET_ACCESS_KEY")

    if not s3_key_id or not s3_secret:
        raise Exception(
            "Must provide S3_INPUT_ACCESS_KEY_ID and"
            " S3_INPUT_SECRET_ACCESS_KEY environment variables."
        )

    s3 = boto3.client(
        "s3",
        endpoint_url=s3_endpoint,
        aws_access_key_id=s3_key_id,
        aws_secret_access_key=s3_secret,
    )

    key = None
    today = datetime.today().strftime("%Y%m%d")

    for ctl in ["nerc-ctl-0", "nerc-ctl-1", "nerc-ctl-2"]:
        dumps = s3.list_objects_v2(Bucket=s3_bucket, Prefix=f"dbs/{ctl}/nova-{today}")

        if "Contents" in dumps:
            key = dumps["Contents"][0]["Key"]
            break

    if not key:
        raise Exception(f"No database dumps found for {today}")

    filename = os.path.basename(key)
    download_location = f"/tmp/{filename}"

    logger.info(f"Downloading {key} to {download_location}.")
    s3.download_file(s3_bucket, key, download_location)

    logger.info("Download complete.")

    path_without_ext, extension = os.path.splitext(download_location)
    if extension == ".gz":
        logger.info(f"Uncompressing {download_location}")
        command = subprocess.run(["gzip", "-d", download_location])
        if command.returncode != 0:
            raise Exception(f"Error uncompressing {download_location}.")

        # Uncompressing removes the .gz, so the file should be named
        # same as path above, and the new extension should be .sql.
        download_location = path_without_ext
        logger.info(f"Uncompressed at {path_without_ext}.")

    return download_location


def convert_mysqldump_to_sqlite(path_to_dump) -> str:
    """Converts mysqldump generated SQL file to SQLite compatible.

    Requires mysql2sqlite binary, fetched from here
    https://github.com/dumblob/mysql2sqlite.

    Returns location of converted file.
    """
    path_without_ext, extension = os.path.splitext(path_to_dump)

    if not extension == ".sql":
        raise Exception("Unsupported file extension for conversion to SQLite.")

    logger.info("Converting MySQL dump to SQLite compatible.")

    destination_path = f"/tmp/{os.path.basename(path_without_ext)}_converted.sql"
    with open(f"{destination_path}", "w") as f:
        command = subprocess.run(["mysql2sqlite", path_to_dump], stdout=f)

    if command.returncode != 0:
        raise Exception(
            f"Error converting {path_to_dump} to SQLite compatible"
            f" at {destination_path}."
        )

    logger.info(f"Converted at {destination_path}.")
    return destination_path
