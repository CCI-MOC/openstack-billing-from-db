import uuid
from datetime import datetime, timedelta

from openstack_billing_db.model import Instance, InstanceEvent, Database
from openstack_billing_db.tests.unit.utils import FLAVORS, MINUTE, HOUR, DAY, MONTH


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
        datetime(year=1999, month=12, day=1, hour=0, minute=0, second=0),
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


def test_instance_stopped_and_deleted():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(hours=1), name="stop", message=""),
        InstanceEvent(time=time + timedelta(hours=2), name="delete", message=""),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex,
        name=uuid.uuid4().hex,
        flavor=FLAVORS[1],
        events=events,
    )

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == (1 * HOUR)
    assert r.total_seconds_stopped == (1 * HOUR)


def test_instance_shelved_and_unshelved():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=40), name="shelve", message=""),
        InstanceEvent(time=time + timedelta(days=1), name="unshelve", message=""),
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
    assert r.total_seconds_stopped == 0


def test_instance_shelved_no_unshelved():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=40), name="shelve", message=""),
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
    assert r.total_seconds_running == (40 * MINUTE)
    assert r.total_seconds_stopped == 0


def test_instance_shelved_unshelved_stopped():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=40), name="stop", message=""),
        InstanceEvent(time=time + timedelta(days=1), name="start", message=""),
        InstanceEvent(
            time=time + timedelta(days=1, hours=6), name="shelve", message=""
        ),
        InstanceEvent(
            time=time + timedelta(days=1, hours=12), name="unshelve", message=""
        ),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex,
        name=uuid.uuid4().hex,
        flavor=FLAVORS[1],
        events=events,
        deleted_at=time + timedelta(days=2),
    )

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == (40 * MINUTE) + (6 * HOUR) + (12 * HOUR)
    assert r.total_seconds_stopped == DAY - (40 * MINUTE)


def test_instance_error_deleted():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message="Error"),
        InstanceEvent(time=time + timedelta(hours=1), name="delete", message=""),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex, name=uuid.uuid4().hex, flavor=FLAVORS[1], events=events
    )

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == 0
    assert r.total_seconds_stopped == 0


def test_instance_error_restart_failed():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=45), name="stop", message=""),
        InstanceEvent(
            time=time + timedelta(hours=1), name="start", message="Error"
        ),  # This start period should not be counted
        InstanceEvent(
            time=time + timedelta(hours=1, minutes=10), name="delete", message=""
        ),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex, name=uuid.uuid4().hex, flavor=FLAVORS[1], events=events
    )

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == 45 * MINUTE
    assert r.total_seconds_stopped == 15 * MINUTE


def test_instance_error_restarted():
    time = datetime(year=2000, month=1, day=2, hour=0, minute=0, second=0)
    events = [
        InstanceEvent(time=time, name="create", message=""),
        InstanceEvent(time=time + timedelta(minutes=45), name="stop", message=""),
        InstanceEvent(
            time=time + timedelta(hours=1), name="start", message="Error"
        ),  # This start/stop period should not be counted
        InstanceEvent(
            time=time + timedelta(hours=1, minutes=15), name="start", message=""
        ),
        InstanceEvent(
            time=time + timedelta(hours=1, minutes=25), name="delete", message=""
        ),
    ]
    i = Instance(
        uuid=uuid.uuid4().hex, name=uuid.uuid4().hex, flavor=FLAVORS[1], events=events
    )

    r = i.get_runtime_during(
        datetime(year=2000, month=1, day=1, hour=0, minute=0, second=0),
        datetime(year=2000, month=2, day=1, hour=0, minute=0, second=0),
    )
    assert r.total_seconds_running == 45 * MINUTE + 10 * MINUTE
    assert r.total_seconds_stopped == 15 * MINUTE


def test_instance_get_gpu_flavor():
    test_pci_info = [("a100", "2"), ("a100-sxm4", "4")]
    answers = [("gpu_a100", 2), ("gpu_a100sxm4", 4)]
    for i in range(len(test_pci_info)):
        pci_request = [
            {"alias_name": test_pci_info[i][0], "count": test_pci_info[i][1]}
        ]

        su_type, count = Database._get_gpu_flavor_info(pci_request)
        assert su_type == answers[i][0]
        assert count == answers[i][1]


def test_error_event_outside_window():
    start = datetime(2000, 1, 1, 0, 0, 0)
    end = datetime(2000, 2, 1, 0, 0, 0)
    events = [
        InstanceEvent(time=start - timedelta(hours=1), name="create", message="Error")
    ]
    # Case 1: Error BEFORE window
    i = Instance(
        uuid=uuid.uuid4().hex, name=uuid.uuid4().hex, flavor=FLAVORS[1], events=events
    )
    r_before = i.get_runtime_during(start, end)
    assert r_before.total_seconds_running == 0
    assert r_before.total_seconds_stopped == 0
    # Case 2: Error AFTER window
    i.events = [
        InstanceEvent(time=start, name="create", message=""),
        InstanceEvent(time=end + timedelta(hours=1), name="stop", message="Error"),
    ]
    r_after = i.get_runtime_during(start, end)
    assert r_after.total_seconds_running == 1 * MONTH
    assert r_after.total_seconds_stopped == 0
