from pydantic import BaseModel

from app.models.enums import ConsentCategory


class ConsentUpdateRequest(BaseModel):
    category: ConsentCategory
    granted: bool


class ConsentStateResponse(BaseModel):
    consent: dict[str, bool]
