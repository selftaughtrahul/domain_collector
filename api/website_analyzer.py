"""
website_analyzer.py
===================

The ENGINE. Fetch -> extract -> match -> score -> decide.

Reading order if you're new to this file:

    1.  TextNormalizer   how raw HTML becomes matchable text
    2.  SignalMatcher    how a pattern turns into a score  (was the bug)
    3.  FeatureExtractor what we pull out of a page
    4.  Scorer           evidence per group
    5.  DecisionEngine   evidence -> a label + a reason      (was the gap)
    6.  WebsiteAnalyzer  glue + public API

WHY THE OLD VERSION RETURNED MOSTLY "UNKNOWN"
---------------------------------------------

    1. Substring matching. `text.count("api")` fires inside "rapido",
       "capital", "terapia". That is why some Portuguese news sites came
       back B2B on zero real evidence.
    2. English-only patterns against Portuguese, Dutch and Italian pages.
       Nothing matched, so business_total stayed under the threshold.
    3. `business_total < 15 -> UNKNOWN` with no fallback.
    4. website_type was computed and then thrown away. A site scoring 90
       on MEDIA still returned UNKNOWN for business model, even though a
       news portal obviously serves consumers.
    5. Homepage only. A news portal homepage is headlines; the business
       model lives on /sobre, /anuncie, /midia-kit.

All five are addressed below. UNKNOWN is now reserved for the case where
we genuinely could not read the page.
"""

from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

import httpx
from bs4 import BeautifulSoup

from utils.config import settings

from .signals import (
    CRAWL_HINT_PATHS,
    ECOMMERCE_TECH,
    NICHE_KEYWORDS,
    PUBLISHING_TECH,
    TEXT_SIGNALS,
    URL_SIGNALS,
    Signal,
)


# ====================================================================
# TUNING
# ====================================================================
#
# Every threshold the decision layer uses lives here, named, in one
# place. Change behaviour by changing numbers, not by rewriting logic.
# ====================================================================


class Config:
    # --- evidence gates -------------------------------------------
    MIN_BUSINESS_EVIDENCE = 10  # below this, commercial intent is noise
    STRONG_BUSINESS_EVIDENCE = 30
    MIN_TYPE_EVIDENCE = 25  # below this, a site-type claim is noise
    STRONG_TYPE_EVIDENCE = 55

    # --- dominance ------------------------------------------------
    TYPE_OVER_COMMERCE = 1.2  # how far site-type evidence must lead
    # commercial evidence to win outright
    BOTH_MIN_PER_SIDE = 30  # both sides must be real for BOTH
    BOTH_MAX_DOMINANCE = 0.30
    AMBIGUOUS_DOMINANCE = 0.12

    # --- content -------------------------------------------------
    MIN_TEXT_CHARS = 250  # below this the page is JS-rendered/blocked
    MAX_COUNT_PER_SIGNAL = 3  # cap repetition so nav menus can't dominate

    # --- crawling -------------------------------------------------
    DEEP_CRAWL = True
    MAX_EXTRA_PAGES = 3


# ====================================================================
# 1. TEXT NORMALIZATION
# ====================================================================


class TextNormalizer:
    _WS = re.compile(r"\s+")
    _SCHEME = re.compile(r"^https?://")
    _WWW = re.compile(r"^www\.")
    _SLASHES = re.compile(r"/+")

    @staticmethod
    def deaccent(text: str) -> str:
        """
        'notícias' -> 'noticias',  'promoção' -> 'promocao'

        Lets one pattern cover accented and unaccented spellings, which
        matters a lot for pt/it/es content where both appear in the wild.
        """
        decomposed = unicodedata.normalize("NFKD", str(text or ""))
        return "".join(ch for ch in decomposed if not unicodedata.combining(ch))

    @classmethod
    def text(cls, value: str) -> str:
        """Lowercase, de-accent, collapse whitespace and punctuation runs."""
        out = cls.deaccent(str(value or "")).lower()
        out = out.replace("’", "'").replace("–", "-").replace("—", "-")
        return cls._WS.sub(" ", out).strip()

    @classmethod
    def domain(cls, value: str) -> str:
        out = str(value or "").strip().lower()
        out = cls._SCHEME.sub("", out)
        out = cls._WWW.sub("", out)
        return out.split("/")[0].rstrip("/")

    @classmethod
    def path(cls, value: str) -> str:
        out = cls.deaccent(str(value or "").strip().lower())
        if not out:
            return "/"
        out = out.split("?")[0].split("#")[0]
        if not out.startswith("/"):
            out = "/" + out
        out = cls._SLASHES.sub("/", out)
        return out.rstrip("/") if len(out) > 1 else out


# ====================================================================
# 2. SIGNAL MATCHING          <-- the original bug lived here
# ====================================================================


class SignalMatcher:
    """
    Turns a Signal into a compiled regex, once, and caches it.

    Word matching uses (?<!\\w) ... (?!\\w) rather than \\b so that
    patterns ending in punctuation still behave. The practical effect:

        "api"   matches  "our api is open"
        "api"   does NOT match  "rapido" / "capital" / "terapia"
    """

    _cache: dict[tuple[str, str], re.Pattern] = {}

    @classmethod
    def compile(cls, signal: Signal) -> re.Pattern:
        key = (signal.text, signal.kind)
        if key not in cls._cache:
            pattern = TextNormalizer.text(signal.text)
            escaped = re.escape(pattern).replace(r"\ ", r"[\s\-_]+")
            if signal.kind == "word":
                expression = rf"(?<!\w){escaped}(?!\w)"
            else:
                expression = escaped
            cls._cache[key] = re.compile(expression)
        return cls._cache[key]

    @classmethod
    def count(cls, text: str, signal: Signal) -> int:
        return len(cls.compile(signal).findall(text))


# ====================================================================
# RESULT CONTAINERS
# ====================================================================


@dataclass
class Match:
    signal: str
    weight: int
    count: int
    score: int
    source: str = "text"  # text | url | tech

    def as_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal,
            "weight": self.weight,
            "count": self.count,
            "score": self.score,
            "source": self.source,
        }


@dataclass
class GroupScore:
    """
    Evidence for one group.

    `coverage` (how many DIFFERENT signals fired) matters as much as
    `score`. One phrase repeated three times is weak evidence; six
    different phrases firing once each is strong. The old code could not
    tell those apart.
    """

    name: str
    score: int = 0
    matches: list[Match] = field(default_factory=list)

    @property
    def coverage(self) -> int:
        return len({m.signal for m in self.matches})

    def add(self, match: Match) -> None:
        self.score += match.score
        self.matches.append(match)

    def top(self, n: int = 8) -> list[dict[str, Any]]:
        ranked = sorted(self.matches, key=lambda m: m.score, reverse=True)
        return [m.as_dict() for m in ranked[:n]]


# ====================================================================
# 3. FEATURE EXTRACTION
# ====================================================================


class FeatureExtractor:
    STRIP_TAGS = ("script", "style", "noscript", "svg", "iframe")

    @classmethod
    def extract(cls, html: str, final_url: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        structured_types = cls._structured_types(soup)
        language = cls._language(soup)

        for tag in soup(cls.STRIP_TAGS):
            tag.decompose()

        text = TextNormalizer.text(soup.get_text(" ", strip=True)[:150_000])
        title = (
            TextNormalizer.text(soup.title.get_text(" ", strip=True))
            if soup.title
            else ""
        )

        meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
        meta_description = TextNormalizer.text(meta.get("content", "")) if meta else ""

        headings = TextNormalizer.text(
            " ".join(
                h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])
            )
        )

        anchors, paths = cls._links(soup)

        return {
            "text": text,
            "title": title,
            "meta_description": meta_description,
            "headings": headings,
            "anchors": anchors,
            "paths": paths,
            "source": html.lower(),
            "structured_types": structured_types,
            "language": language,
            "final_url": final_url,
        }

    @staticmethod
    def _language(soup: BeautifulSoup) -> str:
        html_tag = soup.find("html")
        if html_tag and html_tag.get("lang"):
            return str(html_tag.get("lang")).lower()[:5]
        meta = soup.find("meta", attrs={"property": "og:locale"})
        if meta and meta.get("content"):
            return str(meta.get("content")).lower()[:5]
        return ""

    @staticmethod
    def _links(soup: BeautifulSoup) -> tuple[str, list[str]]:
        anchor_text: list[str] = []
        paths: list[str] = []
        for link in soup.find_all("a", href=True):
            anchor_text.append(link.get_text(" ", strip=True))
            href = str(link.get("href", ""))
            if href.startswith("/"):
                paths.append(TextNormalizer.path(href))
            elif href.startswith("http"):
                # keep same-site absolute links, drop external ones
                remainder = href.split("//", 1)[-1]
                if "/" in remainder:
                    paths.append(TextNormalizer.path("/" + remainder.split("/", 1)[1]))
        return TextNormalizer.text(" ".join(anchor_text)), sorted(set(paths))

    @staticmethod
    def _structured_types(soup: BeautifulSoup) -> list[str]:
        types: list[str] = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                raw = script.string or ""
                if not raw.strip():
                    continue
                data = json.loads(raw)
                for item in data if isinstance(data, list) else [data]:
                    if not isinstance(item, dict):
                        continue
                    value = item.get("@type")
                    if isinstance(value, list):
                        types.extend(str(v).lower() for v in value)
                    elif value:
                        types.append(str(value).lower())
            except Exception:
                continue
        return types

    @staticmethod
    def merge(pages: list[dict[str, Any]]) -> dict[str, Any]:
        """Fold extra crawled pages into the homepage's feature set."""
        base = dict(pages[0])
        for page in pages[1:]:
            base["text"] = f"{base['text']} {page['text']}"[:400_000]
            base["headings"] = f"{base['headings']} {page['headings']}"
            base["anchors"] = f"{base['anchors']} {page['anchors']}"
            base["source"] = f"{base['source']} {page['source']}"[:600_000]
            base["paths"] = sorted(set(base["paths"]) | set(page["paths"]))
            base["structured_types"] = list(
                set(base["structured_types"]) | set(page["structured_types"])
            )
        base["pages_analyzed"] = len(pages)
        return base


# ====================================================================
# 4. SCORING
# ====================================================================


class Scorer:
    @staticmethod
    def searchable(features: dict[str, Any]) -> str:
        """
        Title, description, headings and anchors are weighted by being
        included twice — a phrase in an <h1> or in the nav says more
        about the site than the same phrase buried in body copy.
        """
        emphasis = " ".join(
            [
                features.get("title", ""),
                features.get("meta_description", ""),
                features.get("headings", ""),
                features.get("anchors", ""),
            ]
        )
        return TextNormalizer.text(f"{emphasis} {emphasis} {features.get('text', '')}")

    @classmethod
    def score_text(cls, text: str, group: str, signals: Iterable[Signal]) -> GroupScore:
        result = GroupScore(name=group)
        for signal in signals:
            count = SignalMatcher.count(text, signal)
            if count <= 0:
                continue
            effective = min(count, Config.MAX_COUNT_PER_SIGNAL)
            result.add(
                Match(
                    signal=signal.text,
                    weight=signal.weight,
                    count=count,
                    score=signal.weight * effective,
                )
            )
        return result

    @staticmethod
    def score_paths(
        paths: list[str], group_paths: dict[str, int], into: GroupScore
    ) -> None:
        seen: set[str] = set()
        for raw in paths:
            path = TextNormalizer.path(raw)
            for candidate, weight in group_paths.items():
                candidate = TextNormalizer.path(candidate)
                if candidate == "/" or candidate in seen:
                    continue
                if path == candidate or path.startswith(candidate + "/"):
                    seen.add(candidate)
                    into.add(
                        Match(
                            signal=f"url:{candidate}",
                            weight=weight,
                            count=1,
                            score=weight,
                            source="url",
                        )
                    )

    @classmethod
    def run(cls, features: dict[str, Any]) -> dict[str, Any]:
        text = cls.searchable(features)
        paths = features.get("paths", [])

        groups: dict[str, GroupScore] = {}
        for name, signals in TEXT_SIGNALS.items():
            group = cls.score_text(text, name, signals)
            cls.score_paths(paths, URL_SIGNALS.get(name, {}), group)
            groups[name] = group

        # ---- structured data ---------------------------------------
        structured = {str(x).lower() for x in features.get("structured_types", [])}
        if "product" in structured:
            groups["B2C"].add(Match("schema:Product", 15, 1, 15, "tech"))
        if "offer" in structured:
            groups["B2C"].add(Match("schema:Offer", 8, 1, 8, "tech"))
        if {"newsarticle", "newsmediaorganization", "liveblogposting"} & structured:
            groups["MEDIA"].add(Match("schema:NewsArticle", 15, 1, 15, "tech"))
        if {"article", "blogposting"} & structured:
            groups["MEDIA"].add(Match("schema:Article", 6, 1, 6, "tech"))
        if "educationalorganization" in structured:
            groups["EDUCATION"].add(
                Match("schema:EducationalOrganization", 15, 1, 15, "tech")
            )
        if "ngo" in structured:
            groups["NONPROFIT"].add(Match("schema:NGO", 15, 1, 15, "tech"))
        if (
            "govermentorganization" in structured
            or "governmentorganization" in structured
        ):
            groups["GOVERNMENT"].add(
                Match("schema:GovernmentOrganization", 15, 1, 15, "tech")
            )

        # ---- platform fingerprints ---------------------------------
        source = features.get("source", "")
        ecommerce_platform = None
        for tech, weight in ECOMMERCE_TECH.items():
            if tech in source:
                ecommerce_platform = tech
                groups["B2C"].add(Match(f"tech:{tech}", weight, 1, weight, "tech"))
        for tech, weight in PUBLISHING_TECH.items():
            if weight and tech in source:
                groups["MEDIA"].add(Match(f"tech:{tech}", weight, 1, weight, "tech"))

        return {"groups": groups, "ecommerce_platform": ecommerce_platform}


# ====================================================================
# 5. DECISION LAYER          <-- the original gap lived here
# ====================================================================


SITE_TYPES = ("MEDIA", "TRADE_MEDIA", "EDUCATION", "GOVERNMENT", "NONPROFIT")

# What a site type implies about who it serves, when commercial signals
# are absent. This is the single most important addition: a news portal
# is not "unknown", it is a consumer-audience publisher.
TYPE_AUDIENCE = {
    "MEDIA": "B2C",
    "TRADE_MEDIA": "B2B",
    "EDUCATION": "B2C",
    "GOVERNMENT": "NOT_APPLICABLE",
    "NONPROFIT": "NOT_APPLICABLE",
}


class DecisionEngine:
    @staticmethod
    def site_type(groups: dict[str, GroupScore]) -> tuple[str, float, str]:
        candidates = {name: groups[name] for name in SITE_TYPES}
        best_name, best = max(candidates.items(), key=lambda kv: kv[1].score)

        # Trade press outranks general media when it has its own evidence:
        # a trade title also uses ordinary news vocabulary, so MEDIA will
        # almost always score higher on raw volume.
        trade = groups["TRADE_MEDIA"]
        if trade.score >= Config.MIN_TYPE_EVIDENCE and trade.coverage >= 2:
            best_name, best = "TRADE_MEDIA", trade

        if best.score < Config.MIN_TYPE_EVIDENCE or best.coverage < 2:
            return "BUSINESS", 0.0, "NO_TYPE_EVIDENCE"

        confidence = min(0.97, 0.55 + best.score / 200 + best.coverage / 60)
        return best_name, round(confidence, 2), "TYPE_SIGNALS"

    @staticmethod
    def business_model(
        groups: dict[str, GroupScore],
        site_type: str,
        type_confidence: float,
        ecommerce_platform: str | None,
    ) -> tuple[str, float, str]:
        b2b, b2c = groups["B2B"], groups["B2C"]
        evidence = b2b.score + b2c.score
        type_score = groups[site_type].score if site_type in TYPE_AUDIENCE else 0

        # ---- 1. a clearly identified site type outranks stray commercial
        #         phrases. Order matters here: a news portal that sells ad
        #         space will always trip a few B2B-looking phrases, and
        #         letting those decide is exactly how you mislabel every
        #         publisher in the list as B2B.
        if (
            type_score >= Config.STRONG_TYPE_EVIDENCE
            and type_score > evidence * Config.TYPE_OVER_COMMERCE
            and not ecommerce_platform
        ):
            audience = TYPE_AUDIENCE[site_type]
            confidence = round(min(0.90, 0.50 + type_confidence * 0.35), 2)
            return audience, confidence, f"AUDIENCE_FROM_{site_type}"

        # ---- 2. a storefront is decisive, whatever else is on the page
        if ecommerce_platform and b2c.score >= b2b.score:
            return "B2C", 0.92, "ECOMMERCE_PLATFORM"

        # ---- 3. commercial signals, if there are enough of them
        if (
            evidence >= Config.MIN_BUSINESS_EVIDENCE
            and (b2b.coverage + b2c.coverage) >= 2
        ):
            dominance = abs(b2b.score - b2c.score) / evidence

            if (
                b2b.score >= Config.BOTH_MIN_PER_SIDE
                and b2c.score >= Config.BOTH_MIN_PER_SIDE
                and dominance <= Config.BOTH_MAX_DOMINANCE
            ):
                return "BOTH", round(min(0.95, 0.65 + evidence / 400), 2), "STRONG_BOTH"

            if dominance >= Config.AMBIGUOUS_DOMINANCE:
                winner, group = ("B2B", b2b) if b2b.score > b2c.score else ("B2C", b2c)
                confidence = min(
                    0.97,
                    0.45
                    + dominance * 0.40
                    + min(group.score / 300, 0.15)
                    + min(group.coverage / 40, 0.10),
                )
                return winner, round(confidence, 2), "COMMERCIAL_SIGNALS"

        # ---- 4. no clear commercial motion: fall back to what the site IS
        #         (this is where the old code gave up and said UNKNOWN)
        if site_type in TYPE_AUDIENCE and type_confidence > 0:
            audience = TYPE_AUDIENCE[site_type]
            confidence = round(min(0.88, 0.45 + type_confidence * 0.35), 2)
            return audience, confidence, f"AUDIENCE_FROM_{site_type}"

        # ---- 5. weak commercial hint is better than nothing
        if evidence > 0:
            winner = "B2B" if b2b.score > b2c.score else "B2C"
            return winner, round(min(0.40, 0.20 + evidence / 100), 2), "WEAK_EVIDENCE"

        return "UNKNOWN", 0.0, "NO_EVIDENCE"


# ====================================================================
# 6. NICHE
# ====================================================================


class NicheGuesser:
    @staticmethod
    def guess(text: str) -> dict[str, Any]:
        scored: list[tuple[str, int, list[str]]] = []
        for niche, keywords in NICHE_KEYWORDS.items():
            score, matched = 0, []
            for keyword in keywords:
                signal = Signal(text=keyword, weight=1)
                count = SignalMatcher.count(text, signal)
                if count:
                    score += min(count, Config.MAX_COUNT_PER_SIGNAL)
                    matched.append(keyword)
            if score:
                scored.append((niche, score, matched))

        if not scored:
            return {"name": None, "confidence": 0.0, "signals": [], "runner_up": None}

        scored.sort(key=lambda item: item[1], reverse=True)
        name, score, matched = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else None
        return {
            "name": name,
            "confidence": round(min(score / 12, 1.0), 2),
            "signals": matched[:10],
            "runner_up": runner_up,
        }


# ====================================================================
# 7. PUBLIC API
# ====================================================================


class WebsiteAnalyzer:
    def __init__(self) -> None:
        self.timeout = settings.REQUEST_TIMEOUT
        self.max_response_size = settings.MAX_RESPONSE_SIZE
        self.user_agent = settings.USER_AGENT
        self.max_extra_pages = getattr(
            settings, "MAX_EXTRA_PAGES", Config.MAX_EXTRA_PAGES
        )

    # ----------------------------------------------------------------
    # FETCH
    # ----------------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                # Ask for the local language; many pt/it sites serve a
                # thinner English page to default clients.
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8,it;q=0.7,nl;q=0.6",
            },
        )

    async def _get(self, client: httpx.AsyncClient, url: str) -> tuple[str, str]:
        response = await client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type:
            raise RuntimeError(f"Not HTML: {content_type or 'unknown content-type'}")

        html = response.content[: self.max_response_size].decode(
            response.encoding or "utf-8", errors="replace"
        )
        return html, str(response.url)

    async def fetch_home(self, domain: str) -> tuple[str, str]:
        last_error: Exception | None = None
        async with self._client() as client:
            for scheme in ("https", "http"):
                try:
                    return await self._get(client, f"{scheme}://{domain}")
                except Exception as exc:
                    last_error = exc
        raise RuntimeError(f"Could not reach domain: {last_error}")

    async def fetch_extra(
        self, base_url: str, paths: list[str]
    ) -> list[dict[str, Any]]:
        """Fetch a few high-signal internal pages, best effort."""
        wanted: list[str] = []
        for path in paths:
            if any(path == hint or path.startswith(hint) for hint in CRAWL_HINT_PATHS):
                if path not in wanted:
                    wanted.append(path)
            if len(wanted) >= self.max_extra_pages:
                break

        if not wanted:
            return []

        root = base_url.rstrip("/")
        root = root[: root.index("/", 8)] if "/" in root[8:] else root

        async with self._client() as client:

            async def one(path: str) -> dict[str, Any] | None:
                try:
                    html, url = await self._get(client, f"{root}{path}")
                    return FeatureExtractor.extract(html, url)
                except Exception:
                    return None

            results = await asyncio.gather(*(one(p) for p in wanted))

        return [r for r in results if r]

    # ----------------------------------------------------------------
    # ANALYZE
    # ----------------------------------------------------------------

    async def analyze(self, domain: str, deep: bool | None = None) -> dict[str, Any]:
        deep = Config.DEEP_CRAWL if deep is None else deep
        domain = TextNormalizer.domain(domain)

        result: dict[str, Any] = {
            "domain": domain,
            "b2b_b2c": "UNKNOWN",
            "business_model": "UNKNOWN",
            "business_confidence": 0.0,
            "business_reason": "NOT_ANALYZED",
            "website_type": "UNKNOWN",
            "website_type_confidence": 0.0,
            "category": "UNKNOWN",
            "niche": None,
            "language": None,
            "pages_analyzed": 0,
            "confidence_signals": {},
            "error": None,
        }

        try:
            html, final_url = await self.fetch_home(domain)
            home = FeatureExtractor.extract(html, final_url)

            pages = [home]
            if deep:
                pages.extend(await self.fetch_extra(final_url, home["paths"]))
            features = FeatureExtractor.merge(pages)

            if len(features["text"]) < Config.MIN_TEXT_CHARS:
                result["error"] = (
                    "Thin content — the page is likely JavaScript-rendered or "
                    "behind a bot wall. Rendering is required to classify it."
                )
                result["business_reason"] = "THIN_CONTENT"
                result["pages_analyzed"] = len(pages)
                return result

            scored = Scorer.run(features)
            groups: dict[str, GroupScore] = scored["groups"]

            site_type, type_confidence, type_reason = DecisionEngine.site_type(groups)
            model, model_confidence, model_reason = DecisionEngine.business_model(
                groups, site_type, type_confidence, scored["ecommerce_platform"]
            )
            niche = NicheGuesser.guess(Scorer.searchable(features))

            result.update(
                {
                    "b2b_b2c": model,
                    "business_model": model,
                    "business_confidence": model_confidence,
                    "business_reason": model_reason,
                    "website_type": site_type,
                    "website_type_confidence": type_confidence,
                    "category": site_type,
                    "niche": niche,
                    "language": features.get("language") or None,
                    "pages_analyzed": features.get("pages_analyzed", 1),
                    "confidence_signals": {
                        "scores": {name: g.score for name, g in groups.items()},
                        "coverage": {name: g.coverage for name, g in groups.items()},
                        "type_reason": type_reason,
                        "business_reason": model_reason,
                        "top_b2b_signals": groups["B2B"].top(),
                        "top_b2c_signals": groups["B2C"].top(),
                        "top_media_signals": groups["MEDIA"].top(),
                        "top_trade_media_signals": groups["TRADE_MEDIA"].top(),
                        "top_education_signals": groups["EDUCATION"].top(),
                        "top_government_signals": groups["GOVERNMENT"].top(),
                        "top_nonprofit_signals": groups["NONPROFIT"].top(),
                        "sells_advertising": groups["ADVERTISING"].score >= 10,
                        "top_advertising_signals": groups["ADVERTISING"].top(5),
                        "ecommerce": bool(scored["ecommerce_platform"]),
                        "ecommerce_platform": scored["ecommerce_platform"],
                        "structured_data": features["structured_types"][:20],
                        "text_length": len(features["text"]),
                        "final_url": features["final_url"],
                    },
                }
            )

        except Exception as exc:
            result["error"] = str(exc)
            result["business_reason"] = "FETCH_FAILED"

        return result

    async def analyze_many(
        self, domains: list[str], concurrency: int = 8, deep: bool | None = None
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(concurrency)

        async def guarded(domain: str) -> dict[str, Any]:
            async with semaphore:
                return await self.analyze(domain, deep=deep)

        return await asyncio.gather(*(guarded(d) for d in domains))


analyzer = WebsiteAnalyzer()
