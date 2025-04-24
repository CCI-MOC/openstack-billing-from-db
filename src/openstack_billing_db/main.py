from decimal import Decimal
from datetime import datetime
from datetime import timedelta
import argparse
import logging

from openstack_billing_db import billing, fetch, utils

from nerc_rates import load_from_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_time_argument(arg):
    if isinstance(arg, str):
        return utils.parse_time_from_string(arg)
    return arg


def default_start_argument():
    d = (datetime.today() - timedelta(days=1)).replace(day=1)
    d = d.replace(hour=0, minute=0, second=0, microsecond=0)
    return d


def default_end_argument():
    d = datetime.today()
    d = d.replace(hour=0, minute=0, second=0, microsecond=0)
    return d


def main():
    parser = argparse.ArgumentParser(
        prog="python -m openstack_billing_db.main",
        description="Simple OpenStack Invoicing from the Nova DB",
    )

    parser.add_argument(
        "--start",
        default=default_start_argument(),
        type=parse_time_argument,
        help=(
            "Start of the invoicing period. (YYYY-MM-DD)."
            " Defaults to start of last month if 1st of a month,"
            " or start of this month otherwise."
        ),
    )
    parser.add_argument(
        "--end",
        default=default_end_argument(),
        type=parse_time_argument,
        help=(
            "End of the invoicing period. (YYYY-MM-DD)."
            " Not inclusive. Defaults to today."
        ),
    )
    parser.add_argument(
        "--invoice-month",
        default=default_start_argument().strftime("%Y-%m"),
        help=(
            "Use the first column for Invoice Month, rather than Interval."
            " Defaults to month of start. (YYYY-MM)."
        ),
    )
    parser.add_argument(
        "--coldfront-data-file",
        default=None,
        help=(
            "Path to JSON Output of ColdFront's /api/allocations."
            "Used for populating project names and PIs. If"
            " --download-coldfront-data option is applied, this"
            " location will be used to save the downloaded output."
        ),
    )
    parser.add_argument(
        "--download-coldfront-data",
        default=False,
        help=(
            "Download ColdFront data from ColdFront. Requires the environment"
            " variables KEYCLOAK_CLIENT_ID and KEYCLOAK_CLIENT_SECRET."
            " Default to NERC Keycloak and ColdFront but can be"
            " configure using KEYCLOAK_TOKEN_URL and COLDFRONT_URL environment"
            " variables."
        ),
    )
    parser.add_argument(
        "--sql-dump-file",
        default="",
        help=(
            "Path to SQL Dump of Nova DB. Must have been converted to SQLite3"
            "compatible format using https://github.com/dumblob/mysql2sqlite."
        ),
    )
    parser.add_argument(
        "--convert-sql-dump-file-to-sqlite",
        default=True,
        help=(
            "Automatically convert SQL dump to SQlite3 compatible format using"
            " https://github.com/dumblob/mysql2sqlite."
        ),
    )
    parser.add_argument(
        "--download-sql-dump-from-s3",
        default=False,
        help=(
            "Downloads Nova DB Dump from S3."
            " Must provide S3_INPUT_ACCESS_KEY_ID and"
            " S3_INPUT_SECRET_ACCESS_KEY environment variables."
            " Defaults to Backblaze and to nerc-invoicing bucket"
            " but can be configured through S3_INPUT_BUCKET and"
            " S3_OUTPUT_ENDPOINT_URL environment variables."
            " Automatically decompresses the file if gzipped."
        ),
    )
    parser.add_argument(
        "--rate-cpu-su", default=0, type=Decimal, help="Rate of CPU SU/hr"
    )
    parser.add_argument(
        "--rate-gpu-a100sxm4-su",
        default=0,
        type=Decimal,
        help="Rate of GPU A100SXM4 SU/hr",
    )
    parser.add_argument(
        "--rate-gpu-a100-su", default=0, type=Decimal, help="Rate of GPU A100 SU/hr"
    )
    parser.add_argument(
        "--rate-gpu-v100-su", default=0, type=Decimal, help="Rate of GPU V100 SU/hr"
    )
    parser.add_argument(
        "--rate-gpu-k80-su", default=0, type=Decimal, help="Rate of GPU K80 SU/hr"
    )
    parser.add_argument(
        "--rate-gpu-a2-su", default=0, type=Decimal, help="Rate of GPU A2 SU/hr"
    )
    parser.add_argument(
        "--include-stopped-runtime",
        default=False,
        type=bool,
        help="Include stopped runtime for instances.",
    )
    parser.add_argument(
        "--upload-to-s3",
        default=False,
        type=bool,
        help=(
            "Uploads the CSV result to S3 compatible storage."
            " Must provide S3_OUTPUT_ACCESS_KEY_ID and"
            " S3_OUTPUT_SECRET_ACCESS_KEY environment variables."
            " Defaults to Backblaze and to nerc-invoicing bucket"
            " but can be configured through S3_OUTPUT_BUCKET and"
            " S3_OUTPUT_ENDPOINT_URL environment variables."
        ),
    )
    parser.add_argument(
        "--upload-to-primary-location",
        default=True,
        type=bool,
        help=(
            "When uploading to S3, upload both to primary and"
            " archive location, or just archive location."
        ),
    )
    parser.add_argument(
        "--output-file",
        default="/tmp/openstack_invoices.csv",
        help="Output path for invoice in CSV format.",
    )
    parser.add_argument(
        "--use-nerc-rates",
        action="store_true",
        help="Set to use usage rates from nerc-rates repo instead of cli arguements",
    )

    args = parser.parse_args()

    logger.info(f"Processing invoices for month {args.invoice_month}.")
    logger.info(f"Interval for processing {args.start} - {args.end}.")
    logger.info(f"Invoice file will be saved to {args.output_file}.")

    dump_file = args.sql_dump_file

    if args.download_sql_dump_from_s3:
        dump_file = fetch.download_latest_dump_from_s3()

    if args.convert_sql_dump_file_to_sqlite:
        dump_file = fetch.convert_mysqldump_to_sqlite(dump_file)

    if not dump_file:
        raise Exception(
            "Must provide either --sql_dump_file" "or --download_dump_from_s3."
        )

    coldfront_data_file = args.coldfront_data_file
    if args.download_coldfront_data:
        coldfront_data_file = fetch.download_coldfront_data(coldfront_data_file)

    if coldfront_data_file:
        logger.info(f"Using ColdFront data file at {coldfront_data_file}.")

    if args.use_nerc_rates:

        def get_decimal_rate(rate_name):
            return nerc_repo_rates.get_value_at(rate_name, args.invoice_month, Decimal)

        nerc_repo_rates = load_from_url()
        rates = billing.Rates(
            cpu=get_decimal_rate("CPU SU Rate"),
            gpu_a100sxm4=get_decimal_rate("GPUA100SXM4 SU Rate"),
            gpu_a100=get_decimal_rate("GPUA100 SU Rate"),
            gpu_v100=get_decimal_rate("GPUV100 SU Rate"),
            gpu_k80=get_decimal_rate("GPUK80 SU Rate"),
            gpu_a2=get_decimal_rate("GPUA2 SU Rate"),
            include_stopped_runtime=(
                nerc_repo_rates.get_value_at(
                    "Charge for Stopped Instances", args.invoice_month, bool
                )
            ),
        )
    else:
        rates = billing.Rates(
            cpu=args.rate_cpu_su,
            gpu_a100sxm4=args.rate_gpu_a100sxm4_su,
            gpu_a100=args.rate_gpu_a100_su,
            gpu_v100=args.rate_gpu_v100_su,
            gpu_k80=args.rate_gpu_k80_su,
            gpu_a2=args.rate_gpu_a2_su,
            include_stopped_runtime=args.include_stopped_runtime,
        )

    logger.info(f"Using rates: {rates}.")

    billing.generate_billing(
        args.start,
        args.end,
        args.output_file,
        rates,
        coldfront_data_file=coldfront_data_file,
        invoice_month=args.invoice_month,
        upload_to_s3=args.upload_to_s3,
        sql_dump_file=dump_file,
        upload_to_primary_location=args.upload_to_primary_location,
    )


if __name__ == "__main__":
    main()
