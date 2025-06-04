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
    service_unit_type: str
    vcpus: int
    memory: int
    storage: int
    gpu_count: int = 0

    @property
    def service_units(self):
        # 1 CPU SU = 0 GPU, 1 CPU, 4 GB RAM, 20 GB
        return self.gpu_count or int(
            max(
                self.vcpus,
                self.memory / 4096,
            )
        )


@dataclass()
class InstanceEvent(object):
    time: datetime.datetime
    name: str
    message: str


@dataclass
class InstanceRuntime(object):
    total_seconds_running: int = 0
    total_seconds_stopped: int = 0

    def __sub__(self, other):
        return InstanceRuntime(
            self.total_seconds_running - other.total_seconds_running,
            self.total_seconds_stopped - other.total_seconds_stopped,
        )


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
        def get_time_in_event_pairs(start_events, end_events, warn=False):
            last_event = None
            last_start_time = None
            total_time = 0
            for event in self.events:
                event_time = self._clamp_time(event.time, start_time, end_time)
                if event.name in start_events:
                    last_start_time = event_time
                elif event.name in end_events:
                    if last_start_time:
                        total_time += (event_time - last_start_time).total_seconds()
                        last_start_time = None
                    if last_event and last_event not in start_events and warn:
                        logger.warning(
                            f"Instance {self.name} was {last_event} between being {start_events} and {end_events}. Billing may be incorrect!"
                        )

                last_event = event.name

            # Account for last event pair that hasn't ended
            if last_start_time and not in_error_state:
                total_time += (end_time - last_start_time).total_seconds()

            return total_time

        runtime = InstanceRuntime()

        in_error_state = False
        delete_action_found = False

        for event in self.events:
            if event.message == "Error":
                in_error_state = True
            elif event.name in ["create", "start"]:
                in_error_state = False
            elif event.name == "delete":
                # Some deleted instances do not have a delete event, they do
                # however have a deleted_at timestamp.
                # Delete event takes precedence over deleted_at.
                delete_action_found = True
                end_time = self._clamp_time(event.time, start_time, end_time)
                break

        if self.deleted_at and not delete_action_found:
            self.no_delete_action = True
            end_time = self._clamp_time(self.deleted_at, start_time, end_time)

        run_time = get_time_in_event_pairs(["create", "start"], ["stop"])
        stopped_time = get_time_in_event_pairs(["stop"], ["start"], warn=True)
        shelved_time = get_time_in_event_pairs(["shelve"], ["unshelve"], warn=True)

        runtime.total_seconds_running = run_time - shelved_time
        runtime.total_seconds_stopped = stopped_time
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

    @staticmethod
    def _get_gpu_flavor_info(pci_info):
        if len(pci_info) > 1:
            raise Exception

        pci_name = pci_info[0].get("alias_name", "").lower()
        if pci_name not in ["a100", "a100-sxm4", "v100", "k80"]:
            raise Exception(f"Invalid pci_name {pci_name}.")

        count = int(pci_info[0]["count"])
        su_type = f"gpu_{pci_name}".replace("-", "")

        return (su_type, count)

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
            su_type = "cpu"
            gpu_count = 0
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
                su_type, gpu_count = self._get_gpu_flavor_info(pci_info)

            flavor = Flavor(
                id=instance["instance_type_id"],
                service_unit_type=su_type,
                vcpus=instance["vcpus"],
                memory=instance["memory_mb"],
                storage=20,
                gpu_count=gpu_count,
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
