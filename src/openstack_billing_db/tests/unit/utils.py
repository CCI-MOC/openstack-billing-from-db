from openstack_billing_db import model

FLAVORS = {1: model.Flavor(id=1, name="TestFlavor", vcpus=1, memory=4096, storage=10)}

MINUTE = 60
HOUR = 60 * MINUTE
DAY = HOUR * 24
MONTH = 31 * DAY
