# openstack-billing-from-db
Simple billing solution for OpenStack that fetches the information from the
database.

```bash
usage: python -m openstack_billing_db.main [-h] [--start START] [--end END] [--invoice-month INVOICE_MONTH] [--sql-dump-file SQL_DUMP_FILE]
                                           [--convert-sql-dump-file-to-sqlite CONVERT_SQL_DUMP_FILE_TO_SQLITE]
                                           [--download-sql-dump-from-s3 DOWNLOAD_SQL_DUMP_FROM_S3] [--rate-cpu-su RATE_CPU_SU]
                                           [--rate-gpu-a100sxm4-su RATE_GPU_A100SXM4_SU] [--rate-gpu-a100-su RATE_GPU_A100_SU]
                                           [--rate-gpu-v100-su RATE_GPU_V100_SU] [--rate-gpu-k80-su RATE_GPU_K80_SU] [--rate-gpu-a2-su RATE_GPU_A2_SU]
                                           [--include-stopped-runtime INCLUDE_STOPPED_RUNTIME] [--upload-to-s3 UPLOAD_TO_S3]
                                           [--upload-to-primary-location UPLOAD_TO_PRIMARY_LOCATION] [--output-file OUTPUT_FILE] [--use-nerc-rates]

Simple OpenStack Invoicing from the Nova DB

options:
  -h, --help            show this help message and exit
  --start START         Start of the invoicing period. (YYYY-MM-DD). Defaults to start of last month if 1st of a month, or start of this month otherwise.
  --end END             End of the invoicing period. (YYYY-MM-DD). Not inclusive. Defaults to today.
  --invoice-month INVOICE_MONTH
                        Use the first column for Invoice Month, rather than Interval. Defaults to month of start. (YYYY-MM).
  --sql-dump-file SQL_DUMP_FILE
                        Path to SQL Dump of Nova DB. Must have been converted to SQLite3compatible format using https://github.com/dumblob/mysql2sqlite.
  --convert-sql-dump-file-to-sqlite CONVERT_SQL_DUMP_FILE_TO_SQLITE
                        Automatically convert SQL dump to SQlite3 compatible format using https://github.com/dumblob/mysql2sqlite.
  --download-sql-dump-from-s3 DOWNLOAD_SQL_DUMP_FROM_S3
                        Downloads Nova DB Dump from S3. Must provide S3_INPUT_ACCESS_KEY_ID and S3_INPUT_SECRET_ACCESS_KEY environment variables. Defaults
                        to Backblaze and to nerc-invoicing bucket but can be configured through S3_INPUT_BUCKET and S3_OUTPUT_ENDPOINT_URL environment
                        variables. Automatically decompresses the file if gzipped.
  --rate-cpu-su RATE_CPU_SU
                        Rate of CPU SU/hr
  --rate-gpu-a100sxm4-su RATE_GPU_A100SXM4_SU
                        Rate of GPU A100SXM4 SU/hr
  --rate-gpu-a100-su RATE_GPU_A100_SU
                        Rate of GPU A100 SU/hr
  --rate-gpu-v100-su RATE_GPU_V100_SU
                        Rate of GPU V100 SU/hr
  --rate-gpu-k80-su RATE_GPU_K80_SU
                        Rate of GPU K80 SU/hr
  --rate-gpu-a2-su RATE_GPU_A2_SU
                        Rate of GPU A2 SU/hr
  --include-stopped-runtime INCLUDE_STOPPED_RUNTIME
                        Include stopped runtime for instances.
  --upload-to-s3 UPLOAD_TO_S3
                        Uploads the CSV result to S3 compatible storage. Must provide S3_OUTPUT_ACCESS_KEY_ID and S3_OUTPUT_SECRET_ACCESS_KEY environment
                        variables. Defaults to Backblaze and to nerc-invoicing bucket but can be configured through S3_OUTPUT_BUCKET and
                        S3_OUTPUT_ENDPOINT_URL environment variables.
  --upload-to-primary-location UPLOAD_TO_PRIMARY_LOCATION
                        When uploading to S3, upload both to primary and archive location, or just archive location.
  --output-file OUTPUT_FILE
                        Output path for invoice in CSV format.
  --use-nerc-rates      Set to use usage rates from nerc-rates repo instead of cli arguements

```
