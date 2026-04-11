from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1)
    user_id: Optional[str] = None
    source: str = "api"


class ChatResponse(BaseModel):
    reply: str
    model: str


class NormalizedMessage(BaseModel):
    source: str
    user_id: str
    chat_id: str
    text: str
    raw: Dict[str, Any]
