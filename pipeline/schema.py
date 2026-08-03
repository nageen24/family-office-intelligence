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

from pipeline.ontology import FirmCategory, Status, RouteType


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
    # Stage-2 ontology (S2): the one honest status word for THIS value, and, for
    # contact cells, whose route it is. Same label on every surface; never upgraded.
    status: Optional[Status] = None       # verified / inferred / unresolved / quarantined
    route: Optional[RouteType] = None     # personal vs firm-level (contact cells only)
    # audit-only (S5): NEVER shipped to a customer surface. When a value fails a
    # check it is withheld (value -> None) but preserved here so we can prove
    # exactly what was caught and why.
    quarantined_value: Optional[str] = None
    quarantined_reason: Optional[str] = None

    def is_blank(self) -> bool:
        return self.value in (None, "", "N/A")

    def quarantine(self, reason: str) -> "Cell":
        """Withhold a value that FAILED a check (S5): remove it from every
        customer surface, keep the original in audit-only fields, stamp
        status=quarantined. Validation withholds, it does not merely tag."""
        if self.value is not None:
            self.quarantined_value = self.value
        self.quarantined_reason = reason
        self.method = f"quarantined — {reason}"
        self.value = None
        self.status = Status.QUARANTINED
        self.confidence = None
        self.epistemic = None
        return self

    def mark_unresolved(self) -> "Cell":
        """An honest blank: a value that was never found (not a failed check)."""
        self.value = None
        self.status = Status.UNRESOLVED
        return self


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

    # --- S1 ontology (Stage 2): category + the three SEPARATE proofs ---
    # `category` is the narrowest accurate label from pipeline/ontology.py.
    # Each proof stores the exact own-source sentence (Proof B/C) plus where it
    # came from, so code can re-verify the quote literally exists (quote_present).
    category: Optional[FirmCategory] = None
    proof_exists: Optional[str] = None            # Proof A basis (CIK/site/location/principal)
    proof_function_source: Optional[str] = None   # Proof B: URL/filing the quote is from
    proof_function_quote: Optional[str] = None    # Proof B: exact own-source FO-function sentence
    proof_type_quote: Optional[str] = None        # Proof C: exact sentence proving SFO/MFO
    sec_family_office_exemption: Optional[bool] = None  # Proof B: claimed SEC family-office exemption (single-family)
    ria_adviser_evidence: Optional[str] = None    # affirmative general-adviser evidence -> RIA-nonqualifying
    entity_coherent: Optional[bool] = None        # S6 whole-record resolution result
    counts_toward_500: Optional[bool] = None      # S3 inclusion-floor result
    is_commercial: Optional[bool] = None          # S3 commercial-standard result

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

    def to_flat_row(self, audit: bool = False) -> dict:
        """Flatten to a single CSV row with one column per cell + provenance.

        Default is the CUSTOMER surface: quarantined values appear blank and the
        audit-only columns are omitted. Pass audit=True for an internal export
        that also carries the withheld value + reason.
        """
        row: dict = {
            "firm_name": self.firm_name,
            "discovery_source": self.discovery_source,
            "firm_type": self.firm_type.value if isinstance(self.firm_type, FirmType) else self.firm_type,
            "type_evidence": self.type_evidence,
            "category": self.category.value if isinstance(self.category, FirmCategory) else self.category,
            "proof_exists": self.proof_exists,
            "proof_function_source": self.proof_function_source,
            "proof_function_quote": self.proof_function_quote,
            "proof_type_quote": self.proof_type_quote,
            "entity_coherent": self.entity_coherent,
            "counts_toward_500": self.counts_toward_500,
            "is_commercial": self.is_commercial,
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
            row[f"{name}__status"] = c.status.value if isinstance(c.status, Status) else c.status
            row[f"{name}__route"] = c.route.value if isinstance(c.route, RouteType) else c.route
            if audit:
                row[f"{name}__quarantined_value"] = c.quarantined_value
                row[f"{name}__quarantined_reason"] = c.quarantined_reason
        return row
