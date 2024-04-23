import uuid
from datetime import datetime, timedelta

from openstack_billing_db.model import Instance, InstanceEvent, Flavor

FLAVORS = {1: Flavor(id=1, name="TestFlavor", vcpus=1, memory=4096, storage=10)}

MINUTE = 60
HOUR = 60 * MINUTE
DAY = HOUR * 24
MONTH = 31 * DAY


def test_instance_simple_runtime():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=30), name="delete", message=""),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex, name=uuid.uuid4().hex, flavor=FLAVORS[1], events=events
    )

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=2, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == 30 * MINUTE
    assert r.total_seconds_stopped == 0


def test_instance_runtime_started_before():
    time = datetime(year=1991, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=30), name="delete", message=""),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex, name=uuid.uuid4().hex, flavor=FLAVORS[1], events=events
    )

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=2, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == 0
    assert r.total_seconds_stopped == 0


def test_instance_runtime_started_before_still_running():
    time = datetime(year=1991, month=1, day=2, hour=0, minute=0, second=0)
    events = [InstanceEvent(time=time, name="create", message="")]
    i = Instance(
        uuid=uuid.uuid4().hex, name=uuid.uuid4().hex, flavor=FLAVORS[1], events=events
    )

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == MONTH
    assert r.total_seconds_stopped == 0


def test_instance_runtime_stopped_and_started():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=40), name="stop", message=""),
        InstanceEvent(time=time + timedelta(days=1), name="start", message=""),
        InstanceEvent(
            time=time + timedelta(days=1, minutes=40), name="delete", message=""
        ),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex, name=uuid.uuid4().hex, flavor=FLAVORS[1], events=events
    )

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == (40 * MINUTE) + (40 * MINUTE)
    assert r.total_seconds_stopped == DAY - (40 * MINUTE)


def test_instance_no_delete_action():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex,
        name=uuid.uuid4().hex,
        flavor=FLAVORS[1],
        events=events,
        deleted_at=time + timedelta(days=1, minutes=40),
    )

    # In current billing cycle
    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == DAY + (40 * MINUTE)
    assert r.total_seconds_stopped == 0

    # Outside billing cycles
    r = i.get_runtime_during(
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=3, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == 0
    assert r.total_seconds_stopped == 0

    r = i.get_runtime_during(
        datetime(year=1999, month=11, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=12, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == 0
    assert r.total_seconds_stopped == 0


def test_instance_no_delete_action_stopped():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=40), name="stop", message=""),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex,
        name=uuid.uuid4().hex,
        flavor=FLAVORS[1],
        events=events,
        deleted_at=time + timedelta(days=1, minutes=40),
    )

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == 40 * MINUTE
    assert r.total_seconds_stopped == DAY


def test_instance_no_delete_action_stopped_restarted():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=40), name="stop", message=""),
        InstanceEvent(time=time + timedelta(days=1), name="start", message=""),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex,
        name=uuid.uuid4().hex,
        flavor=FLAVORS[1],
        events=events,
        deleted_at=time + timedelta(days=1, minutes=40),
    )

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == (40 * MINUTE) + (40 * MINUTE)
    assert r.total_seconds_stopped == DAY - (40 * MINUTE)
