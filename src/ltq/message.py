from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

def _default_ctx() -> dict[str, Any]:
    return {"created_at": time.time()}


@dataclass
class Message:
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    task_name: str
    ctx: dict[str, Any] = field(default_factory=_default_ctx)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_json(self) -> str:
        return json.dumps(
            {
                "task_name": self.task_name,
                "id": self.id,
                "args": self.args,
                "kwargs": self.kwargs,
                "ctx": self.ctx,
            }
        )

    @classmethod
    def from_json(cls, data: str | bytes) -> Message:
        return cls(**json.loads(data))
