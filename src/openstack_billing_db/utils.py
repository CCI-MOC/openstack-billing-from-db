from datetime import datetime


def parse_time_from_string(time_str: str) -> datetime:
    return datetime.fromisoformat(time_str)
