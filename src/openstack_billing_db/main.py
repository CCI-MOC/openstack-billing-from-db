from decimal import Decimal
from datetime import datetime
import argparse

from openstack_billing_db import billing


def parse_time_argument(arg):
    return datetime.strptime(arg, '%Y-%m-%d')


def main():
    parser = argparse.ArgumentParser(
        prog="python -m openstack_billing_db.main",
        description="Simple OpenStack Invoicing from the Nova DB",
    )

    parser.add_argument(
        "--start",
        required=True,
        type=parse_time_argument,
        help="Start of the invoicing period. (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end",
        required=True,
        help="End of the invoicing period. (YYYY-MM-DD)",
        type=parse_time_argument
    )
    parser.add_argument(
        "--invoice-month",
        default=None,
        help="Use the first column for Invoice Month, rather than Interval."
    )
    parser.add_argument(
        "--coldfront-data-file",
        default=None,
        help=("Path to JSON Output of ColdFront's /api/allocations."
              "Used for populating project names and PIs.")
    )
    parser.add_argument(
        "--sql-dump-file",
        required=True,
        help=("Path to SQL Dump of Nova DB. Must have been converted to SQLite3"
              "compatible format using https://github.com/dumblob/mysql2sqlite.")
    )
    parser.add_argument(
        "--rate-cpu-su",
        default=0,
        type=Decimal,
        help="Rate of CPU SU/hr"
    )
    parser.add_argument(
        "--rate-gpu-a100-su",
        default=0,
        type=Decimal,
        help="Rate of GPU A100 SU/hr"
    )
    parser.add_argument(
        "--rate-gpu-v100-su",
        default=0,
        type=Decimal,
        help="Rate of GPU V100 SU/hr"
    )
    parser.add_argument(
        "--rate-gpu-k80-su",
        default=0,
        type=Decimal,
        help="Rate of GPU K80 SU/hr"
    )
    parser.add_argument(
        "--rate-gpu-a2-su",
        default=0,
        type=Decimal,
        help="Rate of GPU A2 SU/hr"
    )
    parser.add_argument(
        "--include-stopped-runtime",
        default=False,
        type=bool,
        help="Include stopped runtime for instances."
    )
    parser.add_argument(
        "--upload-to-s3",
        default=False,
        type=bool,
        help=("Uploads the CSV result to S3 compatible storage."
              " Must provide S3_OUTPUT_ACCESS_KEY_ID and"
              " S3_OUTPUT_SECRET_ACCESS_KEY environment variables."
              " Defaults to Backblaze and to nerc-invoicing bucket"
              " but can be configured through S3_OUTPUT_BUCKET and"
              " S3_OUTPUT_ENDPOINT_URL environment variables.")
    )
    parser.add_argument(
        "output",
        default="/tmp/openstack_invoices.csv",
        help="Output path for invoice in CSV format."
    )

    args = parser.parse_args()

    rates = billing.Rates(
        cpu=args.rate_cpu_su,
        gpu_a100=args.rate_gpu_a100_su,
        gpu_v100=args.rate_gpu_v100_su,
        gpu_k80=args.rate_gpu_k80_su,
        gpu_a2=args.rate_gpu_a2_su,
        include_stopped_runtime=args.include_stopped_runtime,
    )

    billing.generate_billing(
        args.start,
        args.end,
        args.output,
        rates,
        coldfront_data_file=args.coldfront_data_file,
        invoice_month=args.invoice_month,
        upload_to_s3=args.upload_to_s3,
        sql_dump_file=args.sql_dump_file,
    )


if __name__ == "__main__":
    main()
