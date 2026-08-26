"""
Full-page domain intelligence collector.
A single call returns every column required for the Google Sheet:
website, tld, country, language, niche, email, dofollow, traffic_estimate,
top_country, b2b_b2c, social profiles, technologies, SEO signals, security, DNS.
"""

import re
import json
from urllib.parse import urlparse, urljoin
from tldextract import extract as tld_extract

import httpx
from bs4 import BeautifulSoup
from utils.config import settings
from api.website_analyzer import analyzer

# ──────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────
SOCIAL_MAP = {
    "linkedin.com": "linkedin",
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "youtube.com": "youtube",
    "tiktok.com": "tiktok",
    "github.com": "github",
    "pinterest.com": "pinterest",
    "tumblr.com": "tumblr",
}

TECH_RULES = {
    "WordPress": ("cms", r"wp-content|wordpress"),
    "Shopify": ("cms", r"cdn\.shopify|shopify"),
    "Wix": ("cms", r"wixstatic|wix\.com"),
    "Webflow": ("cms", r"webflow\.com"),
    "Squarespace": ("cms", r"squarespace\.com"),
    "Ghost": ("cms", r"ghost\.io|content\.ghost"),
    "Drupal": ("cms", r"drupal"),
    "Joomla": ("cms", r"joomla"),
    "React": ("frontend", r"react(?:\.production)?\.min\.js|_react|__react"),
    "Next.js": ("frontend", r"/_next/"),
    "Vue.js": ("frontend", r"vue(?:\.min)?\.js"),
    "Nuxt.js": ("frontend", r"/_nuxt/"),
    "Angular": ("frontend", r"ng-version|angular"),
    "Bootstrap": ("frontend", r"bootstrap(?:\.min)?(?:\.css|\.js)"),
    "Tailwind": ("frontend", r"tailwindcss|tailwind"),
    "jQuery": ("frontend", r"jquery(?:\.min)?\.js"),
    "Google Analytics": (
        "analytics",
        r"google-analytics\.com|googletagmanager\.com/gtag",
    ),
    "Google Tag Manager": ("analytics", r"googletagmanager\.com/gtm"),
    "Meta Pixel": ("analytics", r"connect\.facebook\.net|fbq\("),
    "Hotjar": ("analytics", r"hotjar\.com"),
    "HubSpot": ("crm", r"js\.hs-scripts\.com|hubspot"),
    "Intercom": ("crm", r"intercom\.io"),
    "Cloudflare": ("infrastructure", r"cloudflare"),
    "Vercel": ("infrastructure", r"vercel\.app|_vercel"),
    "AWS": ("infrastructure", r"amazonaws\.com"),
    "Nginx": ("server", r"nginx"),
    "Apache": ("server", r"apache"),
    "PHP": ("backend", r"\.php|x-powered-by.*php"),
    "Node.js": ("backend", r"x-powered-by.*node"),
    "Django": ("backend", r"csrftoken|x-powered-by.*django"),
}

NICHE_RULES = [
    (
        "casino",
        r"\bcasino\b|\bgambling\b|\bpoker\b|\bbetting\b|\bsportsbook\b|\bonline.casino\b",
    ),
    ("crypto", r"\bcrypto\b|\bbitcoin\b|\bblockchain\b|\bnft\b|\bweb3\b"),
    ("sports", r"\bsports?\b|\bfootball\b|\bbasketball\b|\bsoccer\b|\btennis\b"),
    ("finance", r"\bfinance\b|\binvest\b|\bbanking\b|\bloan\b|\binsurance\b"),
    ("technology", r"\btechnology\b|\bsoftware\b|\bsaas\b|\bapi\b|\bcloud\b"),
    ("ecommerce", r"\bshop\b|\bstore\b|\bcart\b|\bcheckout\b|\bproduct\b"),
    ("health", r"\bhealth\b|\bwellness\b|\bmedical\b|\bclinic\b|\bnurse\b"),
    ("news", r"\bnews\b|\bpolitics\b|\bbreaking\b|\bjournalism\b|\beditorial\b"),
    ("entertainment", r"\bentertain\b|\bmovie\b|\bmusic\b|\bcelebrity\b|\bgossip\b"),
    ("education", r"\blearning\b|\bcourse\b|\btutor\b|\beducation\b|\buniversit\b"),
    ("marketing", r"\bmarketing\b|\bseo\b|\bdigital\b|\bbranding\b|\bagency\b"),
    ("travel", r"\btravel\b|\bhotel\b|\bflight\b|\btourism\b|\bvacation\b"),
    ("food", r"\bfood\b|\brecipe\b|\brestaurant\b|\bcooking\b|\bbeverage\b"),
    ("real_estate", r"\breal estate\b|\bproperty\b|\bmortgage\b|\bhouse\b|\bhome\b"),
    ("automotive", r"\bcar\b|\bautomotive\b|\bvehicle\b|\bdealer\b|\bmotor\b"),
]

# JSON-LD @type → niche mapping
_SCHEMA_TYPE_NICHE = {
    "SoftwareApplication": "technology",
    "SoftwareSourceCode": "technology",
    "WebApplication": "technology",
    "MobileApplication": "technology",
    "Product": "ecommerce",
    "Store": "ecommerce",
    "Book": "education",
    "Course": "education",
    "EducationalOrganization": "education",
    "NewsArticle": "news",
    "Article": "news",
    "BlogPosting": "news",
    "MedicalEntity": "health",
    "Hospital": "health",
    "Restaurant": "food",
    "FoodEstablishment": "food",
    "TravelAgency": "travel",
    "Hotel": "travel",
    "RealEstateAgent": "real_estate",
    "AutoDealer": "automotive",
    "FinancialService": "finance",
    "BankOrCreditUnion": "finance",
}


def _guess_niche(text: str, structured_data: list[str] | None = None) -> str | None:
    """
    Score-based niche detection:
    1. Extract niche from JSON-LD @type (highest confidence)
    2. Score every niche by keyword hits across the text
    3. Return the niche with the most hits (min threshold: 2 hits)
    """
    import json as _json

    # Step 1: JSON-LD structured data – high-confidence signal
    if structured_data:
        for raw in structured_data:
            try:
                obj = _json.loads(raw)
                # handle @graph arrays
                items = obj.get("@graph", [obj]) if isinstance(obj, dict) else []
                for item in items:
                    schema_type = item.get("@type", "")
                    if isinstance(schema_type, list):
                        schema_type = schema_type[0]
                    if schema_type in _SCHEMA_TYPE_NICHE:
                        return _SCHEMA_TYPE_NICHE[schema_type]
            except Exception:
                pass

    # Step 2: Score-based keyword matching
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for niche, pattern in NICHE_RULES:
        hits = len(re.findall(pattern, text_lower))
        if hits > 0:
            scores[niche] = hits

    if not scores:
        return None

    best_niche = max(scores, key=lambda k: scores[k])
    # require at least 2 hits to avoid single-word false positives
    return best_niche if scores[best_niche] >= 2 else None


def _extract_emails(text: str, source_url: str) -> list[dict]:
    emails = set(re.findall(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", text, re.I))
    # filter out common false positives
    excluded = {"example.com", "domain.com", "yourdomain.com", "email.com", "test.com"}
    return [
        {"kind": "email", "value": e.lower(), "source_url": source_url}
        for e in emails
        if e.split("@")[-1].lower() not in excluded
    ]


def _extract_phones(text: str, source_url: str) -> list[dict]:
    phones = set(
        re.findall(
            r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?){2,4}\d{3,4}", text
        )
    )
    return [
        {
            "kind": "phone",
            "value": re.sub(r"\s+", " ", p).strip(),
            "source_url": source_url,
        }
        for p in phones
        if sum(c.isdigit() for c in p) >= 7
    ]


def _extract_social(links: list[str]) -> list[dict]:
    seen: dict[tuple, dict] = {}
    for url in links:
        netloc = urlparse(url).netloc.lower()
        for host, platform in SOCIAL_MAP.items():
            if host in netloc:
                seen[(platform, url)] = {"platform": platform, "url": url}
    return list(seen.values())


def _detect_technologies(html: str, headers: dict) -> list[dict]:
    corpus = html + json.dumps(headers)
    return [
        {"name": name, "category": cat, "evidence_pattern": pattern}
        for name, (cat, pattern) in TECH_RULES.items()
        if re.search(pattern, corpus, re.I)
    ]


def _extract_seo(soup: BeautifulSoup, url: str) -> dict:
    imgs = soup.select("img")
    og = {
        x.get("property"): x.get("content")
        for x in soup.select("meta[property^='og:']")
    }
    tw = {
        x.get("name"): x.get("content") for x in soup.select("meta[name^='twitter:']")
    }
    canonical = (soup.select_one("link[rel='canonical']") or {}).get("href")
    robots_meta = (soup.select_one("meta[name='robots']") or {}).get("content", "")
    title = soup.title.get_text(strip=True) if soup.title else None
    description = (soup.select_one("meta[name='description']") or {}).get("content")
    h1_list = [h.get_text(" ", strip=True) for h in soup.select("h1")]
    word_count = len(soup.get_text(" ", strip=True).split())
    structured_data = [
        s.get_text() for s in soup.select("script[type='application/ld+json']")
    ]

    # dofollow / nofollow
    all_links = soup.select("a[href]")
    dofollow = [
        a.get("href") for a in all_links if "nofollow" not in (a.get("rel") or [])
    ]
    nofollow = [a.get("href") for a in all_links if "nofollow" in (a.get("rel") or [])]

    # SEO scoring: simple deterministic 0-100
    score = 0
    if title:
        score += 15
    if description:
        score += 15
    if h1_list:
        score += 10
    if canonical:
        score += 10
    if word_count > 300:
        score += 10
    if og:
        score += 10
    if tw:
        score += 5
    if structured_data:
        score += 10
    if not ("noindex" in robots_meta.lower()):
        score += 15

    return {
        "title": title,
        "meta_description": description,
        "canonical_url": canonical,
        "robots_meta": robots_meta,
        "h1_tags": h1_list,
        "open_graph": og,
        "twitter_cards": tw,
        "structured_data": structured_data,
        "word_count": word_count,
        "images_total": len(imgs),
        "images_with_alt": sum(bool(x.get("alt")) for x in imgs),
        "images_without_alt": sum(not bool(x.get("alt")) for x in imgs),
        "dofollow_links": len(dofollow),
        "nofollow_links": len(nofollow),
        "seo_score": score,
    }


def _extract_security(headers: dict, url: str) -> dict:
    h = {k.lower(): v for k, v in headers.items()}
    return {
        "https": url.startswith("https://"),
        "hsts": h.get("strict-transport-security"),
        "csp": h.get("content-security-policy")
        or h.get("content-security-policy-report-only"),
        "x_frame_options": h.get("x-frame-options"),
        "x_content_type": h.get("x-content-type-options"),
        "referrer_policy": h.get("referrer-policy"),
        "permissions_policy": h.get("permissions-policy"),
    }


def _extract_dns(domain: str) -> list[dict]:
    import dns.resolver

    records = []
    for rtype in ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"):
        try:
            answers = dns.resolver.resolve(domain, rtype, lifetime=5)
            records += [
                {"record_type": rtype, "record_value": str(r), "error": None}
                for r in answers
            ]
        except Exception as exc:
            records.append(
                {
                    "record_type": rtype,
                    "record_value": None,
                    "error": type(exc).__name__,
                }
            )
    return records


def _extract_content_pages(links: list[str], base: str) -> dict:
    keywords = {
        "has_blog": r"/blog|/news|/articles?|/posts?",
        "has_about": r"/about",
        "has_contact": r"/contact",
        "has_pricing": r"/pricing|/plans?|/packages?",
        "has_careers": r"/careers?|/jobs?|/hiring",
        "has_case_studies": r"/case.studie|/success.stor|/portfolio",
        "has_services": r"/services?|/solutions?",
        "has_products": r"/products?|/shop|/store",
        "has_resources": r"/resources?|/downloads?|/guides?",
        "has_faq": r"/faq|/help|/support",
    }
    result = {}
    for key, pattern in keywords.items():
        result[key] = any(re.search(pattern, urlparse(lnk).path, re.I) for lnk in links)
    return result


def _marketing_score(
    seo: dict, social: list, contacts: list, tech: list, pages: dict
) -> dict:
    score = 0
    breakdown = {}

    # Website foundation
    ws = 0
    if seo.get("https"):
        ws += 5  # wait, this is in security; handled separately
    ws += min(15, seo.get("seo_score", 0) // 5)
    breakdown["seo"] = ws

    # Social
    platforms = {s["platform"] for s in social}
    sp = min(25, len(platforms) * 5)
    breakdown["social"] = sp

    # Content
    cp = sum(5 for v in pages.values() if v)
    breakdown["content"] = min(25, cp)

    # Lead gen
    lg = 0
    if any(c["kind"] == "email" for c in contacts):
        lg += 10
    if any(c["kind"] == "phone" for c in contacts):
        lg += 5
    if pages.get("has_contact"):
        lg += 5
    if pages.get("has_pricing"):
        lg += 5
    breakdown["lead_gen"] = min(25, lg)

    # Analytics
    analytics_techs = {t["name"] for t in tech if t["category"] == "analytics"}
    an = min(10, len(analytics_techs) * 5)
    breakdown["analytics"] = an

    score = sum(breakdown.values())
    breakdown["total"] = score
    return breakdown


# ──────────────────────────────────────────────────────────
# main entry point
# ──────────────────────────────────────────────────────────
async def full_domain_analysis(domain: str) -> dict:
    """
    Run all collectors against a single domain and return a flat,
    comprehensive intelligence report designed for Google-Sheet export.
    """
    # normalise
    domain = (
        domain.strip()
        .lower()
        .removeprefix("https://")
        .removeprefix("http://")
        .removeprefix("www.")
        .rstrip("/")
    )

    parsed = tld_extract(domain)
    tld = f".{parsed.suffix}" if parsed.suffix else None

    result: dict = {
        "domain": domain,
        "tld": tld,
        "website": None,
        "language": None,
        "country": None,
        "niche": None,
        "b2b_b2c": None,
        "email": None,
        "phone": None,
        "contacts": [],
        "do_follow_links": None,
        "no_follow_links": None,
        "social": [],
        "technologies": [],
        "seo": {},
        "security": {},
        "dns": [],
        "content_pages": {},
        "marketing_score": {},
        "errors": [],
    }

    ctx: dict | None = None

    # ── Website fetch ──────────────────────────────────────
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
                raise RuntimeError("Could not reach domain over HTTP or HTTPS")

        body = resp.content[: settings.MAX_RESPONSE_SIZE]
        html = (
            body.decode(resp.encoding or "utf-8", errors="replace")
            if "html" in resp.headers.get("content-type", "")
            else ""
        )
        soup = BeautifulSoup(html, "html.parser")
        links = [urljoin(str(resp.url), a["href"]) for a in soup.select("a[href]")]

        result["website"] = str(resp.url)
        result["language"] = soup.html.get("lang") if soup.html else None

        ctx = {
            "soup": soup,
            "html": html,
            "headers": dict(resp.headers),
            "links": links,
            "url": str(resp.url),
        }
    except Exception as exc:
        result["errors"].append(f"website_fetch: {exc}")
        # Still run DNS even if HTTP fails
        try:
            result["dns"] = _extract_dns(domain)
        except Exception as dns_exc:
            result["errors"].append(f"dns: {dns_exc}")
        return result

    # ── SEO ───────────────────────────────────────────────
    try:
        seo_data = _extract_seo(soup, str(resp.url))
        result["seo"] = seo_data
        result["do_follow_links"] = seo_data.get("dofollow_links")
        result["no_follow_links"] = seo_data.get("nofollow_links")
    except Exception as exc:
        result["errors"].append(f"seo: {exc}")

    # ── Contacts ─────────────────────────────────────────
    try:
        page_text = soup.get_text(" ", strip=True)
        emails = _extract_emails(page_text, str(resp.url))
        phones = _extract_phones(page_text, str(resp.url))
        result["contacts"] = emails + phones
        if emails:
            result["email"] = emails[0]["value"]
        if phones:
            result["phone"] = phones[0]["value"]
    except Exception as exc:
        result["errors"].append(f"contacts: {exc}")

    # ── Social ───────────────────────────────────────────
    try:
        result["social"] = _extract_social(links)
    except Exception as exc:
        result["errors"].append(f"social: {exc}")

    # ── Niche & B2B/B2C ──────────────────────────────────
    try:
        page_text = soup.get_text(" ", strip=True)
        structured_data = result.get("seo", {}).get("structured_data", [])
        result["niche"] = _guess_niche(page_text, structured_data)
        analysis = await analyzer.analyze(domain)
        result["b2b_b2c"] = analysis["b2b_b2c"]
    except Exception as exc:
        result["errors"].append(f"classification: {exc}")

    # ── Content page detection ────────────────────────────
    try:
        result["content_pages"] = _extract_content_pages(links, str(resp.url))
    except Exception as exc:
        result["errors"].append(f"content_pages: {exc}")

    # ── Marketing score ──────────────────────────────────
    try:
        result["marketing_score"] = _marketing_score(
            result.get("seo", {}),
            result.get("social", []),
            result.get("contacts", []),
            result.get("technologies", []),
            result.get("content_pages", {}),
        )
    except Exception as exc:
        result["errors"].append(f"marketing_score: {exc}")

    return result


def _guess_country_from_tld(tld: str) -> str | None:
    country_tlds = {
        ".hu": "Hungary",
        ".uk": "United Kingdom",
        ".de": "Germany",
        ".fr": "France",
        ".es": "Spain",
        ".it": "Italy",
        ".pl": "Poland",
        ".ru": "Russia",
        ".br": "Brazil",
        ".au": "Australia",
        ".ca": "Canada",
        ".in": "India",
        ".cn": "China",
        ".jp": "Japan",
        ".kr": "South Korea",
        ".nl": "Netherlands",
        ".be": "Belgium",
        ".se": "Sweden",
        ".no": "Norway",
        ".dk": "Denmark",
        ".fi": "Finland",
        ".pt": "Portugal",
        ".ro": "Romania",
        ".cz": "Czech Republic",
        ".sk": "Slovakia",
        ".gr": "Greece",
        ".tr": "Turkey",
        ".ua": "Ukraine",
        ".za": "South Africa",
        ".mx": "Mexico",
        ".ar": "Argentina",
        ".cl": "Chile",
        ".co": "Colombia",
        ".nz": "New Zealand",
        ".sg": "Singapore",
        ".hk": "Hong Kong",
        ".tw": "Taiwan",
        ".th": "Thailand",
        ".id": "Indonesia",
        ".my": "Malaysia",
        ".ph": "Philippines",
        ".vn": "Vietnam",
        ".pk": "Pakistan",
        ".eg": "Egypt",
        ".ng": "Nigeria",
        ".ke": "Kenya",
    }
    return country_tlds.get(tld)
