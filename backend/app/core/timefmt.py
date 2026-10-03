"""Every time the API returns is in Korea time (UTC+9) with an explicit
offset, e.g. "2026-10-02T18:47:50+09:00" — participants and the research
team are in Korea, and an explicit offset can't be misread by any client.

The database stores UTC; SQLite hands values back without a zone, so naive
values are taken as UTC here.
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

from pydantic import PlainSerializer

KST = timezone(timedelta(hours=9))


def kst_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(KST).isoformat()


def kst_iso_or_none(value: datetime | None) -> str | None:
    return kst_iso(value) if value else None


# For response-schema fields typed as datetime.
KSTDateTime = Annotated[datetime, PlainSerializer(kst_iso, return_type=str)]
