# openstack-billing-from-db
Simple billing solution for OpenStack that fetches the information from the
database.

```bash
python3 -m openstack_billing_db.main --help
usage: python -m openstack_billing_db.main [-h] --start START --end END [--invoice-month INVOICE_MONTH]
                                           [--coldfront-data-file COLDFRONT_DATA_FILE] [--sql-dump-file SQL_DUMP_FILE]
                                           [--convert-sql-dump-file-to-sqlite CONVERT_SQL_DUMP_FILE_TO_SQLITE]
                                           [--download-sql-dump-from-s3 DOWNLOAD_SQL_DUMP_FROM_S3] [--rate-cpu-su RATE_CPU_SU]
                                           [--rate-gpu-a100-su RATE_GPU_A100_SU] [--rate-gpu-v100-su RATE_GPU_V100_SU]
                                           [--rate-gpu-k80-su RATE_GPU_K80_SU] [--rate-gpu-a2-su RATE_GPU_A2_SU]
                                           [--include-stopped-runtime INCLUDE_STOPPED_RUNTIME] [--upload-to-s3 UPLOAD_TO_S3]
                                           output

Simple OpenStack Invoicing from the Nova DB

positional arguments:
  output                Output path for invoice in CSV format.

options:
  -h, --help            show this help message and exit
  --start START         Start of the invoicing period. (YYYY-MM-DD)
  --end END             End of the invoicing period. (YYYY-MM-DD)
  --invoice-month INVOICE_MONTH
                        Use the first column for Invoice Month, rather than Interval.
  --coldfront-data-file COLDFRONT_DATA_FILE
                        Path to JSON Output of ColdFront's /api/allocations.Used for populating project names and PIs.
  --sql-dump-file SQL_DUMP_FILE
                        Path to SQL Dump of Nova DB. Must have been converted to SQLite3compatible format using
                        https://github.com/dumblob/mysql2sqlite.
  --convert-sql-dump-file-to-sqlite CONVERT_SQL_DUMP_FILE_TO_SQLITE
                        Automatically convert SQL dump to SQlite3 compatible format using
                        https://github.com/dumblob/mysql2sqlite.
  --download-sql-dump-from-s3 DOWNLOAD_SQL_DUMP_FROM_S3
                        Downloads Nova DB Dump from S3. Must provide S3_INPUT_ACCESS_KEY_ID and S3_INPUT_SECRET_ACCESS_KEY
                        environment variables. Defaults to Backblaze and to nerc-invoicing bucket but can be configured through
                        S3_INPUT_BUCKET and S3_OUTPUT_ENDPOINT_URL environment variables. Automatically decompresses the file if
                        gzipped.
  --rate-cpu-su RATE_CPU_SU
                        Rate of CPU SU/hr
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
                        Uploads the CSV result to S3 compatible storage. Must provide S3_OUTPUT_ACCESS_KEY_ID and
                        S3_OUTPUT_SECRET_ACCESS_KEY environment variables. Defaults to Backblaze and to nerc-invoicing bucket but
                        can be configured through S3_OUTPUT_BUCKET and S3_OUTPUT_ENDPOINT_URL environment variables.

```
