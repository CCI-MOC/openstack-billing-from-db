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
        "--coldfront-data-file",
        default=None,
        help=("Path to JSON Output of ColdFront's /api/allocations."
              "Used for populating project names and PIs.")
    )
    parser.add_argument(
        "--flavors-cache-file",
        default=None,
        help="Path to file to cache previously encountered flavors."
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
        "output",
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
        flavors_cache_file=args.flavors_cache_file
    )


if __name__ == "__main__":
    main()
