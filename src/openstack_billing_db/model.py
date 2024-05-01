import json
from abc import abstractmethod
import datetime
from dataclasses import dataclass
from dataclasses_json import dataclass_json
import logging
import sqlite3
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass_json()
@dataclass()
class Flavor(object):
    id: int
    name: str
    vcpus: int
    memory: int
    storage: int

    @property
    def service_units(self):
        if "gpu" not in self.name:
            # 1 CPU SU = 0 GPU, 1 CPU, 4 GB RAM, 20 GB
            return int(
                max(
                    self.vcpus,
                    self.memory / 4096,
                )
            )
        else:
            # The flavor for 2 SUs of V100 is inconsistent with previous
            # naming scheme.
            if self.name == "gpu-su-v100.1m":
                return 2

            split = self.name.split(".")
            return int(split[-1])

    @property
    def service_unit_type(self):
        if "gpu" not in self.name:
            return "CPU"
        elif "a100-sxm4" in self.name:
            return "GPU A100SXM4"
        elif "a100" in self.name and "sxm4" not in self.name:
            return "GPU A100"
        elif "v100" in self.name:
            return "GPU V100"
        elif "k80" in self.name:
            return "GPU K80"
        elif "gpu-su-a2" in self.name:
            return "GPU A2"
        else:
            # New GPU type that we need to take into account.
            raise Exception()


@dataclass()
class InstanceEvent(object):
    time: datetime.datetime
    name: str
    message: str


@dataclass
class InstanceRuntime(object):
    total_seconds_running: int = 0
    total_seconds_stopped: int = 0


@dataclass
class Instance(object):
    uuid: str
    name: str
    flavor: Flavor
    events: list[InstanceEvent]

    deleted_at: Optional[datetime.datetime] = None
    no_delete_action: bool = False

    @staticmethod
    def _clamp_time(time, min_time, max_time):
        # Note(knikolla): SQLite gives me a string here, sometimes.
        if isinstance(time, str):
            time = datetime.datetime.fromisoformat(time)

        if time < min_time:
            time = min_time
        if time > max_time:
            time = max_time
        return time

    def get_runtime_during(self, start_time, end_time):
        runtime = InstanceRuntime()

        last_start = None  # Time the instance was last started
        last_stop = None  # Time the instance was last stopped
        in_error_state = False
        delete_action_found = False

        # If the instance as a deleted_at time, clamp it to within
        # the invoicing period.
        if self.deleted_at:
            self.deleted_at = self._clamp_time(self.deleted_at, start_time, end_time)

        for event in self.events:
            event.time = self._clamp_time(event.time, start_time, end_time)

            if event.message == "Error":
                in_error_state = True
                continue

            if event.name in ["create", "start"]:
                last_start = event.time
                in_error_state = False

                # Count stopped time from last known stop.
                if last_stop:
                    runtime.total_seconds_stopped += (
                        last_start - last_stop
                    ).total_seconds()
                    last_stop = None

            # Some deleted instances do not have a delete event, they do
            # however have a deleted_at timestamp.
            if event.name == "delete":
                delete_action_found = True

            if event.name in ["delete", "stop"]:
                last_stop = event.time

                # Count running time from last known start.
                if last_start:
                    runtime.total_seconds_running += (
                        last_stop - last_start
                    ).total_seconds()
                    last_start = None

            if event.name == "delete":
                # Prevent counting deletion as a stopped state by
                # unsetting the last stop time.
                last_stop = None
                break

        if self.deleted_at and not delete_action_found:
            self.no_delete_action = True
            end_time = self.deleted_at

        # Handle the time since the last event.
        if last_start:
            runtime.total_seconds_running += (end_time - last_start).total_seconds()

        if last_stop and not in_error_state:
            runtime.total_seconds_stopped += (end_time - last_stop).total_seconds()

        return runtime

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


class BaseDatabase(object):
    @property
    @abstractmethod
    def projects(self) -> list[Project]:
        """Returns a list of Project, containing instances and events."""


class Database(BaseDatabase):
    def __init__(self, start, sql_dump_location: str):
        self.db_nova = sqlite3.connect(":memory:")
        self.db_nova.row_factory = sqlite3.Row
        with open(sql_dump_location, "r") as sql:
            self.db_nova.executescript(sql.read())
        self.start = start

        self._projects = None

    @property
    def projects(self) -> list[Project]:
        if not self._projects:
            self._projects = self.get_projects()

        return self._projects

    def get_events(self, instance_uuid) -> list[InstanceEvent]:
        cursor = self.db_nova.cursor()
        cursor.execute(
            f"select created_at, action, message from instance_actions where"
            f' instance_uuid = "{instance_uuid}" order by created_at'
        )
        return [
            InstanceEvent(
                time=event["created_at"], name=event["action"], message=event["message"]
            )
            for event in cursor.fetchall()
        ]

    def get_instances(self, project) -> list[Instance]:
        instances = []

        cursor = self.db_nova.cursor()
        cursor.execute(
            f"""
            select
                instances.uuid,
                hostname,
                instance_type_id,
                memory_mb,
                vcpus,
                instances.deleted_at,
                pci_requests
            from instances
            left join instance_extra on instances.uuid = instance_extra.instance_uuid
            where
                instances.project_id = "{project}"
                and (instances.deleted_at > "{self.start.isoformat()}"
                    or instances.deleted = 0)
        """
        )

        for instance in cursor.fetchall():
            try:
                pci_info = json.loads(instance["pci_requests"])
            except TypeError:
                pci_info = None
                logger.warning(
                    f"Could not parse pci requests from instance {instance}."
                )
            su_name = "cpu"
            if pci_info:
                # The PCI Requests column of the database contains a JSON
                # object with the below format. If the instance has an
                # associated GPU, it will show up in the list of PCI
                # requests as below.
                #
                # [
                #   {
                #     "count": 1,
                #     "spec": [...],
                #     "alias_name": "V100",
                #     "is_new": false,
                #     "numa_policy": "legacy",
                #     "request_id": null,
                #     "requester_id": null
                #   }
                # ]
                if len(pci_info) > 1:
                    raise Exception

                pci_name = pci_info[0].get("alias_name", "").lower()
                if pci_name not in ["a100", "a100-sxm4", "v100", "k80"]:
                    raise Exception(f"Invalid pci_name {pci_name}.")

                count = pci_info[0]["count"]
                su_name = f"gpu-{pci_name}.{count}"

            flavor = Flavor(
                id=instance["instance_type_id"],
                name=su_name,
                vcpus=instance["vcpus"],
                memory=instance["memory_mb"],
                storage=20,
            )

            i = Instance(
                uuid=instance["uuid"],
                name=instance["hostname"],
                flavor=flavor,
                events=self.get_events(instance["uuid"]),
                deleted_at=instance["deleted_at"],
            )
            instances.append(i)
        return instances

    def get_projects(self) -> list[Project]:
        cursor = self.db_nova.cursor()
        cursor.execute("select distinct project_id from instances")
        return [
            Project(uuid=project[0], instances=self.get_instances(project[0]))
            for project in cursor.fetchall()
        ]
