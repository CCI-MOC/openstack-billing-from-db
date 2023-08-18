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
        "--coldfront-data-file",
        default=None,
        help=("Path to JSON Output of ColdFront's /api/allocations."
              "Used for populating project names and PIs.")
    )
    parser.add_argument(
        "output",
        help="Output path for invoice in CSV format."
    )

    args = parser.parse_args()

    billing.generate_billing(
        args.start,
        args.end,
        args.output,
        coldfront_data_file=args.coldfront_data_file
    )


if __name__ == "__main__":
    main()
