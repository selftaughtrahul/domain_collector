from fastapi import APIRouter, Query
from collectors.intelligence import (
    full_domain_analysis,
    _classify_b2b_b2c,
    _guess_niche,
)
import httpx
from bs4 import BeautifulSoup
from utils.config import settings

router = APIRouter(tags=["Analyze"])


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


# @router.get("/classify", summary="Classify domain as B2B or B2C")
# async def classify_domain(
#     domain: str = Query(..., description="Domain name, e.g. google.com"),
# ):
#     """
#     Fast classification endpoint.
#     Fetches the homepage of the domain and returns:
#     - `domain`
#     - `b2b_b2c` — B2B / B2C / UNKNOWN
#     - `niche` — detected industry (casino, crypto, finance, tech, etc.)
#     - `confidence_signals` — the keywords/signals that drove the classification
#     """
#     domain = domain.strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")

#     result = {
#         "domain": domain,
#         "b2b_b2c": "UNKNOWN",
#         "niche": None,
#         "confidence_signals": {},
#         "error": None,
#     }

#     try:
#         async with httpx.AsyncClient(
#             timeout=settings.REQUEST_TIMEOUT,
#             follow_redirects=True,
#             headers={"User-Agent": settings.USER_AGENT},
#         ) as client:
#             for scheme in ("https", "http"):
#                 try:
#                     resp = await client.get(f"{scheme}://{domain}")
#                     break
#                 except Exception:
#                     continue
#             else:
#                 raise RuntimeError("Could not reach domain")

#         html = resp.content[:settings.MAX_RESPONSE_SIZE].decode(
#             resp.encoding or "utf-8", errors="replace"
#         )
#         soup = BeautifulSoup(html, "html.parser")
#         text = soup.get_text(" ", strip=True)

#         # Detect niche
#         result["niche"] = _guess_niche(text)

#         # Classify B2B / B2C with signal counts
#         import re
#         b2b_pattern = r"\benterprise\b|\bsolution[s]?\b|\bpartner[s]?\b|\bclient[s]?\b|b2b|\bbusiness\b|\bteam[s]?\b|\bapi\b|\bsaas\b"
#         b2c_pattern = r"\bshop\b|\bstore\b|\bprice\b|\bbuy\b|\bpurchase\b|\bsale\b|\bcustomer\b|b2c"

#         b2b_matches = re.findall(b2b_pattern, text[:50000], re.I)
#         b2c_matches = re.findall(b2c_pattern, text[:50000], re.I)

#         b2b_count = len(b2b_matches)
#         b2c_count = len(b2c_matches)

#         result["confidence_signals"] = {
#             "b2b_keyword_count": b2b_count,
#             "b2c_keyword_count": b2c_count,
#             "top_b2b_signals": list(set(w.lower() for w in b2b_matches))[:10],
#             "top_b2c_signals": list(set(w.lower() for w in b2c_matches))[:10],
#         }

#         if b2c_count > b2b_count:
#             result["b2b_b2c"] = "B2C"
#         elif b2b_count > b2c_count:
#             result["b2b_b2c"] = "B2B"
#         else:
#             result["b2b_b2c"] = "UNKNOWN"

#     except Exception as exc:
#         result["error"] = str(exc)

#     return result


import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query

from utils.config import settings

router = APIRouter()


# ============================================================
# B2B SIGNALS
# ============================================================

B2B_SIGNALS = {
    # Very strong signals
    "request a demo": 12,
    "book a demo": 12,
    "schedule a demo": 12,
    "contact sales": 12,
    "talk to sales": 12,
    "request pricing": 10,
    "custom pricing": 10,
    "enterprise": 8,
    "enterprise solution": 10,
    "business solutions": 8,
    "wholesale": 10,
    "distributor": 9,
    "procurement": 8,
    # Strong
    "partner program": 7,
    "partners": 5,
    "reseller": 7,
    "supplier": 6,
    "vendor": 5,
    "for businesses": 7,
    "for enterprises": 8,
    "for teams": 5,
    "business customers": 7,
    # Medium
    "saas": 5,
    "api": 4,
    "developers": 3,
    "integrations": 3,
    "organization": 3,
    "organizations": 3,
    "corporate": 4,
    "teams": 3,
    "employees": 3,
}


# ============================================================
# B2C SIGNALS
# ============================================================

B2C_SIGNALS = {
    # Very strong
    "add to cart": 12,
    "checkout": 12,
    "buy now": 12,
    "shop now": 10,
    "track order": 10,
    "wishlist": 8,
    # Strong
    "free shipping": 8,
    "home delivery": 8,
    "size guide": 7,
    "shopping cart": 10,
    "your cart": 8,
    "place order": 8,
    "order now": 8,
    # Medium
    "shop": 4,
    "store": 3,
    "sale": 3,
    "discount": 3,
    "coupon": 4,
    "delivery": 3,
    "consumer": 5,
    "individual": 3,
}


# ============================================================
# URL SIGNALS
# ============================================================

B2B_URL_SIGNALS = {
    "/enterprise": 10,
    "/business": 7,
    "/solutions": 5,
    "/industries": 5,
    "/partners": 6,
    "/partner": 6,
    "/developers": 5,
    "/api": 5,
    "/request-demo": 12,
    "/demo": 10,
    "/contact-sales": 12,
    "/enterprise-solutions": 10,
}


B2C_URL_SIGNALS = {
    "/shop": 8,
    "/store": 6,
    "/products": 5,
    "/product": 5,
    "/cart": 12,
    "/checkout": 12,
    "/wishlist": 8,
    "/collections": 6,
    "/sale": 5,
    "/orders": 6,
}


# ============================================================
# E-COMMERCE TECHNOLOGIES
# ============================================================

ECOMMERCE_TECH = {
    "shopify": 10,
    "woocommerce": 10,
    "magento": 8,
    "prestashop": 8,
    "bigcommerce": 8,
}


# ============================================================
# NICHE KEYWORDS
# ============================================================

NICHE_KEYWORDS = {
    "crypto": [
        "cryptocurrency",
        "bitcoin",
        "ethereum",
        "crypto",
        "blockchain",
        "web3",
        "defi",
        "nft",
    ],
    "finance": [
        "banking",
        "loan",
        "mortgage",
        "investment",
        "fintech",
        "finance",
        "insurance",
        "credit",
    ],
    "casino": [
        "casino",
        "slots",
        "betting",
        "sportsbook",
        "poker",
        "gambling",
    ],
    "technology": [
        "software",
        "technology",
        "cloud",
        "saas",
        "api",
        "developer",
        "platform",
    ],
    "ecommerce": [
        "shopping",
        "online store",
        "product",
        "add to cart",
        "checkout",
        "shop now",
    ],
    "healthcare": [
        "healthcare",
        "hospital",
        "clinic",
        "medical",
        "doctor",
        "pharmacy",
    ],
    "education": [
        "education",
        "course",
        "training",
        "school",
        "university",
        "learning",
    ],
    "marketing": [
        "marketing",
        "seo",
        "advertising",
        "social media",
        "digital marketing",
        "content marketing",
    ],
}


# ============================================================
# DOMAIN NORMALIZATION
# ============================================================


def normalize_domain(domain: str) -> str:
    domain = domain.strip().lower()

    domain = re.sub(
        r"^https?://",
        "",
        domain,
    )

    domain = re.sub(
        r"^www\.",
        "",
        domain,
    )

    return domain.rstrip("/")


# ============================================================
# FETCH WEBSITE
# ============================================================


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


# ============================================================
# TEXT NORMALIZATION
# ============================================================


def _normalize_text(text: str) -> str:
    text = text.lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# EXTRACT WEBSITE FEATURES
# ============================================================


def _extract_features(
    html: str,
    final_url: str,
) -> dict[str, Any]:

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    # Remove unnecessary elements
    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
        ]
    ):
        tag.decompose()

    # --------------------------------------------------------
    # Visible text
    # --------------------------------------------------------

    visible_text = soup.get_text(
        " ",
        strip=True,
    )

    visible_text = _normalize_text(visible_text[:100_000])

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    title = ""

    if soup.title:
        title = _normalize_text(soup.title.get_text(" ", strip=True))

    # --------------------------------------------------------
    # Meta description
    # --------------------------------------------------------

    meta_description = ""

    meta = soup.find(
        "meta",
        attrs={"name": re.compile("^description$", re.I)},
    )

    if meta:
        meta_description = _normalize_text(meta.get("content", ""))

    # --------------------------------------------------------
    # Headings
    # --------------------------------------------------------

    headings = " ".join(
        _normalize_text(h.get_text(" ", strip=True))
        for h in soup.find_all(["h1", "h2", "h3"])
    )

    # --------------------------------------------------------
    # Links
    # --------------------------------------------------------

    links = []

    for link in soup.find_all("a", href=True):
        href = link.get("href", "").lower()
        anchor = _normalize_text(link.get_text(" ", strip=True))

        links.append(
            {
                "href": href,
                "anchor": anchor,
            }
        )

    # --------------------------------------------------------
    # HTML source
    # --------------------------------------------------------

    source = html.lower()

    # --------------------------------------------------------
    # Structured data
    # --------------------------------------------------------

    structured_types = []

    for script in soup.find_all(
        "script",
        type="application/ld+json",
    ):

        try:
            data = json.loads(script.string or "")

            items = data if isinstance(data, list) else [data]

            for item in items:

                if not isinstance(item, dict):
                    continue

                item_type = item.get("@type")

                if isinstance(item_type, list):
                    structured_types.extend(str(x).lower() for x in item_type)

                elif item_type:
                    structured_types.append(str(item_type).lower())

        except Exception:
            continue

    # --------------------------------------------------------
    # Link paths
    # --------------------------------------------------------

    paths = []

    for link in links:

        href = link["href"]

        if href.startswith("/"):
            paths.append(href.split("?")[0])

    return {
        "text": visible_text,
        "title": title,
        "meta_description": meta_description,
        "headings": headings,
        "source": source,
        "links": links,
        "paths": paths,
        "structured_types": structured_types,
        "final_url": final_url,
    }


# ============================================================
# SIGNAL SCORING
# ============================================================


def _score_signals(features: dict[str, Any]) -> dict[str, Any]:

    text = features["text"]

    searchable_text = " ".join(
        [
            text,
            features["title"],
            features["meta_description"],
            features["headings"],
        ]
    )

    searchable_text = _normalize_text(searchable_text)

    source = features["source"]

    b2b_score = 0
    b2c_score = 0

    b2b_signals = []
    b2c_signals = []

    # --------------------------------------------------------
    # Text signals
    # --------------------------------------------------------

    for keyword, weight in B2B_SIGNALS.items():

        count = searchable_text.count(keyword)

        if count > 0:

            # Cap repeated keywords
            effective_count = min(count, 3)

            score = weight * effective_count

            b2b_score += score

            b2b_signals.append(
                {
                    "signal": keyword,
                    "count": count,
                    "weight": weight,
                    "score": score,
                }
            )

    for keyword, weight in B2C_SIGNALS.items():

        count = searchable_text.count(keyword)

        if count > 0:

            effective_count = min(count, 3)

            score = weight * effective_count

            b2c_score += score

            b2c_signals.append(
                {
                    "signal": keyword,
                    "count": count,
                    "weight": weight,
                    "score": score,
                }
            )

    # --------------------------------------------------------
    # URL/path signals
    # --------------------------------------------------------

    paths = features["paths"]

    for path in paths:

        for signal, weight in B2B_URL_SIGNALS.items():

            if path.startswith(signal):
                b2b_score += weight

                b2b_signals.append(
                    {
                        "signal": f"url:{signal}",
                        "count": 1,
                        "weight": weight,
                        "score": weight,
                    }
                )

        for signal, weight in B2C_URL_SIGNALS.items():

            if path.startswith(signal):
                b2c_score += weight

                b2c_signals.append(
                    {
                        "signal": f"url:{signal}",
                        "count": 1,
                        "weight": weight,
                        "score": weight,
                    }
                )

    # --------------------------------------------------------
    # Structured data
    # --------------------------------------------------------

    structured_types = set(features["structured_types"])

    if "product" in structured_types:
        b2c_score += 15

        b2c_signals.append(
            {
                "signal": "schema:Product",
                "count": 1,
                "weight": 15,
                "score": 15,
            }
        )

    if "offer" in structured_types:
        b2c_score += 8

        b2c_signals.append(
            {
                "signal": "schema:Offer",
                "count": 1,
                "weight": 8,
                "score": 8,
            }
        )

    # --------------------------------------------------------
    # E-commerce technology
    # --------------------------------------------------------

    ecommerce_detected = None

    for tech, weight in ECOMMERCE_TECH.items():

        if tech in source:

            ecommerce_detected = tech

            b2c_score += weight

            b2c_signals.append(
                {
                    "signal": f"technology:{tech}",
                    "count": 1,
                    "weight": weight,
                    "score": weight,
                }
            )

    # --------------------------------------------------------
    # HTML CTA detection
    # --------------------------------------------------------

    strong_b2b_ctas = [
        "request a demo",
        "book a demo",
        "contact sales",
        "talk to sales",
        "schedule a demo",
        "request pricing",
    ]

    strong_b2c_ctas = [
        "add to cart",
        "buy now",
        "checkout",
        "shop now",
        "order now",
    ]

    for cta in strong_b2b_ctas:

        if cta in searchable_text:

            b2b_score += 15

            b2b_signals.append(
                {
                    "signal": f"cta:{cta}",
                    "count": 1,
                    "weight": 15,
                    "score": 15,
                }
            )

    for cta in strong_b2c_ctas:

        if cta in searchable_text:

            b2c_score += 15

            b2c_signals.append(
                {
                    "signal": f"cta:{cta}",
                    "count": 1,
                    "weight": 15,
                    "score": 15,
                }
            )

    return {
        "b2b_score": b2b_score,
        "b2c_score": b2c_score,
        "b2b_signals": b2b_signals,
        "b2c_signals": b2c_signals,
        "ecommerce_detected": ecommerce_detected,
    }


# ============================================================
# CLASSIFICATION
# ============================================================


def _classify(
    b2b_score: float,
    b2c_score: float,
) -> tuple[str, float]:

    total = b2b_score + b2c_score

    if total == 0:
        return "UNKNOWN", 0.0

    difference = abs(b2b_score - b2c_score)

    # Both strong
    if b2b_score >= 30 and b2c_score >= 30 and difference <= total * 0.35:
        confidence = min(
            0.99,
            total / 150,
        )

        return "BOTH", round(
            confidence,
            2,
        )

    # Too close to classify
    if difference < 10:
        return "UNKNOWN", round(
            difference / max(total, 1),
            2,
        )

    if b2b_score > b2c_score:

        confidence = b2b_score / total

        return "B2B", round(
            confidence,
            2,
        )

    confidence = b2c_score / total

    return "B2C", round(
        confidence,
        2,
    )


# ============================================================
# NICHE
# ============================================================


def _guess_niche(
    features: dict[str, Any],
) -> dict[str, Any]:

    text = " ".join(
        [
            features["text"],
            features["title"],
            features["meta_description"],
            features["headings"],
        ]
    )

    text = _normalize_text(text)

    scores = {}

    for niche, keywords in NICHE_KEYWORDS.items():

        score = 0
        matched = []

        for keyword in keywords:

            count = text.count(keyword)

            if count:

                score += min(
                    count,
                    3,
                )

                matched.append(keyword)

        if score:
            scores[niche] = {
                "score": score,
                "signals": matched,
            }

    if not scores:
        return {
            "name": None,
            "confidence": 0.0,
            "signals": [],
        }

    best_niche = max(
        scores,
        key=lambda x: scores[x]["score"],
    )

    best_score = scores[best_niche]["score"]

    confidence = min(
        best_score / 10,
        1.0,
    )

    return {
        "name": best_niche,
        "confidence": round(
            confidence,
            2,
        ),
        "signals": scores[best_niche]["signals"],
    }


# ============================================================
# API ENDPOINT
# ============================================================


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

    domain = normalize_domain(domain)

    result = {
        "domain": domain,
        "b2b_b2c": "UNKNOWN",
        "confidence": 0.0,
        "niche": None,
        "confidence_signals": {},
        "error": None,
    }

    try:

        # ----------------------------------------------------
        # Fetch
        # ----------------------------------------------------

        html, final_url = await _fetch_website(domain)

        # ----------------------------------------------------
        # Extract
        # ----------------------------------------------------

        features = _extract_features(
            html,
            final_url,
        )

        # ----------------------------------------------------
        # Niche
        # ----------------------------------------------------

        niche = _guess_niche(features)

        # ----------------------------------------------------
        # Classification
        # ----------------------------------------------------

        scores = _score_signals(features)

        classification, confidence = _classify(
            scores["b2b_score"],
            scores["b2c_score"],
        )

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        result.update(
            {
                "b2b_b2c": classification,
                "confidence": confidence,
                "niche": niche,
                "confidence_signals": {
                    "b2b_score": scores["b2b_score"],
                    "b2c_score": scores["b2c_score"],
                    "top_b2b_signals": sorted(
                        scores["b2b_signals"],
                        key=lambda x: x["score"],
                        reverse=True,
                    )[:10],
                    "top_b2c_signals": sorted(
                        scores["b2c_signals"],
                        key=lambda x: x["score"],
                        reverse=True,
                    )[:10],
                    "ecommerce": bool(scores["ecommerce_detected"]),
                    "ecommerce_platform": (scores["ecommerce_detected"]),
                    "structured_data": features["structured_types"],
                    "final_url": features["final_url"],
                },
            }
        )

    except Exception as exc:

        result["error"] = str(exc)

    return result
