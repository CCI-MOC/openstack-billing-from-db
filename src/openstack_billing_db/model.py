import json
from abc import abstractmethod
import datetime
from dataclasses import dataclass
from dataclasses_json import dataclass_json
import logging
import sqlite3
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class State:
    name: str
    triggers: list[str]

    time_in: int = 0
    _last_entered: datetime.datetime = None

    def enter(self, time: datetime.datetime):
        self._last_entered = time

    def exit(self, time: datetime.datetime):
        self.time_in += (time - self._last_entered).total_seconds()


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
        def run_state_machine():
            """
            Iterates through `self.events` to determine time
            spent in various VM states (i.e running, stopped)
            """
            current_state = None
            for event in self.events:
                event_time = self._clamp_time(event.time, start_time, end_time)

                # Error state can only be determined by the event message
                if event.message == "Error":
                    if current_state is None:
                        current_state = enter_state("Error", event_time)
                    else:
                        current_state.exit(event_time)
                        current_state = enter_state("Error", event_time)
                    continue

                for state in vm_states:
                    if event.name in state.triggers:
                        if current_state is None:
                            current_state = state
                            state.enter(event_time)
                        elif state.name != current_state.name:
                            current_state.exit(event_time)
                            current_state = state
                            state.enter(event_time)

            # Some VM instances may have a `deleted_at` time, another trigger for the `Deleted` state
            if self.deleted_at:
                deleted_at_time = self._clamp_time(
                    self.deleted_at, start_time, end_time
                )
                current_state.exit(deleted_at_time)
                current_state = enter_state("Deleted", deleted_at_time)

            current_state.exit(end_time)

        def get_state_time(state_name):
            for state in vm_states:
                if state.name == state_name:
                    return state.time_in

        def enter_state(state_name, enter_time) -> State:
            for state in vm_states:
                if state.name == state_name:
                    state.enter(enter_time)
                    return state

        runtime = InstanceRuntime()
        vm_states = [
            State(state_name, state_triggers)
            for state_name, state_triggers in (
                ("Running", ["unshelve", "create", "start"]),
                ("Shelved", ["shelve"]),
                ("Stopped", ["stop"]),
                ("Deleted", ["delete"]),
                ("Error", []),
            )
        ]

        run_state_machine()

        runtime.total_seconds_running = get_state_time("Running")
        runtime.total_seconds_stopped = get_state_time("Stopped")
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
