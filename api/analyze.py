from fastapi import APIRouter, Query
from collectors.intelligence import (
    full_domain_analysis,
    _guess_niche,
)
import httpx
from utils.config import settings
from .helper import analyzer

router = APIRouter(tags=["Analyze Domains"])


@router.get("/analyze", summary="Full domain intelligence — one call, all data")
async def analyze_domain(
    domain: str = Query(
        ..., description="Domain to analyse, e.g. google.com or https://example.com"
    ),
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


async def _fetch_website(domain: str) -> tuple[str, str]:
    headers = {
        "User-Agent": settings.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    }

    async with httpx.AsyncClient(
        timeout=settings.REQUEST_TIMEOUT,
        follow_redirects=True,
        headers=headers,
    ) as client:

        last_error = None

        for scheme in ("https", "http"):

            try:
                response = await client.get(f"{scheme}://{domain}")

                response.raise_for_status()

                content_type = response.headers.get(
                    "content-type",
                    "",
                ).lower()

                if "html" not in content_type:
                    raise RuntimeError(f"Website did not return HTML: {content_type}")

                html = response.content[: settings.MAX_RESPONSE_SIZE].decode(
                    response.encoding or "utf-8",
                    errors="replace",
                )

                return html, str(response.url)

            except Exception as exc:
                last_error = exc

        raise RuntimeError(f"Could not reach domain: {last_error}")


@router.get(
    "/classify",
    summary="Classify domain as B2B or B2C",
)
async def classify_domain(
    domain: str = Query(
        ...,
        description="Domain name, e.g. google.com",
    ),
):

    try:

        return await analyzer.analyze(domain)

    except Exception as exc:

        normalized_domain = analyzer.normalize_domain(domain)

        return {
            "domain": normalized_domain,
            "b2b_b2c": "UNKNOWN",
            "confidence": 0.0,
            "category": "UNKNOWN",
            "niche": None,
            "confidence_signals": {},
            "error": str(exc),
        }
