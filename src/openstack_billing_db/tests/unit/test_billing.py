import uuid
from datetime import datetime, timedelta
import pytest

from openstack_billing_db import billing
from openstack_billing_db.model import Instance, InstanceEvent
from openstack_billing_db.tests.unit.utils import FLAVORS, MINUTE, HOUR, DAY, MONTH


def test_instance_simple_runtime():
    time = datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(days=15), name="delete", message=""),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex, name=uuid.uuid4().hex, flavor=FLAVORS[1], events=events
    )

    r = billing.get_runtime_for_instance(
        i,
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
        excluded_intervals=[
            ["2000-01-07", "2000-01-08"],
            ["2000-01-01", "2000-01-02"],
        ],
    )
    assert r.total_seconds_running == (15 * DAY) - (DAY * 2)
    assert r.total_seconds_stopped == 0


def test_billing_add_su_hours():
    invoice = billing.ProjectInvoice(
        project_name="foo",
        project_id="foo",
        pi="foo",
        institution="foo",
        invoice_interval="foo",
        instances=[],
        rates=None,
    )
    invoice = billing.set_invoice_su_hours(invoice, "cpu", 24)
    assert invoice.cpu_su_hours == 24

    invoice = billing.set_invoice_su_hours(invoice, "gpu_a100", 48)
    assert invoice.gpu_a100_su_hours == 48

    with pytest.raises(Exception) as e:
        invoice = billing.set_invoice_su_hours(invoice, "gpu_fake", 72)
