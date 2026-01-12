"""helpers module"""
# Helper mappings:

from datetime import datetime
from zoneinfo import ZoneInfo

DAYS_EN = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

MONTHS_EN = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def to_utc_naive(date_str: str) -> datetime:
    """Helper to convert AI strings into UTC naive for the database

    Args:
        date_str(str): Ai string date
    Returns:
        datetime: UTC naive time without timezone

    """
    # 1. Parse AI string
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")

    # 2. Make it timezone Aware
    dt_tz = dt.replace(tzinfo=ZoneInfo("Europe/Madrid"))

    # 3. UTC conversion
    dt_utc = dt_tz.astimezone(ZoneInfo("UTC"))

    # 4. Convert to naive.
    return dt_utc.replace(tzinfo=None)


def from_utc_to_local(dt_utc: datetime) -> datetime:
    """Helper to convert database dates into Naive timezones for AI
    Args:
        dt_utc(str): utc date without timezone
    Returns:
        datetime: Timezone converted datetime

    """
    # 1. Make it UTC
    dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))

    # 2. Convert to timezone and make it naive to make it easier to read for the AI
    return dt_utc.astimezone(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
