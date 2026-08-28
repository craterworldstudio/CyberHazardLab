from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class Event:
    type: str
    source: str | None
    destination: str | None
    protocol: str | None = None
    port: int | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


