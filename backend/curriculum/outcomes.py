"""FLN outcome catalog - loads content/lessons/fln_outcomes.json."""

from __future__ import annotations

import json

from .. import config
from ..engines.base import ModelUnavailable


class OutcomeCatalog:
    def __init__(self, path=None):
        self.path = path or config.OUTCOMES_PATH
        self.data = None
        self._load()

    def _load(self):
        if not self.path.exists():
            raise ModelUnavailable(
                f"{self.path.name} not found - run scripts/emit_content.py"
            )
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def meta(self) -> dict:
        return self.data["meta"]

    def grades(self) -> list[str]:
        return self.meta["grades"]

    def subjects(self) -> list[str]:
        return self.meta["subjects"]

    def topics(self) -> list[str]:
        return self.meta["topics"]

    def outcomes_for(self, grade: str, subject: str | None = None,
                     topic: str | None = None) -> list[dict]:
        results = []
        for o in self.data["outcomes"]:
            if o["grade"] != grade:
                continue
            if subject and o["subject"] != subject:
                continue
            if topic and topic.lower() not in [t.lower() for t in o["topics"]]:
                continue
            results.append(o)
        return results


_instance: OutcomeCatalog | None = None


def catalog() -> OutcomeCatalog:
    global _instance
    if _instance is None:
        _instance = OutcomeCatalog()
    return _instance
