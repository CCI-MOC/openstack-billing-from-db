import csv
from dataclasses import dataclass
from decimal import Decimal
import json

from openstack_billing_db import model


@dataclass()
class Rates(object):
    cpu: Decimal
    gpu_a100: Decimal
    gpu_v100: Decimal
    gpu_a2: Decimal
    gpu_k80: Decimal

    cpu_su_name: str = "OpenStack CPU"
    gpu_a100_su_name: str = "OpenStack GPUA100"
    gpu_v100_su_name: str = "OpenStack GPUV100"
    gpu_a2_su_name: str = "OpenStack GPUA2"
    gpu_k80_su_name: str = "OpenStack GPUK80"


@dataclass()
class ProjectInvoice(object):
    """Represents the invoicing data for a project."""

    project_name: str
    project_id: str
    pi: str
    institution: str
    invoice_interval: str

    instances: list[model.Instance]

    rates: Rates

    cpu_su_hours: int = 0
    gpu_a100_su_hours: int = 0
    gpu_v100_su_hours: int = 0
    gpu_k80_su_hours: int = 0
    gpu_a2_su_hours: int = 0

    institution_specific_code: str = "N/A"

    @property
    def cpu_su_cost(self):
        return self.rates.cpu * self.cpu_su_hours

    @property
    def gpu_a100_su_cost(self):
        return self.rates.gpu_a100 * self.gpu_a100_su_hours

    @property
    def gpu_v100_su_cost(self):
        return self.rates.gpu_v100 * self.gpu_v100_su_hours

    @property
    def gpu_k80_su_cost(self):
        return self.rates.gpu_k80 * self.gpu_k80_su_hours

    @property
    def gpu_a2_su_cost(self):
        return self.rates.gpu_a2 * self.gpu_a2_su_hours


def collect_invoice_data_from_openstack(database, billing_start, billing_end, rates):
    invoices = []
    for project in database.projects:
        invoice = ProjectInvoice(
            project_name="",
            project_id=project.uuid,
            pi="",
            institution="",
            instances=project.instances,
            invoice_interval=f"{billing_start.date()} - {billing_end.date()}",
            rates=rates
        )

        for i in project.instances:  # type: model.Instance
            runtime = i.get_runtime_during(billing_start, billing_end)
            assert runtime <= (billing_end - billing_start).total_seconds()

            if runtime > 0:
                try:
                    su = i.service_units
                    su_hours = runtime * su

                    if i.service_unit_type == "CPU":
                        invoice.cpu_su_hours += su_hours
                    elif i.service_unit_type == "GPU A100":
                        invoice.gpu_a100_su_hours += su_hours
                    elif i.service_unit_type == "GPU V100":
                        invoice.gpu_v100_su_hours += su_hours
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
                "Project - Allocation",
                "Project - Allocation ID",
                "Manager (PI)",
                "Invoice Email",
                "Invoice Address",
                "Institution",
                "Institution - Specific Code",
                "SU Hours (GBhr or SUhr)",
                "SU Type",
                "Rate",
                "Cost",
            ]
        )

        for invoice in invoices:
            for invoice_type in ['cpu', 'gpu_a100', 'gpu_v100', 'gpu_k80', 'gpu_a2']:
                # Each project gets two rows, one for CPU and one for GPU
                hours = invoice.__getattribute__(f"{invoice_type}_su_hours")
                rate = invoice.rates.__getattribute__(invoice_type)
                su_name = invoice.rates.__getattribute__(f"{invoice_type}_su_name")
                cost = invoice.__getattribute__(f"{invoice_type}_su_cost")
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
                            su_name,
                            rate,  # Rate
                            cost,  # Cost
                        ]
                    )


def generate_billing(start, end, output, rates,
                     coldfront_data_file=None, flavors_cache_file=None):
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

    invoices = collect_invoice_data_from_openstack(database, start, end, rates)
    if coldfront_data_file:
        merge_coldfront_data(invoices, coldfront_data_file)
    write(invoices, output)
