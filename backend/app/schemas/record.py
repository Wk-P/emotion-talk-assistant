from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import RecordType


class SaveRecordRequest(BaseModel):
    session_id: str
    record_type: RecordType
    payload: dict[str, Any]


class RecordResponse(BaseModel):
    id: str
    record_type: RecordType
    payload: dict[str, Any]
    created_at: datetime
