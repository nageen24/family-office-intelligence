"""Base class + registry for discovery sources.

Each discovery source has ONE job: find firms that *might* be family offices
and tag where it found them. It must NOT assert a firm's type — that is the
validation stage's job (Rule 2). Keeping discovery and proof separate is a
core requirement (see DECISIONS.md, sourcing strategy).
"""
from __future__ import annotations

import time
from typing import List

import requests

from pipeline.schema import CandidateFirm

# A polite, identifiable UA. SEC and others require a real UA with contact.
USER_AGENT = "family-office-research/0.1 (contact: nageenabid0624@gmail.com)"

_REGISTRY: list = []


def register(cls):
    _REGISTRY.append(cls)
    return cls


def all_sources():
    return [cls() for cls in _REGISTRY]


class DiscoverySource:
    """Subclass and implement discover(). Set `name` and `job`."""

    name: str = "base"
    # 'discovery' = good for finding firms; some sources also help prove facts,
    # but discovery modules only claim the discovery job here.
    job: str = "discovery"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def get(self, url, **kw):
        kw.setdefault("timeout", 30)
        r = self.session.get(url, **kw)
        r.raise_for_status()
        time.sleep(0.3)  # be polite; avoid hammering free endpoints
        return r

    def discover(self, limit: int = 40) -> List[CandidateFirm]:
        raise NotImplementedError
