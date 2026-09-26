"""Mesh tests: message rules + the simulation's relay behaviour.

These are the acceptance tests for CLAUDE.md's Module 3:
  * a message floods to every node, hop by hop
  * student B (2 hops away) receives it labelled "Received via mesh - 2 hops"
  * nodes never relay a message id they have already seen (duplicate drop)
  * every relay costs 1 TTL; the message dies at 0 (TTL expiry)
"""

import pytest

from backend.mesh.message import DEFAULT_TTL, MESSAGE_TYPES, Message
from backend.mesh.simulation import LocalMeshSimulation


def _msg(ttl=DEFAULT_TTL, **kw):
    # path defaults here instead of inline below, so a test can pass its
    # own path without the same keyword arriving twice.
    kw.setdefault("path", ["teacher"])
    return Message(
        type="CLASSROOM_MESSAGE", language="hi",
        payload={"title": "homework", "text": "कल गणित की कॉपी साथ लाईये।"},
        sender_id="teacher", ttl=ttl, **kw,
    )


# ------------------------------------------------------------- message -----

def test_message_defaults():
    m = Message(type="LESSON", language="hi", payload={})
    assert m.ttl == DEFAULT_TTL == 5
    assert m.hop_count == 0
    assert len(m.id) == 32          # uuid4 hex
    assert m.timestamp             # ISO-8601 string
    assert "LESSON" in MESSAGE_TYPES


def test_unknown_type_rejected():
    with pytest.raises(ValueError):
        Message(type="NOT_A_REAL_TYPE", language="hi", payload={})


def test_copy_for_relay_costs_ttl_and_adds_hop():
    m = _msg(ttl=3, hop_count=1, path=["teacher", "student-a"])
    relayed = m.copy_for_relay("student-b")
    assert relayed.id == m.id            # same message continues
    assert relayed.ttl == 2              # relay costs 1 TTL
    assert relayed.hop_count == 2        # and adds 1 hop
    assert relayed.path == ["teacher", "student-a", "student-b"]


def test_cannot_relay_dead_message():
    with pytest.raises(ValueError):
        _msg(ttl=0).copy_for_relay("student-a")


# --------------------------------------------------------- simulation -----

def test_flood_reaches_everyone_with_hop_labels():
    sim = LocalMeshSimulation()
    events = sim.broadcast(_msg(), "teacher")
    by_kind = {}
    for e in events:
        by_kind.setdefault(e.event, []).append(e)

    assert by_kind["originated"][0].to_node == "teacher"
    delivered = {(e.from_node, e.to_node): e for e in by_kind["delivered"]}
    assert ("teacher", "student-a") in delivered            # hop 1
    assert ("student-a", "student-b") in delivered          # hop 2

    inbox_b = sim.inbox("student-b")
    assert len(inbox_b) == 1
    assert inbox_b[0]["label"] == "Received via mesh - 2 hops"
    assert inbox_b[0]["received_hop_count"] == 2
    assert inbox_b[0]["path"] == ["teacher", "student-a", "student-b"]

    inbox_a = sim.inbox("student-a")
    assert inbox_a[0]["label"] == "Received via mesh - 1 hop"


def test_duplicates_are_suppressed_with_events():
    sim = LocalMeshSimulation()
    events = sim.broadcast(_msg(), "teacher")
    dupes = [e for e in events if e.event == "duplicate"]
    assert dupes, "a full flood must bounce back at the sender and be dropped"
    # Each node delivered exactly once:
    assert len(sim.inbox("teacher")) == 1
    assert len(sim.inbox("student-a")) == 1
    assert len(sim.inbox("student-b")) == 1


def test_ttl_one_never_reaches_two_hops_away():
    sim = LocalMeshSimulation()
    events = sim.broadcast(_msg(ttl=1), "teacher")
    assert any(e.event == "delivered" and e.to_node == "student-a" for e in events)
    assert not any(e.event == "delivered" and e.to_node == "student-b" for e in events), \
        "TTL=1 must die at the first relay"
    assert sim.inbox("student-b") == []


def test_ttl_two_reaches_student_b_and_stops():
    sim = LocalMeshSimulation()
    events = sim.broadcast(_msg(ttl=2), "teacher")
    hop2 = [e for e in events if e.event == "delivered" and e.to_node == "student-b"]
    assert hop2 and hop2[0].ttl_remaining == 0


def test_reset_clears_seen_ids_and_inboxes():
    sim = LocalMeshSimulation()
    sim.broadcast(_msg(), "teacher")
    sim.reset()
    for nid in ("teacher", "student-a", "student-b"):
        assert sim.inbox(nid) == []
    # After reset the same flood works again (fresh radio session):
    events = sim.broadcast(_msg(), "teacher")
    assert any(e.event == "delivered" and e.to_node == "student-b" for e in events)


def test_describe_admits_simulation_mode():
    d = LocalMeshSimulation().describe()
    assert d["mode"] == "simulation"
    assert "SIMULATION" in d["label"].upper(), \
        "the transport must label itself as a simulation, not a radio"


# ------------------------------------------------------------- manager -----

def test_manager_send_validates_and_logs(tmp_path, monkeypatch):
    from backend import config
    from backend.mesh import manager as manager_mod

    log = tmp_path / "mesh_log.jsonl"
    monkeypatch.setattr(manager_mod, "_manager", None)
    m = manager_mod.MeshManager(log_path=log)

    result = m.send(
        sender_id="teacher", type_="ANNOUNCEMENT", language="hi",
        payload={"text": "test"}, ttl=5,
    )
    assert result["message"]["hop_count"] == 0
    # send() hands back JSON-serializable dicts, not MeshEvent objects
    delivered = [e for e in result["events"] if e["event"] == "delivered"]
    assert any(e["to_node"] == "student-b" and e["hop_count"] == 2 for e in delivered)

    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1, "one JSONL record per send"

    with pytest.raises(ValueError):
        m.send(sender_id="teacher", type_="Bogus", language="hi", payload={})
    with pytest.raises(ValueError):
        m.send(sender_id="headmaster", type_="ALERT", language="hi", payload={})
