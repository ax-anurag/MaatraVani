"""MeshTransport: the seam where real radio replaces the simulation.

Any transport implements this interface. The MeshManager and the UI never
assume which one is live — they read describe() and show the truth,
including the "DEMO / SIMULATION MODE" banner when only the simulation is
available on the machine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .message import Message, MeshEvent


class MeshTransport(ABC):
    name: str = "transport"
    mode: str = "simulation"  # "simulation" | "ble"

    @abstractmethod
    def describe(self) -> dict:
        """{"name", "mode", "available", "reason"} — shown verbatim in the UI."""

    @abstractmethod
    def nodes(self) -> list[dict]:
        """Peer devices this transport can see."""

    @abstractmethod
    def broadcast(self, message: Message, origin_id: str) -> list[MeshEvent]:
        """Push a message out; return the relay events (possibly async later)."""

    def stop(self) -> None:
        """Release radio resources, if any were held."""
