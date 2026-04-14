import contextvars
import json
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import settings


_trace_account: contextvars.ContextVar[str] = contextvars.ContextVar("rag_trace_account", default="unknown")
_trace_channel: contextvars.ContextVar[str] = contextvars.ContextVar("rag_trace_channel", default="unknown")
_write_lock = threading.Lock()


@contextmanager
def rag_trace_context(account: str, channel: str) -> Iterator[None]:
    account_token = _trace_account.set(account)
    channel_token = _trace_channel.set(channel)
    try:
        yield
    finally:
        _trace_account.reset(account_token)
        _trace_channel.reset(channel_token)


def archive_trace_event(trace_id: str, event: str, payload: dict[str, Any]) -> Path | None:
    if not settings.rag_trace_archive_enabled:
        return None
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None

    timestamp = datetime.now(timezone.utc)
    record = {
        "timestamp": timestamp.isoformat(),
        "trace_id": trace_id,
        "event": event,
        "account": _trace_account.get(),
        "channel": _trace_channel.get(),
        "payload": payload,
    }
    return _write_trace_record(record, Path(settings.rag_trace_archive_dir))


def _write_trace_record(record: dict[str, Any], base_dir: Path) -> Path:
    timestamp = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
    account = _sanitize_path_component(str(record.get("account") or "unknown"))
    dated_name = timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d")
    target_dir = base_dir / account
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{dated_name}.jsonl"

    with _write_lock:
        with target_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    return target_path


def _sanitize_path_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return sanitized or "unknown"