from abc import ABC, abstractmethod
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


@dataclass()
class Flavor(object):

    name: str
    vcpus: int
    memory: int
    storage: int

    @property
    def service_units(self):
        if "gpu" not in self.name:
            # 1 CPU SU = 0 GPU, 1 CPU, 4 GB RAM, 20 GB
            return int(max(
                self.vcpus,
                self.memory / 4096,
            ))
        else:
            split = self.name.split(".")
            return int(split[-1])

    @property
    def service_unit_type(self):
        if "gpu" not in self.name:
            return "CPU"
        else:
            return "GPU"


def get_all_flavors() -> dict[Flavor]:
    c = db_nova_api.cursor()
    c.execute("select id, name, vcpus, memory_mb, root_gb from flavors")
    r = c.fetchall()

    flavors = dict()
    for x in r:
        flavors[x[0]] = Flavor(name=x[1],
                               vcpus=x[2],
                               memory=x[3],
                               storage=x[4])

    # Add flavors that don't exist in the database anymore
    flavors[5] = Flavor(
        name="Unknown", vcpus=1, memory=2048, storage=10
    )
    flavors[11] = Flavor(
        name="Unknown", vcpus=4, memory=8192, storage=10
    )
    flavors[191] = Flavor(
        name="gpu-v100.1", vcpus=12, memory=98304, storage=10
    )


FLAVORS = get_all_flavors()


@dataclass()
class InstanceEvent(object):
    time: datetime.datetime
    name: str
    message: str


@dataclass
class Instance(object):

    uuid: str
    name: str
    flavor: Flavor
    events: list[InstanceEvent]

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
        return self.flavor.service_units

    @property
    def service_unit_type(self):
        return self.flavor.service_unit_type


@dataclass()
class Project(object):
    uuid: str
    instances: list[Instance]


def get_events(instance_uuid):
    c = db_nova.cursor()
    c.execute(f"select created_at, action, message from instance_actions where"
              f" instance_uuid = \"{instance_uuid}\" order by created_at")
    r = c.fetchall()

    events = []
    for x in r:
        i = InstanceEvent(time=x[0], name=x[1], message=x[2])
        events.append(i)
    return events


def get_instances(project):
    c = db_nova.cursor()
    c.execute(f"select uuid, hostname, instance_type_id from instances"
              f" where project_id = \"{project}\"")
    r = c.fetchall()

    instances = []
    for x in r:
        i = Instance(uuid=x[0],
                     name=x[1],
                     flavor=FLAVORS[x[2]],
                     events=get_events(x[0]))
        instances.append(i)
    return instances


def get_projects() -> list[Project]:
    c = db_nova.cursor()
    c.execute("select unique(project_id) from instances")
    r = c.fetchall()

    projects = []
    for x in r:
        p = Project(uuid=x[0], instances=get_instances(x[0]))
        projects.append(p)
    return projects


class BaseDatabase(object):
    @property
    @abstractmethod
    def projects(self) -> list[Project]:
        """Returns a list of Project, containing instances and events."""


class Database(BaseDatabase):

    def __init__(self):
        self._projects = get_projects()

    def projects(self) -> list[Project]:
        return self._projects
