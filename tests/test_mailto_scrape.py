"""Personal emails published only inside <a href='mailto:'> are recovered from the
raw hrefs (tag-stripping would otherwise drop them) and flow to the contact picker."""
import pipeline.enrichment.function_proof as fp
from pipeline.enrichment.contacts import same_domain_emails


class _Resp:
    def __init__(self, text):
        self.text = text
        self.headers = {"content-type": "text/html"}
        self.status_code = 200


def test_mailto_email_is_pulled_from_hrefs(monkeypatch):
    html = ('<html><body><h1>Team</h1>'
            '<p>Reach our founder:</p>'
            '<a href="mailto:jane.cedar@cedarfo.com">Email Jane</a>'
            '</body></html>')
    # first base probe + first page return the html; others 404 (None)
    calls = {"n": 0}
    def fake_get(u, timeout=8):
        calls["n"] += 1
        return _Resp(html) if calls["n"] <= 2 else None
    monkeypatch.setattr(fp, "_get", fake_get)

    text = fp.fetch_site_text("https://cedarfo.com")
    # the address itself (not just the visible 'Email Jane') is present
    assert "jane.cedar@cedarfo.com" in text
    # and the contact picker sees it as a same-domain candidate
    assert "jane.cedar@cedarfo.com" in same_domain_emails(text, "https://cedarfo.com")


def test_mailto_regex_ignores_non_mailto_text():
    assert fp._MAILTO.findall('mailto:a@b.com and plain c@d.com') == ["a@b.com"]
