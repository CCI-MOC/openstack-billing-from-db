import csv
from dataclasses import dataclass
import json

from openstack_billing_db import model


@dataclass()
class ProjectInvoice(object):
    """Represents the invoicing data for a project."""

    project_name: str
    project_id: str
    pi: str
    institution: str
    invoice_interval: str

    instances: list[model.Instance]

    cpu_su_hours: int = 0
    gpu_a100_su_hours: int = 0
    gpu_v100_su_hours: int = 0

    institution_specific_code: str = "N/A"


def collect_invoice_data_from_openstack(database, billing_start, billing_end):
    invoices = []
    for project in database.projects:
        invoice = ProjectInvoice(
            project_name="",
            project_id=project.uuid,
            pi="",
            institution="",
            instances=project.instances,
            invoice_interval=f"{billing_start.date()} - {billing_end.date()}"
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
                    elif i.service_unit_type == "GPU A100":
                        invoice.gpu_a100_su_hours += cost
                    elif i.service_unit_type == "GPU V100":
                        invoice.gpu_v100_su_hours += cost
                except Exception:
                    raise Exception("Invalid flavor.")

        invoices.append(invoice)
    return invoices


def load_flavors_cache(flavors_cache_file) -> dict[int: model.Flavor]:
    with open(flavors_cache_file, 'r') as f:
        cache = json.load(f)

    flavors = []
    for flavor in cache:
        flavors.append((model.Flavor(**flavor)))

    return flavors


def write_flavors_cache(flavors_cache_file, flavors):
    with open(flavors_cache_file, 'w') as f:
        f.write(json.dumps(flavors, indent=4))


def merge_coldfront_data(invoices, coldfront_data_file):
    with open(coldfront_data_file, 'r') as f:
        allocations = json.load(f)

    by_project_id = {
        a["attributes"].get("Allocated Project ID"): a for a in allocations
    }

    for invoice in invoices:
        try:
            a = by_project_id[invoice.project_id]
            invoice.project_name = a["attributes"]["Allocated Project Name"]
            invoice.pi = a["project"]["pi"]
        except KeyError:
            continue


def write(invoices, output):
    with open(output, 'w', newline='') as f:
        csv_invoice_writer = csv.writer(
            f, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL
        )
        # Write Headers
        csv_invoice_writer.writerow(
            [
                "Interval",
                "Project Name",
                "Project ID",
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

        for invoice in invoices:
            for invoice_type in ['cpu', 'gpu_a100', 'gpu_v100']:
                # Each project gets two rows, one for CPU and one for GPU
                hours = invoice.__getattribute__(f"{invoice_type}_su_hours")
                if hours > 0:
                    csv_invoice_writer.writerow(
                        [
                            invoice.invoice_interval,
                            invoice.project_name,
                            invoice.project_id,
                            invoice.pi,
                            "",  # Invoice Email
                            "",  # Invoice Address
                            invoice.institution,
                            invoice.institution_specific_code,
                            hours,
                            f"{invoice_type.replace('_', ' ').upper()}",
                            "",  # Rate
                            "",  # Cost
                        ]
                    )


def generate_billing(start, end, output, coldfront_data_file=None,
                     flavors_cache_file=None):
    # Flavors are occasionally deleted leaving no reference in the
    # database.
    flavors_cache = None
    if flavors_cache_file:
        flavors_cache = load_flavors_cache(flavors_cache_file)

    database = model.Database(initial_flavors=flavors_cache)

    if flavors_cache_file:
        write_flavors_cache(
            flavors_cache_file,
            [f.to_dict() for f in database.flavors.values()]
        )

    invoices = collect_invoice_data_from_openstack(database, start, end)
    if coldfront_data_file:
        merge_coldfront_data(invoices, coldfront_data_file)
    write(invoices, output)
