"""Single source of "now".

All business logic reads the current time from here so tests can pin it.
Times are naive restaurant-local datetimes.
"""

from datetime import datetime


def now() -> datetime:
    return datetime.now()
