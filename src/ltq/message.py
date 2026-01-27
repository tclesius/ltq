from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .task import Task


@dataclass
class Message:
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    task_name: str
    task: Task | None = None  # only set when Message created with Task.message
    ctx: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

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
