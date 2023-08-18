import uuid
from datetime import datetime, timedelta

from openstack_billing_db.model import Instance, InstanceEvent, Flavor

FLAVORS = {
    1: Flavor(name="TestFlavor",
              vcpus=1,
              memory=4096,
              storage=10)
}


def test_instance_simple_runtime():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=30), name="delete", message="")
    ]
    i = Instance(uuid=uuid.uuid4().hex,
                 name=uuid.uuid4().hex,
                 flavor=FLAVORS[1],
                 events=events)

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=2, hour=0, minute=0, second=0)
    )
    assert r == 1


def test_instance_runtime_started_before():
    time = datetime(year=1991, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=30), name="delete", message="")
    ]
    i = Instance(uuid=uuid.uuid4().hex,
                 name=uuid.uuid4().hex,
                 flavor=FLAVORS[1],
                 events=events)

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=2, hour=0, minute=0, second=0)
    )
    assert r == 0


def test_instance_runtime_started_before_still_running():
    time = datetime(year=1991, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message="")
    ]
    i = Instance(uuid=uuid.uuid4().hex,
                 name=uuid.uuid4().hex,
                 flavor=FLAVORS[1],
                 events=events)

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0)
    )
    assert r == (31 * 24 * 1)


def test_instance_runtime_stopped_and_started():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=40), name="stop", message=""),
        InstanceEvent(time=time + timedelta(days=1), name="start", message=""),
        InstanceEvent(time=time + timedelta(days=1, minutes=40), name="delete", message="")
    ]
    i = Instance(uuid=uuid.uuid4().hex,
                 name=uuid.uuid4().hex,
                 flavor=FLAVORS[1],
                 events=events)

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0)
    )
    assert r == 2
