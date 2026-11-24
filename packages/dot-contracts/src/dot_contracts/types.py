from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; everything in the database is UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


# Serialises as ISO-8601 with a trailing Z so browsers never read it as local time.
UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]
