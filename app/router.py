from app.models import NormalizedMessage


class MessageRouter:
    def build_prompt(self, message: NormalizedMessage) -> str:
        return message.text.strip()
