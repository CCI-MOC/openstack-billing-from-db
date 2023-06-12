import datetime

from openstack_billing_db import model


def main():
    projects = model.get_projects()

    billing_start = datetime.datetime(year=2023, month=5, day=1)
    billing_end = datetime.datetime(year=2023, month=6, day=1)

    for project in projects:
        print(f"\n\nProject ID: {project.uuid}")
        print(f"==========================")
        total_project_cost = 0
        for i in project.instances:
            runtime = i.get_runtime_during(billing_start, billing_end)
            if runtime > 0:
                try:
                    su = i.service_units
                    cost_per_su_hrs = 1
                    cost = runtime * su * cost_per_su_hrs
                    total_project_cost += cost

                    print(f"Instance {i.name} ({i.uuid}):\t\t{runtime}hr x {su}SU\t= {cost} SU hrs.")
                except:
                    print(f"Invalid flavor {i.flavor}.")

        print(f"\nTotal project cost {total_project_cost}")


if __name__ == "__main__":
    main()
