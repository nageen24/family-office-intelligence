"""Hunter.io + Snov.io (free tiers) — principal-email PROVIDER sources.

Same standing as Apollo (see apollo.py): a provider fills the personal-email gap
but does NOT self-certify. The rules here:

- NEVER pattern-built: a Hunter result is accepted only when Hunter saw the
  address in public sources or its own verifier says "valid" — a bare
  most-likely-pattern guess (no sources, unverified) is discarded. A Snov result
  is accepted only with emailStatus "valid".
- OUR validation still runs: the address must be on the firm's own domain and
  route as PERSONAL for the named principal (ontology.email_route) before we
  keep it. Then validate_all's MX + SMTP check decides the final status — a
  provider email enters as `inferred` and becomes `verified` only if OUR
  mailbox probe confirms it. It counts toward the 200-verified-email gate only
  then; a free-tier shortfall is documented, never faked.
- CREDIT DISCIPLINE: free tiers are tiny (Hunter ~25 searches/mo). A committed
  monthly counter (shared across scheduled runs, like Serper's daily one) stops
  quota burn, and the strongest records spend first.

Graceful no-op without HUNTER_API_KEY / SNOV_CLIENT_ID+SNOV_CLIENT_SECRET.
"""
from __future__ import annotations

import json
import os
from datetime import date
from typing import Optional

from pipeline.schema import CandidateFirm, Cell, Epistemic, Confidence
from pipeline.ontology import Status, RouteType, email_route

QUOTA_PATH = os.path.join("data", "state", "email_quota.json")


def _domain(url: str) -> Optional[str]:
    from urllib.parse import urlparse
    if not url:
        return None
    host = urlparse(url if "//" in url else "//" + url).netloc.lower()
    return host[4:] if host.startswith("www.") else host or None


# --- committed monthly quota (spend guard shared across scheduled runs) --------
def _load_quota(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def monthly_quota_ok(provider: str, limit: int, path: str = QUOTA_PATH) -> bool:
    q = _load_quota(path)
    month = date.today().isoformat()[:7]
    if q.get("month") != month:
        return True                          # new month resets every counter
    return q.get(provider, 0) < limit


def bump_quota(provider: str, path: str = QUOTA_PATH) -> None:
    month = date.today().isoformat()[:7]
    q = _load_quota(path)
    if q.get("month") != month:
        q = {"month": month}
    q[provider] = q.get(provider, 0) + 1
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(q, f)


# --- acceptance: provider evidence + our own routing rules ---------------------
def _accept(firm: CandidateFirm, email: str, source: str, method: str) -> bool:
    """Domain must be the firm's own; address must route PERSONAL for the named
    principal. Only then does the provider email land on the record."""
    dom = _domain(firm.website)
    if not (email and dom and email.lower().endswith("@" + dom)):
        return False
    if email_route(email, firm.principal_name.value or "") is not RouteType.PERSONAL:
        return False
    firm.principal_email = Cell(
        value=email, source=source,
        method=method + "; name+domain matched by us; NOT mailbox-verified "
                        "(provider-returned; our own SMTP check decides)",
        epistemic=Epistemic.INFERENCE, confidence=Confidence.MEDIUM,
        status=Status.INFERRED, route=RouteType.PERSONAL)
    return True


def enrich_hunter(firm: CandidateFirm, client: "HunterClient") -> bool:
    """Hunter email-finder for the named principal. Accepts only source-backed or
    Hunter-verified results — a pure pattern prediction is discarded."""
    pn = (firm.principal_name.value or "").split()
    dom = _domain(firm.website)
    if len(pn) < 2 or not dom:
        return False
    data = client.find(domain=dom, first_name=pn[0], last_name=pn[-1])
    if not data:
        return False
    email = (data.get("email") or "").strip()
    sources = data.get("sources") or []
    vstatus = ((data.get("verification") or {}).get("status") or "").lower()
    if not email or (not sources and vstatus != "valid"):
        return False                          # pattern-built guess -> refused
    basis = (f"seen in {len(sources)} public source(s)" if sources
             else "Hunter verifier reports 'valid'")
    return _accept(firm, email, "Hunter.io",
                   f"provider-returned by Hunter.io email-finder ({basis}, "
                   f"score {data.get('score')})")


def enrich_snov(firm: CandidateFirm, client: "SnovClient") -> bool:
    """Snov email-by-name for the named principal. Accepts only emailStatus
    'valid' — 'unknown'/'not_valid' results are discarded."""
    pn = (firm.principal_name.value or "").split()
    dom = _domain(firm.website)
    if len(pn) < 2 or not dom:
        return False
    for item in client.find(domain=dom, first_name=pn[0], last_name=pn[-1]) or []:
        if (item.get("emailStatus") or "").lower() == "valid":
            if _accept(firm, (item.get("email") or "").strip(), "Snov.io",
                       "provider-returned by Snov.io email-by-name "
                       "(Snov status 'valid')"):
                return True
    return False


def enrich_email_finders(firm: CandidateFirm, hunter: "HunterClient",
                         snov: "SnovClient") -> bool:
    """Try Hunter first (source-backed evidence), then Snov. First accept wins."""
    if not firm.principal_email.is_blank():
        return False
    if hunter.enabled() and enrich_hunter(firm, hunter):
        return True
    return bool(snov.enabled() and enrich_snov(firm, snov))


# --- live clients (injectable in tests) ----------------------------------------
class HunterClient:
    """Hunter.io email-finder (free tier ~25 searches/mo). Needs HUNTER_API_KEY."""

    ENDPOINT = "https://api.hunter.io/v2/email-finder"

    def __init__(self, key: Optional[str] = None, quota_path: str = QUOTA_PATH,
                 monthly_limit: Optional[int] = None):
        self.key = key or os.getenv("HUNTER_API_KEY")
        self.quota_path = quota_path
        self.limit = monthly_limit or int(os.getenv("HUNTER_MONTHLY_LIMIT", "25"))

    def enabled(self) -> bool:
        return bool(self.key)

    def find(self, domain: str, first_name: str, last_name: str) -> Optional[dict]:
        if not self.enabled() or not monthly_quota_ok("hunter", self.limit,
                                                      self.quota_path):
            return None
        import requests
        try:
            bump_quota("hunter", self.quota_path)
            r = requests.get(self.ENDPOINT, timeout=15, params={
                "domain": domain, "first_name": first_name,
                "last_name": last_name, "api_key": self.key})
            return (r.json() or {}).get("data") if r.ok else None
        except requests.RequestException:
            return None


class SnovClient:
    """Snov.io email-by-name (free-tier credits). Needs SNOV_CLIENT_ID + SECRET."""

    TOKEN_URL = "https://api.snov.io/v1/oauth/access_token"
    FIND_URL = "https://api.snov.io/restapi/get-emails-from-names"

    def __init__(self, client_id: Optional[str] = None,
                 client_secret: Optional[str] = None,
                 quota_path: str = QUOTA_PATH,
                 monthly_limit: Optional[int] = None):
        self.client_id = client_id or os.getenv("SNOV_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SNOV_CLIENT_SECRET")
        self.quota_path = quota_path
        self.limit = monthly_limit or int(os.getenv("SNOV_MONTHLY_LIMIT", "50"))
        self._token: Optional[str] = None

    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _access_token(self) -> Optional[str]:
        if self._token:
            return self._token
        import requests
        try:
            r = requests.post(self.TOKEN_URL, timeout=15, json={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret})
            self._token = (r.json() or {}).get("access_token") if r.ok else None
        except requests.RequestException:
            self._token = None
        return self._token

    def find(self, domain: str, first_name: str, last_name: str) -> list[dict]:
        if not self.enabled() or not monthly_quota_ok("snov", self.limit,
                                                      self.quota_path):
            return []
        token = self._access_token()
        if not token:
            return []
        import requests
        try:
            bump_quota("snov", self.quota_path)
            r = requests.post(self.FIND_URL, timeout=20, json={
                "access_token": token, "domain": domain,
                "firstName": first_name, "lastName": last_name})
            if not r.ok:
                return []
            data = (r.json() or {}).get("data") or {}
            return data.get("emails") or []
        except requests.RequestException:
            return []
