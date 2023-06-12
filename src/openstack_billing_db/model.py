import math
import datetime
from dataclasses import dataclass

import mysql.connector


db_nova = mysql.connector.connect(
    host="127.0.0.1",
    database="nova",
    user="root",
    password="root",
)

db_nova_api = mysql.connector.connect(
    host="127.0.0.1",
    database="nova_api",
    user="root",
    password="root",
)


class Flavor(object):
    all_flavors = dict()

    def __init__(self, name, vcpus, memory, storage):
        self.name = name
        self.vcpus = vcpus
        self.memory = memory
        self.storage = storage

    @property
    def service_units(self):
        if "gpu" not in self.name:
            # 1 CPU SU = 0 GPU, 1 CPU, 4 GB RAM, 20 GB
            return int(max(
                self.vcpus,
                self.memory / 4096,
                self.storage / 20
            ))
        else:
            return int(self.name[:-1])

    @property
    def service_unite_type(self):
        if "gpu" not in self.name:
            return "CPU"
        else:
            return "GPU"

    @property
    def cost_per_su(self):
        if self.service_unite_type == "CPU":
            return 1
        else:
            return 2

    @classmethod
    def get_all_flavors(cls):
        c = db_nova_api.cursor()
        c.execute("select id, name, vcpus, memory_mb, root_gb from flavors")
        r = c.fetchall()

        for x in r:
            cls.all_flavors[x[0]] = Flavor(*x[1:])


Flavor.get_all_flavors()


@dataclass()
class InstanceEvent(object):
    time: datetime.datetime
    name: str
    message: str


class Instance(object):

    def __init__(self, uuid, name, flavor):
        self.uuid = uuid
        self.name = name
        self.flavor = flavor
        self.events = self.get_events()

    def get_events(self):
        c = db_nova.cursor()
        c.execute(f"select created_at, action, message from instance_actions where"
                  f" instance_uuid = \"{self.uuid}\" order by created_at")
        r = c.fetchall()

        events = []
        for x in r:
            i = InstanceEvent(time=x[0], name=x[1], message=x[2])
            events.append(i)
        return events

    def get_runtime_during(self, start_time, end_time):
        total_seconds_running = 0
        last_start = None

        for event in self.events:
            if event.time < start_time:
                event.time = start_time

            if event.time > end_time:
                event.time = end_time

            if event.name in ["create", "start"] and event.message != "Error":
                last_start = event.time

            if event.name in ["delete", "stop"]:
                if not last_start:
                    # Deletions don't create a preceding stop event, and stopped
                    # instances can be deleted.
                    continue
                total_seconds_running += (event.time - last_start).total_seconds()
                last_start = None

            if event.name == ["resize"]:
                # Still don't quite know how to get the starting flavor and the ending one
                # but we seemed to have gotten zero resizes in a year.
                raise Exception()

        if last_start:
            total_seconds_running += (end_time - last_start).total_seconds()

        return math.ceil(total_seconds_running / 3600)

    @property
    def service_units(self):
        return Flavor.all_flavors[self.flavor].service_units




@dataclass()
class Project(object):
    uuid: str
    instances: list[Instance]


def get_instances(project):
    c = db_nova.cursor()
    c.execute(f"select uuid, hostname, instance_type_id  from instances"
              f" where project_id = \"{project}\"")
    r = c.fetchall()

    instances = []
    for x in r:
        i = Instance(*x)
        instances.append(i)
    return instances


def get_projects():
    c = db_nova.cursor()
    c.execute("select unique(project_id) from instances")
    r = c.fetchall()

    projects = []
    for x in r:
        p = Project(uuid=x[0], instances=get_instances(x[0]))
        projects.append(p)
    return projects
