"""Generator file to add generic operations"""

from datetime import datetime
from zoneinfo import ZoneInfo


def gen_monthly_range(month: int, year: int) -> tuple[datetime, datetime]:
    """Generates range for a given month of a year
    Args:
        month (int): month number to generate the range for,
        year (int): year of the month to generate the range for.

    Returns:
        tuple[datetime, datetime]: Timezone aware Datetimes of the generated range.
    """
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    return (
        datetime(year=year, month=month, day=1, tzinfo=ZoneInfo("UTC")),
        datetime(year=next_year, month=next_month, day=1, tzinfo=ZoneInfo("UTC")),
    )
