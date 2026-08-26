import json
import re
from typing import Any
import httpx
from bs4 import BeautifulSoup
from utils.config import settings
from .kewords_classify import *


class WebsiteAnalyzer:

    def __init__(self):
        self.timeout = settings.REQUEST_TIMEOUT
        self.max_response_size = settings.MAX_RESPONSE_SIZE
        self.user_agent = settings.USER_AGENT

    @staticmethod
    def normalize_domain(domain: str) -> str:
        domain = domain.strip().lower()
        domain = re.sub(r"^https?://", "", domain)
        domain = re.sub(r"^www\.", "", domain)
        return domain.rstrip("/")

    async def fetch(self, domain: str) -> tuple[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml",
        }

        last_error = None

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:

            for scheme in ("https", "http"):
                try:
                    response = await client.get(f"{scheme}://{domain}")

                    response.raise_for_status()

                    content_type = response.headers.get(
                        "content-type",
                        "",
                    ).lower()

                    if "html" not in content_type:
                        raise RuntimeError(
                            f"Website did not return HTML: {content_type}"
                        )

                    html = response.content[: self.max_response_size].decode(
                        response.encoding or "utf-8",
                        errors="replace",
                    )

                    return html, str(response.url)

                except Exception as exc:
                    last_error = exc

        raise RuntimeError(f"Could not reach domain: {last_error}")

    @staticmethod
    def normalize_text(text: str) -> str:
        text = text.lower()
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def extract_features(
        self,
        html: str,
        final_url: str,
    ) -> dict[str, Any]:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()

        text = self.normalize_text(soup.get_text(" ", strip=True)[:100_000])

        title = ""

        if soup.title:
            title = self.normalize_text(soup.title.get_text(" ", strip=True))

        meta_description = ""

        meta = soup.find(
            "meta",
            attrs={
                "name": re.compile(
                    "^description$",
                    re.I,
                )
            },
        )

        if meta:
            meta_description = self.normalize_text(meta.get("content", ""))

        headings = self.normalize_text(
            " ".join(
                h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])
            )
        )

        links = []

        for link in soup.find_all(
            "a",
            href=True,
        ):
            links.append(
                {
                    "href": link.get(
                        "href",
                        "",
                    ).lower(),
                    "anchor": self.normalize_text(
                        link.get_text(
                            " ",
                            strip=True,
                        )
                    ),
                }
            )

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

        paths = [
            link["href"].split("?")[0] for link in links if link["href"].startswith("/")
        ]

        return {
            "text": text,
            "title": title,
            "meta_description": meta_description,
            "headings": headings,
            "source": html.lower(),
            "links": links,
            "paths": paths,
            "structured_types": structured_types,
            "final_url": final_url,
        }

    @staticmethod
    def searchable_text(
        features: dict[str, Any],
    ) -> str:

        return WebsiteAnalyzer.normalize_text(
            " ".join(
                [
                    features["text"],
                    features["title"],
                    features["meta_description"],
                    features["headings"],
                ]
            )
        )

    @staticmethod
    def score_signal_group(
        text: str,
        signals: dict[str, int],
    ) -> tuple[float, list]:

        score = 0
        matches = []

        for keyword, weight in signals.items():

            count = text.count(keyword)

            if count <= 0:
                continue

            effective_count = min(
                count,
                3,
            )

            signal_score = weight * effective_count

            score += signal_score

            matches.append(
                {
                    "signal": keyword,
                    "count": count,
                    "weight": weight,
                    "score": signal_score,
                }
            )

        return score, matches

    def score_url_signals(
        self,
        paths: list[str],
        signals: dict[str, int],
    ) -> tuple[float, list]:

        score = 0
        matches = []

        for path in paths:

            for signal, weight in signals.items():

                if path.startswith(signal):

                    score += weight

                    matches.append(
                        {
                            "signal": f"url:{signal}",
                            "count": 1,
                            "weight": weight,
                            "score": weight,
                        }
                    )

        return score, matches

    def score(self, features: dict[str, Any]) -> dict[str, Any]:

        text = self.searchable_text(features)

        b2b_score, b2b_signals = self.score_signal_group(
            text,
            B2B_SIGNALS,
        )

        b2c_score, b2c_signals = self.score_signal_group(
            text,
            B2C_SIGNALS,
        )

        media_score, media_signals = self.score_signal_group(
            text,
            MEDIA_SIGNALS,
        )

        professional_media_score, professional_media_signals = self.score_signal_group(
            text,
            PROFESSIONAL_MEDIA_SIGNALS,
        )

        education_score, education_signals = self.score_signal_group(
            text,
            EDUCATION_SIGNALS,
        )

        government_score, government_signals = self.score_signal_group(
            text,
            GOVERNMENT_SIGNALS,
        )

        nonprofit_score, nonprofit_signals = self.score_signal_group(
            text,
            NONPROFIT_SIGNALS,
        )

        b2b_url_score, b2b_url_signals = self.score_url_signals(
            features["paths"],
            B2B_URL_SIGNALS,
        )

        b2c_url_score, b2c_url_signals = self.score_url_signals(
            features["paths"],
            B2C_URL_SIGNALS,
        )

        b2b_score += b2b_url_score
        b2c_score += b2c_url_score

        ecommerce_detected = None

        for tech, weight in ECOMMERCE_TECH.items():

            if tech in features["source"]:

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

        return {
            "b2b_score": b2b_score,
            "b2c_score": b2c_score,
            "media_score": media_score,
            "professional_media_score": professional_media_score,
            "education_score": education_score,
            "government_score": government_score,
            "nonprofit_score": nonprofit_score,
            "b2b_signals": b2b_signals + b2b_url_signals,
            "b2c_signals": b2c_signals + b2c_url_signals,
            "media_signals": media_signals,
            "professional_media_signals": professional_media_signals,
            "education_signals": education_signals,
            "government_signals": government_signals,
            "nonprofit_signals": nonprofit_signals,
            "ecommerce_detected": ecommerce_detected,
        }

    @staticmethod
    def classify(
        scores: dict[str, Any],
    ) -> tuple[str, float, str]:

        b2b = scores["b2b_score"]
        b2c = scores["b2c_score"]

        business_total = b2b + b2c

        special_scores = {
            "MEDIA": scores["media_score"],
            "EDUCATION": scores["education_score"],
            "GOVERNMENT": scores["government_score"],
            "NONPROFIT": scores["nonprofit_score"],
        }

        special_type, special_score = max(
            special_scores.items(),
            key=lambda x: x[1],
        )

        professional_media = scores["professional_media_score"]

        if professional_media >= 30:

            confidence = min(
                0.99,
                professional_media / 100,
            )

            return (
                "B2B",
                round(confidence, 2),
                "PROFESSIONAL_MEDIA",
            )

        if special_type == "MEDIA" and media_is_strong(scores):

            confidence = min(
                0.99,
                special_score / 100,
            )

            return (
                "B2C",
                round(confidence, 2),
                "MEDIA",
            )

        if special_type == "EDUCATION" and special_score >= 40:

            confidence = min(
                0.99,
                special_score / 100,
            )

            return (
                "B2C",
                round(confidence, 2),
                "EDUCATION",
            )

        if special_type == "GOVERNMENT" and special_score >= 40:

            confidence = min(
                0.99,
                special_score / 100,
            )

            return (
                "B2C",
                round(confidence, 2),
                "GOVERNMENT",
            )

        if special_type == "NONPROFIT" and special_score >= 40:

            confidence = min(
                0.99,
                special_score / 100,
            )

            return (
                "B2C",
                round(confidence, 2),
                "NONPROFIT",
            )

        if business_total == 0:

            return (
                "UNKNOWN",
                0.0,
                "UNKNOWN",
            )

        difference = abs(b2b - b2c)

        if b2b >= 30 and b2c >= 30 and difference <= business_total * 0.35:

            confidence = min(
                0.99,
                business_total / 150,
            )

            return (
                "BOTH",
                round(confidence, 2),
                "BUSINESS",
            )

        if difference < 10:

            return (
                "UNKNOWN",
                round(
                    difference
                    / max(
                        business_total,
                        1,
                    ),
                    2,
                ),
                "BUSINESS",
            )

        if b2b > b2c:

            return (
                "B2B",
                round(
                    b2b / business_total,
                    2,
                ),
                "BUSINESS",
            )

        return (
            "B2C",
            round(
                b2c / business_total,
                2,
            ),
            "BUSINESS",
        )

    @staticmethod
    def guess_niche(
        features: dict[str, Any],
    ) -> dict[str, Any]:

        text = WebsiteAnalyzer.searchable_text(features)

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

        return {
            "name": best_niche,
            "confidence": round(
                min(
                    best_score / 10,
                    1.0,
                ),
                2,
            ),
            "signals": scores[best_niche]["signals"],
        }

    async def analyze(
        self,
        domain: str,
    ) -> dict[str, Any]:

        domain = self.normalize_domain(domain)

        html, final_url = await self.fetch(domain)

        features = self.extract_features(
            html,
            final_url,
        )

        scores = self.score(features)

        classification, confidence, category = self.classify(scores)

        niche = self.guess_niche(features)

        return {
            "domain": domain,
            "b2b_b2c": classification,
            "confidence": confidence,
            "category": category,
            "niche": niche,
            "confidence_signals": {
                "b2b_score": scores["b2b_score"],
                "b2c_score": scores["b2c_score"],
                "media_score": scores["media_score"],
                "professional_media_score": scores["professional_media_score"],
                "education_score": scores["education_score"],
                "government_score": scores["government_score"],
                "nonprofit_score": scores["nonprofit_score"],
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
                "top_media_signals": sorted(
                    scores["media_signals"],
                    key=lambda x: x["score"],
                    reverse=True,
                )[:10],
                "top_professional_media_signals": sorted(
                    scores["professional_media_signals"],
                    key=lambda x: x["score"],
                    reverse=True,
                )[:10],
                "ecommerce": bool(scores["ecommerce_detected"]),
                "ecommerce_platform": scores["ecommerce_detected"],
                "structured_data": features["structured_types"],
                "final_url": features["final_url"],
            },
            "error": None,
        }


def media_is_strong(
    scores: dict[str, Any],
) -> bool:

    media_score = scores["media_score"]
    professional_score = scores["professional_media_score"]

    return media_score >= 40 and media_score > professional_score


analyzer = WebsiteAnalyzer()
