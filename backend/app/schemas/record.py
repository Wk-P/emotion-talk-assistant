from typing import Any

from pydantic import BaseModel

from app.core.timefmt import KSTDateTime
from app.models.enums import RecordType


class SaveRecordRequest(BaseModel):
    session_id: str
    record_type: RecordType
    payload: dict[str, Any]


class RecordResponse(BaseModel):
    id: str
    record_type: RecordType
    payload: dict[str, Any]
    created_at: KSTDateTime


class OwnRecordItem(RecordResponse):
    """A record in the "my records" list, which spans all of the owner's
    conversations — so it carries which conversation it came from."""

    session_id: str
    session_created_at: KSTDateTime
