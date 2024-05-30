from openstack_billing_db.model import InstanceRuntime


def test_instance_runtime_subtract():
    a = InstanceRuntime(total_seconds_running=1000, total_seconds_stopped=1000)
    b = InstanceRuntime(total_seconds_running=100, total_seconds_stopped=200)
    c = a - b
    assert c.total_seconds_running == 900
    assert c.total_seconds_running == a.total_seconds_running - b.total_seconds_running
    assert c.total_seconds_stopped == 800
    assert c.total_seconds_stopped == a.total_seconds_stopped - b.total_seconds_stopped
