import csv
from dataclasses import dataclass
import datetime
import json

from openstack_billing_db import model


@dataclass()
class ProjectInvoice(object):
    """Represents the invoicing data for a project."""

    project_name: str
    pi: str
    institution: str

    instances: list[model.Instance]

    cpu_su_hours: int = 0
    gpu_a100_su_hours: int = 0

    institution_specific_code: str = "N/A"
    invoice_interval: str = "2023-06-01 - 2023-07-01"


ALL_INVOICES = []  # type: list[ProjectInvoice]


def collect_invoice_data_from_openstack():
    projects = model.get_projects()

    billing_start = datetime.datetime(year=2023, month=6, day=1)
    billing_end = datetime.datetime(year=2023, month=7, day=1)

    for project in projects:

        invoice = ProjectInvoice(
            project_name=project.uuid,
            pi="",
            institution="",
            instances=project.instances
        )

        for i in project.instances:  # type: model.Instance
            runtime = i.get_runtime_during(billing_start, billing_end)
            assert runtime <= (billing_end - billing_start).total_seconds()

            if runtime > 0:
                try:
                    su = i.service_units
                    cost = runtime * su

                    if i.service_unit_type == "CPU":
                        invoice.cpu_su_hours += cost
                    elif i.service_unit_type == "GPU":
                        # There's only a A100 flavor at the moment.
                        invoice.gpu_a100_su_hours += cost
                except Exception:
                    raise Exception("Invalid flavor.")

        ALL_INVOICES.append(invoice)


def merge_coldfront_data():
    with open('../coldfront_data.json', 'r') as f:
        allocations = json.load(f)

    by_project_id = {
        a["attributes"].get("Allocated Project ID"): a for a in allocations
    }

    for invoice in ALL_INVOICES:
        try:
            a = by_project_id[invoice.project_name]
            invoice.project_name = a["attributes"]["Allocated Project Name"]
            invoice.pi = a["project"]["pi"]
        except KeyError:
            continue


def write():
    with open('invoices.csv', 'w', newline='') as f:
        csv_invoice_writer = csv.writer(
            f, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL
        )
        # Write Headers
        csv_invoice_writer.writerow(
            [
                "Interval",
                "Project Name",
                "PI",
                "Invoice Email",
                "Invoice Address",
                "Institution",
                "Institution Specific Code",
                "Invoice Type Hours",
                "Invoice Type",
                "Rate",
                "Cost",
            ]
        )

        for invoice in ALL_INVOICES:
            for invoice_type in ['cpu', 'gpu_a100']:
                # Each project gets two rows, one for CPU and one for GPU
                hours = invoice.__getattribute__(f"{invoice_type}_su_hours")
                if hours > 0:
                    csv_invoice_writer.writerow(
                        [
                            invoice.invoice_interval,
                            invoice.project_name,
                            invoice.pi,
                            "",  # Invoice Email
                            "",  # Invoice Address
                            invoice.institution,
                            invoice.institution_specific_code,
                            hours,
                            f"{invoice_type.replace('_', '').upper()}",
                            "",  # Rate
                            "",  # Cost
                        ]
                    )


if __name__ == "__main__":
    collect_invoice_data_from_openstack()
    merge_coldfront_data()
    write()
