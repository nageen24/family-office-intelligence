"""
Shared data schema for the Family Office pipeline.

This is the single contract every discovery, enrichment, and validation
module writes against. Discovery modules produce `CandidateFirm`s; enrichment
fills them out; validation stamps provenance and decides qualification.

Design notes (see DECISIONS.md):
- Every high-value cell carries its own provenance: source, method,
  confidence, epistemic status, and as-of date. Provenance lives in
  separate columns (not JSON) so a reviewer can check a cell fast.
- firm_type is SFO / MFO / UNCONFIRMED. We never guess SFO to inflate value.
- Honest blank over fake: an unconfirmed value stays empty, never invented.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class FirmType(str, Enum):
    SFO = "SFO"                # single-family office
    MFO = "MFO"                # multi-family office
    UNCONFIRMED = "Unconfirmed"


class Confidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Epistemic(str, Enum):
    FACT = "fact"              # directly stated by an authoritative source
    INFERENCE = "inference"    # reasoned from evidence, not stated outright
    SPECULATION = "speculation"


@dataclass
class Cell:
    """A single high-value value plus the basis for trusting it.

    An empty `value` with method='could not verify' is an honest blank.
    """
    value: Optional[str] = None
    source: Optional[str] = None          # exact URL / filing / place
    method: Optional[str] = None          # how it was confirmed
    confidence: Optional[Confidence] = None
    epistemic: Optional[Epistemic] = None
    asof_date: Optional[str] = None       # YYYY-MM-DD when confirmed / as-of

    def is_blank(self) -> bool:
        return self.value in (None, "", "N/A")


@dataclass
class CandidateFirm:
    """A firm as it moves through the pipeline.

    Discovery sets firm_name + discovery_source (+ whatever it can).
    Enrichment fills the Cells. Validation sets firm_type, type_evidence,
    reachability_score, record_status.
    """
    # --- identity / discovery ---
    firm_name: str
    discovery_source: str                 # which source class found it
    firm_type: FirmType = FirmType.UNCONFIRMED
    type_evidence: Optional[str] = None   # what proves it's an FO / its type
    website: Optional[str] = None
    hq_location: Optional[str] = None
    corporate_linkedin: Optional[str] = None
    cik: Optional[str] = None              # SEC CIK, when discovered via EDGAR

    # --- entity intelligence (high-value cells) ---
    aum: Cell = field(default_factory=Cell)
    investing_thesis: Cell = field(default_factory=Cell)
    mandate: Cell = field(default_factory=Cell)
    background: Cell = field(default_factory=Cell)

    # --- principal / decision-maker (highest value) ---
    principal_name: Cell = field(default_factory=Cell)
    principal_title: Cell = field(default_factory=Cell)
    principal_linkedin: Cell = field(default_factory=Cell)
    principal_email: Cell = field(default_factory=Cell)
    principal_phone: Cell = field(default_factory=Cell)

    # --- recent dated signals ("why now") ---
    recent_signal: Cell = field(default_factory=Cell)
    signal_date: Optional[str] = None
    signal_type: Optional[str] = None     # investment / hire / fund / news

    # --- product scoring / status ---
    reachability_score: Optional[int] = None   # 0-100
    record_status: Optional[str] = None        # Qualified / Rejected / Review

    # --- audit ---
    rejection_reason: Optional[str] = None     # set when disqualified

    def to_flat_row(self) -> dict:
        """Flatten to a single CSV row with one column per cell + provenance."""
        row: dict = {
            "firm_name": self.firm_name,
            "discovery_source": self.discovery_source,
            "firm_type": self.firm_type.value if isinstance(self.firm_type, FirmType) else self.firm_type,
            "type_evidence": self.type_evidence,
            "website": self.website,
            "hq_location": self.hq_location,
            "corporate_linkedin": self.corporate_linkedin,
            "signal_date": self.signal_date,
            "signal_type": self.signal_type,
            "reachability_score": self.reachability_score,
            "record_status": self.record_status,
            "rejection_reason": self.rejection_reason,
        }
        cell_fields = [
            "aum", "investing_thesis", "mandate", "background",
            "principal_name", "principal_title", "principal_linkedin",
            "principal_email", "principal_phone", "recent_signal",
        ]
        for name in cell_fields:
            c: Cell = getattr(self, name)
            row[name] = c.value
            row[f"{name}__source"] = c.source
            row[f"{name}__method"] = c.method
            row[f"{name}__confidence"] = c.confidence.value if isinstance(c.confidence, Confidence) else c.confidence
            row[f"{name}__epistemic"] = c.epistemic.value if isinstance(c.epistemic, Epistemic) else c.epistemic
            row[f"{name}__asof"] = c.asof_date
        return row
