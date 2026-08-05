"""Bing redirect decoding — the fix that let the browser layer find any website.

Bing wraps every organic result in `bing.com/ck/a?...&u=a1<base64url>`; the naive
host check saw `bing.com` and rejected all of them, so find_website always
returned None. _debing unwraps the real destination."""
import base64

from pipeline.enrichment.render import _debing


def _wrap(url: str) -> str:
    b64 = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    return f"https://www.bing.com/ck/a?!&&p=abc&u=a1{b64}&ntb=1"


def test_decodes_bing_redirect_to_real_url():
    assert _debing(_wrap("https://www.walmart.com/")) == "https://www.walmart.com/"
    assert _debing(_wrap("https://acme-family-office.com/team")) == \
        "https://acme-family-office.com/team"


def test_non_bing_href_passes_through():
    assert _debing("https://acme.com/x") == "https://acme.com/x"


def test_bing_href_without_u_param_passes_through():
    assert _debing("https://www.bing.com/search?q=x") == "https://www.bing.com/search?q=x"


def test_malformed_base64_does_not_crash():
    bad = "https://www.bing.com/ck/a?u=a1!!!notbase64!!!"
    assert _debing(bad) == bad          # falls back to the original href
