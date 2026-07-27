"""Discovery via the SEC's complete CIK company-name registry (keyless, official).

`cik-lookup-data.txt` lists EVERY entity that ever registered with the SEC —
name + CIK, one per line. Grepping it for family-office names yields firms that
are, by construction, provable legal entities with a federal identifier: the
existence gate is satisfied at discovery time, and enrichment can pull their
official phone/address (submissions JSON) and 13F value where filed.

This became the anchor source after the existence gate exposed that
news-discovered names couldn't prove they exist (see DECISIONS.md). SPV series
entries ("BETTY LABS SPV, A SERIES OF LAMBETH FAMILY OFFICE LLC") are collapsed
to their parent family office — the SPV proves the parent runs live deals.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from pipeline.discovery.base import DiscoverySource, register
from pipeline.schema import CandidateFirm

LOOKUP_URL = "https://www.sec.gov/Archives/edgar/cik-lookup-data.txt"
LOCAL = Path("data/raw/cik-lookup-data.txt")

PATTERNS = ("FAMILY OFFICE", "SINGLE FAMILY OFFICE", "FAMILY OFFICES")
# entities that merely sell TO family offices / funds named after the phrase
NOISE = ("PORTFOLIO", "FUND", "INSTITUTE", "RESEARCH", "SERVICES /ADV",
         "EXCHANGE", "SUMMIT", "ASSOCIATION", "NETWORK", "CONFERENCE")
SPV_RE = re.compile(r"A SERIES OF\s+(.+?FAMILY OFFICE[S]?(?:\s+LLC|\s+LP|\s+INC\.?)?)\s*$",
                    re.I)


@register
class CikRegistry(DiscoverySource):
    name = "SEC CIK registry (entity names)"
    job = "discovery + existence proof (federal entity record)"

    def _ensure_file(self) -> bool:
        if LOCAL.exists() and LOCAL.stat().st_size > 1_000_000:
            return True
        try:
            LOCAL.parent.mkdir(parents=True, exist_ok=True)
            r = self.get(LOOKUP_URL, stream=True, timeout=180)
            with open(LOCAL, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            return True
        except Exception as e:
            print(f"[{self.name}] download failed: {e}")
            return False

    def discover(self, limit: int = 200) -> List[CandidateFirm]:
        if not self._ensure_file():
            return []
        out: List[CandidateFirm] = []
        seen = set()
        for line in LOCAL.read_text(encoding="latin-1").splitlines():
            up = line.upper()
            if not any(p in up for p in PATTERNS):
                continue
            if any(nz in up for nz in NOISE):
                continue
            # "NAME:CIK:" — name may itself contain colons rarely; CIK is the
            # last numeric field.
            m = re.match(r"^(.*):(\d{10}):\s*$", line.strip())
            if not m:
                continue
            raw_name, cik = m.group(1).strip(), m.group(2)
            # collapse SPV series to the parent family office
            spv = SPV_RE.search(raw_name)
            if spv:
                raw_name = spv.group(1).strip().title()
            else:
                raw_name = re.sub(r"\s+/ADV\s*$", "", raw_name).strip()
                raw_name = raw_name.title()
            key = raw_name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(CandidateFirm(
                firm_name=raw_name,
                discovery_source=self.name,
                cik=cik,
            ))
            if len(out) >= limit:
                break
        print(f"[{self.name}] {len(out)} registry-proven candidates")
        return out
