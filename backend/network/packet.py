from dataclasses import dataclass, field
from typing import Any


@dataclass
class Packet:
    source_ip: str
    destination_ip: str
    protocol: str
    payload: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)