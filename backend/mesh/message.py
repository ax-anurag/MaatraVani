"""Message format for the offline mesh.

Same shape whether a message travels through the local simulation or a real
Bluetooth LE transport:

    Message {
        id          unique, used for duplicate detection
        sender_id   who composed it (e.g. "teacher")
        timestamp   ISO-8601
        ttl         drops by 1 per relay; message dies at 0
        hop_count   how many relays it took to reach the reader
        type        LESSON | WORKSHEET | ANNOUNCEMENT | CLASSROOM_MESSAGE | ALERT
        language    "hi" | "sat" | ...
        payload     arbitrary dict (text, title, materials ref, ...)
        path        node ids traversed, for the hop display
    }

Relay rules (enforced in the transports, verified in tests):
  * a node relays a message only if ttl > 0 and it has not seen the id before
  * every relay costs 1 ttl and adds 1 hop
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field

MESSAGE_TYPES = (
    "LESSON",
    "WORKSHEET",
    "ANNOUNCEMENT",
    "CLASSROOM_MESSAGE",
    "ALERT",
)

DEFAULT_TTL = 5


@dataclass
class Message:
    type: str
    language: str
    payload: dict
    sender_id: str = "teacher"
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    ttl: int = DEFAULT_TTL
    hop_count: int = 0
    path: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.type not in MESSAGE_TYPES:
            raise ValueError(f"unknown message type: {self.type}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def copy_for_relay(self, relay_id: str) -> "Message":
        """The copy that continues past the current node."""
        if self.ttl <= 0:
            raise ValueError("cannot relay a message with no TTL left")
        return Message(
            type=self.type,
            language=self.language,
            payload=self.payload,
            sender_id=self.sender_id,
            id=self.id,
            timestamp=self.timestamp,
            ttl=self.ttl - 1,
            hop_count=self.hop_count + 1,
            path=self.path + [relay_id],
        )


@dataclass
class MeshEvent:
    """One observable hop, for the UI timeline and for tests."""

    event: str  # "originated" | "delivered" | "duplicate" | "ttl_expired"
    message_id: str
    from_node: str | None
    to_node: str | None
    hop_count: int = 0
    ttl_remaining: int = 0
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
