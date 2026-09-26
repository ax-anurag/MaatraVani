"""LocalMeshSimulation — the demo transport.

A deterministic in-process model of the classroom mesh: a teacher phone and
student phones linked by Bluetooth range. Flood routing with the TTL/duplicate
rules from message.py, event by event, so the frontend can animate exactly
what a real relay would do.

This is a SIMULATION and the UI labels it as such — no real radio is
involved, and we do not claim otherwise in the demo.
"""

from __future__ import annotations

from .message import DEFAULT_TTL, Message, MeshEvent
from .transport import MeshTransport

# Default classroom topology. Teacher reaches Student A directly; A relays
# to B; the second student is 2 hops from the teacher, which is what makes
# "Received via mesh - 2 hops" a real, visible property.
DEFAULT_TOPOLOGY = {
    "teacher": ["student-a"],
    "student-a": ["teacher", "student-b"],
    "student-b": ["student-a"],
}

NODE_META = {
    "teacher": {"name": "Teacher Device", "role": "teacher"},
    "student-a": {"name": "Student Device A", "role": "student"},
    "student-b": {"name": "Student Device B", "role": "student"},
}


class SimNode:
    def __init__(self, node_id: str):
        self.id = node_id
        self.seen: set[str] = set()
        self.inbox: list[dict] = []

    def deliver(self, msg: Message) -> None:
        self.inbox.append(
            {
                **msg.to_dict(),
                "received_via": "mesh",
                "received_hop_count": msg.hop_count,
                "label": (
                    f"Received via mesh - {msg.hop_count} hop"
                    + ("s" if msg.hop_count != 1 else "")
                )
                    if msg.hop_count > 0
                    else "Sent from this device",
            }
        )


class LocalMeshSimulation(MeshTransport):
    name = "LocalMeshSimulation"
    mode = "simulation"

    def __init__(self, topology: dict | None = None, node_meta: dict | None = None):
        self.topology = topology or DEFAULT_TOPOLOGY
        self.meta = node_meta or NODE_META
        self.nodes_map = {nid: SimNode(nid) for nid in self.topology}
        self.label = "DEMO / SIMULATION MODE"

    # -- MeshTransport ---------------------------------------------------

    def describe(self) -> dict:
        return {
            "name": self.name,
            "mode": self.mode,
            "label": self.label,
            "available": True,
            "reason": "In-process simulation of the classroom Bluetooth mesh.",
            "node_count": len(self.nodes_map),
        }

    def nodes(self) -> list[dict]:
        return [
            {
                "id": nid,
                **self.meta.get(nid, {"name": nid, "role": "student"}),
                "neighbors": self.topology[nid],
                "inbox_size": len(self.nodes_map[nid].inbox),
            }
            for nid in self.topology
        ]

    def inbox(self, node_id: str) -> list[dict]:
        node = self.nodes_map.get(node_id)
        return list(node.inbox) if node else []

    def reset(self) -> None:
        """Forget seen-ids (fresh radio session)."""
        for node in self.nodes_map.values():
            node.seen.clear()
            node.inbox.clear()

    def broadcast(self, message: Message, origin_id: str) -> list[MeshEvent]:
        if origin_id not in self.nodes_map:
            raise ValueError(f"unknown node: {origin_id}")
        events: list[MeshEvent] = []
        origin = self.nodes_map[origin_id]
        origin.seen.add(message.id)
        origin.deliver(message)
        events.append(
            MeshEvent(
                event="originated",
                message_id=message.id,
                from_node=None,
                to_node=origin_id,
                hop_count=0,
                ttl_remaining=message.ttl,
            )
        )

        # Breadth-first flood, one hop per level, honouring TTL and seen-ids.
        frontier = [(origin_id, message)]
        while frontier:
            next_frontier = []
            for current_id, msg in frontier:
                for neighbor_id in self.topology.get(current_id, []):
                    neighbor = self.nodes_map[neighbor_id]
                    if msg.id in neighbor.seen:
                        events.append(
                            MeshEvent(
                                event="duplicate",
                                message_id=msg.id,
                                from_node=current_id,
                                to_node=neighbor_id,
                                hop_count=msg.hop_count,
                                detail="duplicate suppressed (already seen)",
                            )
                        )
                        continue
                    if msg.ttl <= 0:
                        events.append(
                            MeshEvent(
                                event="ttl_expired",
                                message_id=msg.id,
                                from_node=current_id,
                                to_node=neighbor_id,
                                hop_count=msg.hop_count,
                                detail="dropped: TTL exhausted",
                            )
                        )
                        continue
                    neighbor.seen.add(msg.id)
                    relayed = msg.copy_for_relay(neighbor_id)
                    neighbor.deliver(relayed)
                    events.append(
                        MeshEvent(
                            event="delivered",
                            message_id=msg.id,
                            from_node=current_id,
                            to_node=neighbor_id,
                            hop_count=relayed.hop_count,
                            ttl_remaining=relayed.ttl,
                        )
                    )
                    if relayed.ttl > 0:
                        next_frontier.append((neighbor_id, relayed))
            frontier = next_frontier
        return events
