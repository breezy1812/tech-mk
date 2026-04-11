from typing import Any, Dict, Optional

from app.models import NormalizedMessage


class TelegramParser:
    @staticmethod
    def parse(payload: Dict[str, Any]) -> Optional[NormalizedMessage]:
        message = payload.get("message") or payload.get("edited_message")
        if not message:
            return None

        text = message.get("text")
        if not text:
            return None

        from_user = message.get("from", {})
        chat = message.get("chat", {})

        return NormalizedMessage(
            source="telegram",
            user_id=str(from_user.get("id", "unknown")),
            chat_id=str(chat.get("id", "unknown")),
            text=text,
            raw=payload,
        )
