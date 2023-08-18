# openstack-billing-from-db
Simple billing solution for OpenStack that fetches the information from the
database.

```bash
usage: python -m openstack_billing_db.main [-h] --start START --end END

Simple OpenStack Invoicing from the Nova DB

options:
  -h, --help     show this help message and exit
  --start START  Start of the invoicing period. (YYYY-MM-DD)
  --end END      End of the invoicing period. (YYYY-MM-DD)

```
