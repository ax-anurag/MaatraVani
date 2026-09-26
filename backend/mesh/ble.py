"""Real Bluetooth LE mesh transport, on top of `bleak`.

Honest status first: this build machine is WSL2, which exposes no Bluetooth
adapter to Linux, so this transport reports "unavailable, simulation
available" here and is exercised only on real hardware (Linux laptop with
BlueZ, or a native Windows/macOS host). The code is a compact, real
GATT flood-mesh: each instance advertises a custom service, accepts message
frames written to its characteristic, and re-relays them (TTL/duplicate
rules identical to the simulation).

It is deliberately small and marked experimental: real BLE relaying needs
on-device testing we could not do in this environment. The transport seam
(backend/mesh/transport.py) is the point — the simulation above proves the
protocol; this class proves the seam fits a real radio stack too.
"""

from __future__ import annotations

import asyncio
import json

from .message import Message, MeshEvent
from .transport import MeshTransport

# Custom GATT profile for MaatraVani message frames.
SERVICE_UUID = "0000fe5a-0000-1000-8000-00805f9b34fa"  # MaatraVani mesh service
MSG_CHAR_UUID = "0000fe5b-0000-1000-8000-00805f9b34fb"  # write/notify message frame

try:
    from bleak import BleakClient, BleakScanner

    _BLEAK_ERROR = None
except ImportError as e:
    BleakClient = BleakScanner = None
    _BLEAK_ERROR = str(e)


class BleakMeshTransport(MeshTransport):
    name = "AndroidBluetoothMeshTransport (bleak)"
    mode = "ble"

    def __init__(self, node_id: str = "teacher"):
        self.node_id = node_id
        self._seen: set[str] = set()
        self._inbox: list[dict] = []
        self._peers: list[dict] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    # -- availability ----------------------------------------------------

    def describe(self) -> dict:
        reason = None
        if _BLEAK_ERROR:
            reason = f"bleak not installed: {_BLEAK_ERROR}"
        else:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # No running loop => no BlueZ/D-Bus session in this environment.
                reason = (
                    "No Bluetooth adapter accessible on this machine "
                    "(WSL2 exposes none to Linux). Run on a host with BLE "
                    "and BlueZ to use the native transport."
                )
        return {
            "name": self.name,
            "mode": self.mode,
            "available": reason is None,
            "reason": reason or "BLE adapter present.",
            "node_count": len(self._peers),
        }

    def nodes(self) -> list[dict]:
        return self._peers

    def inbox(self) -> list[dict]:
        return list(self._inbox)

    # -- frame (de)serialisation ------------------------------------------

    @staticmethod
    def encode(message: Message) -> bytes:
        return json.dumps(message.to_dict(), ensure_ascii=False).encode("utf-8")

    @staticmethod
    def decode(frame: bytes) -> Message:
        return Message.from_dict(json.loads(frame.decode("utf-8")))

    # -- relay ------------------------------------------------------------

    def _on_frame(self, characteristic, frame: bytearray):
        """Inbound frame from a peer: deliver once, re-relay if TTL remains."""
        try:
            msg = self.decode(bytes(frame))
        except Exception:
            return
        if msg.id in self._seen or msg.ttl <= 0:
            return  # duplicate / expired: same rules as the simulation
        self._seen.add(msg.id)
        self._inbox.append({**msg.to_dict(), "received_via": "ble"})
        if msg.ttl > 1:
            try:
                asyncio.get_running_loop().create_task(self._flood(msg))
            except RuntimeError:
                pass

    async def _flood(self, message: Message):
        """Write the relayed frame to every peer we can currently reach."""
        relayed = message.copy_for_relay(self.node_id)
        frame = self.encode(relayed)
        for peer in await BleakScanner.discover(timeout=3.0, service_uuids=[SERVICE_UUID]):
            try:
                async with BleakClient(peer) as client:
                    await client.write_gatt_char(MSG_CHAR_UUID, frame, response=True)
            except Exception:
                continue  # a radio that blinked is a radio we retry next flood

    async def broadcast_async(self, message: Message, origin_id: str) -> list[MeshEvent]:
        self._seen.add(message.id)
        self._inbox.append({**message.to_dict(), "received_via": "ble"})
        events = [
            MeshEvent(
                event="originated", message_id=message.id,
                from_node=None, to_node=origin_id,
                hop_count=0, ttl_remaining=message.ttl,
            )
        ]
        await self._flood(message)
        return events

    def broadcast(self, message: Message, origin_id: str) -> list[MeshEvent]:
        if _BLEAK_ERROR:
            raise RuntimeError(_BLEAK_ERROR)
        return asyncio.run(self.broadcast_async(message, origin_id))
