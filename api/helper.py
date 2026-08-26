import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from utils.config import settings
from .kewords_classify import (
    B2B_SIGNALS,
    B2C_SIGNALS,
    B2B_URL_SIGNALS,
    B2C_URL_SIGNALS,
    ECOMMERCE_TECH,
    MEDIA_SIGNALS,
    PROFESSIONAL_MEDIA_SIGNALS,
    EDUCATION_SIGNALS,
    GOVERNMENT_SIGNALS,
    NONPROFIT_SIGNALS,
    MEDIA_URL_SIGNALS,
    EDUCATION_URL_SIGNALS,
    GOVERNMENT_URL_SIGNALS,
    NICHE_KEYWORDS,
)


SPECIAL_SIGNAL_GROUPS = {
    "MEDIA": MEDIA_SIGNALS,
    "PROFESSIONAL_MEDIA": PROFESSIONAL_MEDIA_SIGNALS,
    "EDUCATION": EDUCATION_SIGNALS,
    "GOVERNMENT": GOVERNMENT_SIGNALS,
    "NONPROFIT": NONPROFIT_SIGNALS,
}


class WebsiteAnalyzer:

    def __init__(self):
        self.timeout = settings.REQUEST_TIMEOUT
        self.max_response_size = settings.MAX_RESPONSE_SIZE
        self.user_agent = settings.USER_AGENT

    @staticmethod
    def normalize_domain(domain: str) -> str:
        domain = str(domain or "").strip().lower()

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

        domain = domain.split("/")[0]

        return domain.rstrip("/")

    @staticmethod
    def normalize_text(text: str) -> str:
        text = str(text or "").lower()

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

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

    def extract_features(
        self,
        html: str,
        final_url: str,
    ) -> dict[str, Any]:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        for tag in soup(
            [
                "script",
                "style",
                "noscript",
                "svg",
                "iframe",
            ]
        ):
            tag.decompose()

        text = self.normalize_text(
            soup.get_text(
                " ",
                strip=True,
            )[:100_000]
        )

        title = ""

        if soup.title:
            title = self.normalize_text(
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            )

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
            meta_description = self.normalize_text(
                meta.get(
                    "content",
                    "",
                )
            )

        headings = self.normalize_text(
            " ".join(
                h.get_text(
                    " ",
                    strip=True,
                )
                for h in soup.find_all(
                    [
                        "h1",
                        "h2",
                        "h3",
                    ]
                )
            )
        )

        links = []

        for link in soup.find_all(
            "a",
            href=True,
        ):
            href = str(
                link.get(
                    "href",
                    "",
                )
            ).lower()

            anchor = self.normalize_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

            links.append(
                {
                    "href": href,
                    "anchor": anchor,
                }
            )

        structured_types = []

        for script in soup.find_all(
            "script",
            type="application/ld+json",
        ):

            try:
                raw = script.string or ""
                data = json.loads(raw)

                items = data if isinstance(data, list) else [data]

                for item in items:

                    if not isinstance(item, dict):
                        continue

                    item_type = item.get("@type")

                    if isinstance(
                        item_type,
                        list,
                    ):
                        structured_types.extend(str(x).lower() for x in item_type)

                    elif item_type:
                        structured_types.append(str(item_type).lower())

            except Exception:
                continue

        paths = []

        for link in links:

            href = link["href"]

            if href.startswith("/"):
                paths.append(href.split("?")[0].lower())

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

    @classmethod
    def searchable_text(
        cls,
        features: dict[str, Any],
    ) -> str:

        return cls.normalize_text(
            " ".join(
                [
                    features.get("text", ""),
                    features.get("title", ""),
                    features.get("meta_description", ""),
                    features.get("headings", ""),
                ]
            )
        )

    @classmethod
    def score_signal_group(
        cls,
        text: str,
        signals: dict[str, int],
        prefix: str = "",
    ) -> tuple[float, list[dict[str, Any]]]:

        score = 0
        matches = []

        for keyword, weight in signals.items():

            keyword = cls.normalize_text(keyword)

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
                    "signal": f"{prefix}{keyword}",
                    "count": count,
                    "weight": weight,
                    "score": signal_score,
                }
            )

        return score, matches

    @staticmethod
    def score_url_signals(
        paths: list[str],
        signals: dict[str, int],
    ) -> tuple[float, list[dict[str, Any]]]:

        score = 0
        matches = []

        for path in paths:

            path = path.lower()

            for signal, weight in signals.items():

                signal = signal.lower()

                if (
                    path == signal
                    or path.startswith(signal + "/")
                    or path.startswith(signal + "?")
                ):

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

    def score(
        self,
        features: dict[str, Any],
    ) -> dict[str, Any]:

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

        media_url_score, media_url_signals = self.score_url_signals(
            features["paths"],
            MEDIA_URL_SIGNALS,
        )

        education_url_score, education_url_signals = self.score_url_signals(
            features["paths"],
            EDUCATION_URL_SIGNALS,
        )

        government_url_score, government_url_signals = self.score_url_signals(
            features["paths"],
            GOVERNMENT_URL_SIGNALS,
        )

        b2b_score += b2b_url_score
        b2c_score += b2c_url_score
        media_score += media_url_score
        education_score += education_url_score
        government_score += government_url_score

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

        ecommerce_detected = None

        for tech, weight in ECOMMERCE_TECH.items():

            if tech.lower() in features["source"]:

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
            "media_signals": media_signals + media_url_signals,
            "professional_media_signals": professional_media_signals,
            "education_signals": education_signals + education_url_signals,
            "government_signals": government_signals + government_url_signals,
            "nonprofit_signals": nonprofit_signals,
            "ecommerce_detected": ecommerce_detected,
        }

    @staticmethod
    def classify(
        scores: dict[str, Any],
    ) -> tuple[str, float, str]:

        b2b = float(
            scores.get(
                "b2b_score",
                0,
            )
        )

        b2c = float(
            scores.get(
                "b2c_score",
                0,
            )
        )

        media = float(
            scores.get(
                "media_score",
                0,
            )
        )

        professional_media = float(
            scores.get(
                "professional_media_score",
                0,
            )
        )

        education = float(
            scores.get(
                "education_score",
                0,
            )
        )

        government = float(
            scores.get(
                "government_score",
                0,
            )
        )

        nonprofit = float(
            scores.get(
                "nonprofit_score",
                0,
            )
        )

        business_total = b2b + b2c

        special_scores = {
            "MEDIA": media,
            "EDUCATION": education,
            "GOVERNMENT": government,
            "NONPROFIT": nonprofit,
        }

        special_type, special_score = max(
            special_scores.items(),
            key=lambda item: item[1],
        )

        if professional_media >= 30:

            confidence = min(
                0.99,
                0.60 + professional_media / 150,
            )

            return (
                "B2B",
                round(confidence, 2),
                "PROFESSIONAL_MEDIA",
            )

        if special_type == "MEDIA" and media >= 40 and media > professional_media:

            confidence = min(
                0.99,
                0.60 + media / 180,
            )

            return (
                "B2C",
                round(confidence, 2),
                "MEDIA",
            )

        if special_type == "EDUCATION" and education >= 40:

            confidence = min(
                0.99,
                0.60 + education / 180,
            )

            return (
                "B2C",
                round(confidence, 2),
                "EDUCATION",
            )

        if special_type == "GOVERNMENT" and government >= 40:

            confidence = min(
                0.99,
                0.60 + government / 180,
            )

            return (
                "B2C",
                round(confidence, 2),
                "GOVERNMENT",
            )

        if special_type == "NONPROFIT" and nonprofit >= 40:

            confidence = min(
                0.99,
                0.60 + nonprofit / 180,
            )

            return (
                "B2C",
                round(confidence, 2),
                "NONPROFIT",
            )

        if business_total <= 0:

            return (
                "UNKNOWN",
                0.0,
                "LOW_EVIDENCE",
            )

        difference = abs(b2b - b2c)

        dominant_score = max(
            b2b,
            b2c,
        )

        dominance = difference / business_total

        relative_confidence = dominant_score / business_total

        # Strong evidence on both sides
        if b2b >= 35 and b2c >= 35 and dominance <= 0.30:

            confidence = min(
                0.99,
                0.65 + business_total / 300,
            )

            return (
                "BOTH",
                round(confidence, 2),
                "BUSINESS",
            )

        # Very low evidence
        if business_total < 15:

            return (
                "UNKNOWN",
                round(
                    min(
                        0.49,
                        business_total / 30,
                    ),
                    2,
                ),
                "LOW_EVIDENCE",
            )

        # Balanced but enough evidence
        # Instead of immediately UNKNOWN when difference < 10
        if dominance < 0.12:

            if b2b >= 20 and b2c >= 20:

                return (
                    "BOTH",
                    round(
                        min(
                            0.85,
                            0.55 + business_total / 250,
                        ),
                        2,
                    ),
                    "BALANCED_BUSINESS",
                )

            return (
                "UNKNOWN",
                round(
                    max(
                        0.35,
                        relative_confidence,
                    ),
                    2,
                ),
                "AMBIGUOUS",
            )

        # B2B
        if b2b > b2c:

            confidence = min(
                0.99,
                0.50 + dominance * 0.60 + min(b2b / 300, 0.20),
            )

            return (
                "B2B",
                round(
                    confidence,
                    2,
                ),
                "BUSINESS",
            )

        # B2C
        confidence = min(
            0.99,
            0.50 + dominance * 0.60 + min(b2c / 300, 0.20),
        )

        return (
            "B2C",
            round(
                confidence,
                2,
            ),
            "BUSINESS",
        )

    @classmethod
    def guess_niche(
        cls,
        features: dict[str, Any],
    ) -> dict[str, Any]:

        text = cls.searchable_text(features)

        scores = {}

        for niche, keywords in NICHE_KEYWORDS.items():

            score = 0
            matched = []

            for keyword in keywords:

                count = text.count(cls.normalize_text(keyword))

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

        ranked = sorted(
            scores.items(),
            key=lambda item: item[1]["score"],
            reverse=True,
        )

        best_niche, best_data = ranked[0]

        best_score = best_data["score"]

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
            "signals": best_data["signals"],
        }

    async def analyze(
        self,
        domain: str,
    ) -> dict[str, Any]:

        domain = self.normalize_domain(domain)

        result = {
            "domain": domain,
            "b2b_b2c": "UNKNOWN",
            "confidence": 0.0,
            "category": "UNKNOWN",
            "niche": None,
            "confidence_signals": {},
            "error": None,
        }

        try:

            html, final_url = await self.fetch(domain)

            features = self.extract_features(
                html,
                final_url,
            )

            scores = self.score(features)

            classification, confidence, category = self.classify(scores)

            niche = self.guess_niche(features)

            result.update(
                {
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
                }
            )

        except Exception as exc:

            result["error"] = str(exc)

        return result


analyzer = WebsiteAnalyzer()
