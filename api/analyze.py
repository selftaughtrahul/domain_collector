from fastapi import APIRouter, Query
from collectors.intelligence import full_domain_analysis, _classify_b2b_b2c, _guess_niche
import httpx
from bs4 import BeautifulSoup
from utils.config import settings

router = APIRouter(tags=["Analyze"])


@router.get("/analyze", summary="Full domain intelligence — one call, all data")
async def analyze_domain(
    domain: str = Query(..., description="Domain to analyse, e.g. google.com or https://example.com"),
):
    """
    Takes any domain input (with or without http/https/www) and returns:

    - `domain`, `tld`, `website`, `language`, `country`
    - `niche` — auto-detected industry category
    - `b2b_b2c` — B2B / B2C / UNKNOWN classification
    - `email`, `phone` — first found contact info
    - `contacts` — full list of emails and phones
    - `do_follow_links`, `no_follow_links` — link counts
    - `social` — detected social media profiles
    - `technologies` — CMS, frameworks, analytics tools
    - `seo` — title, description, canonical, Open Graph, word count, SEO score 0–100
    - `security` — HTTPS, HSTS, CSP, X-Frame-Options etc.
    - `dns` — A, AAAA, MX, NS, TXT, CNAME, SOA records
    - `content_pages` — has_blog, has_pricing, has_contact etc.
    - `marketing_score` — deterministic score 0–100 breakdown
    - `errors` — per-collector error list (partial results still returned)
    """
    return await full_domain_analysis(domain)


@router.get("/classify", summary="Classify domain as B2B or B2C")
async def classify_domain(
    domain: str = Query(..., description="Domain name, e.g. google.com"),
):
    """
    Fast classification endpoint.
    Fetches the homepage of the domain and returns:
    - `domain`
    - `b2b_b2c` — B2B / B2C / UNKNOWN
    - `niche` — detected industry (casino, crypto, finance, tech, etc.)
    - `confidence_signals` — the keywords/signals that drove the classification
    """
    domain = domain.strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")
    
    result = {
        "domain": domain,
        "b2b_b2c": "UNKNOWN",
        "niche": None,
        "confidence_signals": {},
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient(
            timeout=settings.REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": settings.USER_AGENT},
        ) as client:
            for scheme in ("https", "http"):
                try:
                    resp = await client.get(f"{scheme}://{domain}")
                    break
                except Exception:
                    continue
            else:
                raise RuntimeError("Could not reach domain")

        html = resp.content[:settings.MAX_RESPONSE_SIZE].decode(
            resp.encoding or "utf-8", errors="replace"
        )
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)

        # Detect niche
        result["niche"] = _guess_niche(text)

        # Classify B2B / B2C with signal counts
        import re
        b2b_pattern = r"\benterprise\b|\bsolution[s]?\b|\bpartner[s]?\b|\bclient[s]?\b|b2b|\bbusiness\b|\bteam[s]?\b|\bapi\b|\bsaas\b"
        b2c_pattern = r"\bshop\b|\bstore\b|\bprice\b|\bbuy\b|\bpurchase\b|\bsale\b|\bcustomer\b|b2c"

        b2b_matches = re.findall(b2b_pattern, text[:50000], re.I)
        b2c_matches = re.findall(b2c_pattern, text[:50000], re.I)

        b2b_count = len(b2b_matches)
        b2c_count = len(b2c_matches)

        result["confidence_signals"] = {
            "b2b_keyword_count": b2b_count,
            "b2c_keyword_count": b2c_count,
            "top_b2b_signals": list(set(w.lower() for w in b2b_matches))[:10],
            "top_b2c_signals": list(set(w.lower() for w in b2c_matches))[:10],
        }

        if b2c_count > b2b_count:
            result["b2b_b2c"] = "B2C"
        elif b2b_count > b2c_count:
            result["b2b_b2c"] = "B2B"
        else:
            result["b2b_b2c"] = "UNKNOWN"

    except Exception as exc:
        result["error"] = str(exc)

    return result
