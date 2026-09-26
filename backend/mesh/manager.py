"""MeshManager — one object for the API layer to talk to.

Owns the simulation, the (optional) BLE transport, the append-only message
log, and the subscriber list the WebSocket endpoint pushes events to.
"""

from __future__ import annotations

import json
import threading

from .. import config
from .ble import BleakMeshTransport
from .message import MESSAGE_TYPES, Message, MeshEvent
from .simulation import LocalMeshSimulation


class MeshManager:
    def __init__(self, log_path=None):
        self.simulation = LocalMeshSimulation()
        self.ble = BleakMeshTransport()
        self.active = self.simulation  # simulation is the default transport
        self.log_path = log_path or (config.GENERATED_DIR / "mesh_log.jsonl")
        self._lock = threading.Lock()
        self._subscribers: list = []
        self._events: list[dict] = []

    # -- status -----------------------------------------------------------

    def describe(self) -> dict:
        return {
            "active_transport": self.active.describe(),
            "transports": [self.simulation.describe(), self.ble.describe()],
            "simulation_banner": (
                "DEMO / SIMULATION MODE - no radio hardware involved"
                if self.active.mode == "simulation"
                else None
            ),
        }

    def nodes(self) -> list[dict]:
        return self.simulation.nodes()

    def inbox(self, node_id: str) -> list[dict]:
        return self.simulation.inbox(node_id)

    def events(self) -> list[dict]:
        with self._lock:
            return list(self._events)

    def reset(self) -> None:
        self.simulation.reset()
        with self._lock:
            self._events.clear()

    # -- sending ----------------------------------------------------------

    def send(self, sender_id: str, type_: str, language: str, payload: dict,
             ttl: int | None = None) -> dict:
        if type_ not in MESSAGE_TYPES:
            raise ValueError(f"unknown message type: {type_}")
        if sender_id not in ("teacher", "student-a", "student-b"):
            raise ValueError(f"unknown node: {sender_id}")
        msg = Message(
            type=type_,
            language=language,
            payload=payload,
            sender_id=sender_id,
            ttl=ttl if ttl is not None else 5,
            path=[sender_id],
        )
        events = self.simulation.broadcast(msg, sender_id)
        with self._lock:
            for ev in events:
                self._events.append(ev.to_dict())
        self._log(msg, events)
        self._notify(events)
        return {
            "message": msg.to_dict(),
            "events": [e.to_dict() for e in events],
        }

    # -- plumbing ----------------------------------------------------------

    def _log(self, msg: Message, events: list[MeshEvent]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"message": msg.to_dict(), "events": [e.to_dict() for e in events]}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)

    def _notify(self, events: list[MeshEvent]) -> None:
        for cb in self._subscribers:
            try:
                cb(events)
            except Exception:
                pass  # a slow UI listener must never break relaying


_manager: MeshManager | None = None


def manager() -> MeshManager:
    global _manager
    if _manager is None:
        _manager = MeshManager()
    return _manager
