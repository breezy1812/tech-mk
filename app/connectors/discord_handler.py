from typing import Any, Dict, Optional

from app.models import NormalizedMessage


class DiscordParser:
    @staticmethod
    def parse(payload: Dict[str, Any]) -> Optional[NormalizedMessage]:
        # Phase 1: 只做最小 message normalization。
        # 真正 Discord interaction 驗簽與 slash commands 可放到 Phase 2。
        content = payload.get("content")
        author = payload.get("author", {})
        channel_id = payload.get("channel_id")

        if not content:
            return None

        return NormalizedMessage(
            source="discord",
            user_id=str(author.get("id", "unknown")),
            chat_id=str(channel_id or "unknown"),
            text=content,
            raw=payload,
        )
