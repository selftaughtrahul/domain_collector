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

    # ============================================================
    # NORMALIZATION
    # ============================================================

    @staticmethod
    def normalize_domain(domain: str) -> str:
        """
        Normalize a domain.

        Example:
            https://www.example.com/test
            ->
            example.com
        """

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
        """
        Normalize text for keyword matching.
        """

        text = str(text or "").lower()

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    @staticmethod
    def normalize_path(path: str) -> str:
        """
        Normalize URL paths.

        Examples:
            /blog/
            blog
            /blog?x=1

        become:

            /blog
        """

        path = str(path or "").strip().lower()

        if not path:
            return "/"

        path = path.split("?")[0]
        path = path.split("#")[0]

        if not path.startswith("/"):
            path = "/" + path

        path = re.sub(
            r"/+",
            "/",
            path,
        )

        if len(path) > 1:
            path = path.rstrip("/")

        return path

    # ============================================================
    # FETCH WEBSITE
    # ============================================================

    async def fetch(
        self,
        domain: str,
    ) -> tuple[str, str]:

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

                    return (
                        html,
                        str(response.url),
                    )

                except Exception as exc:

                    last_error = exc

        raise RuntimeError(f"Could not reach domain: {last_error}")

    # ============================================================
    # EXTRACT FEATURES
    # ============================================================

    def extract_features(
        self,
        html: str,
        final_url: str,
    ) -> dict[str, Any]:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        # --------------------------------------------------------
        # Remove non-visible content
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Main text
        # --------------------------------------------------------

        text = self.normalize_text(
            soup.get_text(
                " ",
                strip=True,
            )[:100_000]
        )

        # --------------------------------------------------------
        # Title
        # --------------------------------------------------------

        title = ""

        if soup.title:

            title = self.normalize_text(
                soup.title.get_text(
                    " ",
                    strip=True,
                )
            )

        # --------------------------------------------------------
        # Meta description
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Headings
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Links
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Structured data
        # --------------------------------------------------------

        structured_types = []

        for script in soup.find_all(
            "script",
            type="application/ld+json",
        ):

            try:

                raw = script.string or ""

                if not raw:
                    continue

                data = json.loads(raw)

                items = data if isinstance(data, list) else [data]

                for item in items:

                    if not isinstance(
                        item,
                        dict,
                    ):
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

        # --------------------------------------------------------
        # URL paths
        # --------------------------------------------------------

        paths = []

        for link in links:

            href = link["href"]

            # Relative URL
            if href.startswith("/"):

                path = self.normalize_path(href)

                paths.append(path)

        return {
            "text": text,
            "title": title,
            "meta_description": meta_description,
            "headings": headings,
            "source": html.lower(),
            "links": links,
            "paths": list(set(paths)),
            "structured_types": structured_types,
            "final_url": final_url,
        }

    # ============================================================
    # SEARCHABLE TEXT
    # ============================================================

    @classmethod
    def searchable_text(
        cls,
        features: dict[str, Any],
    ) -> str:

        return cls.normalize_text(
            " ".join(
                [
                    features.get(
                        "text",
                        "",
                    ),
                    features.get(
                        "title",
                        "",
                    ),
                    features.get(
                        "meta_description",
                        "",
                    ),
                    features.get(
                        "headings",
                        "",
                    ),
                ]
            )
        )

    # ============================================================
    # TEXT SIGNAL SCORING
    # ============================================================

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

            if not keyword:
                continue

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

        return (
            score,
            matches,
        )

    # ============================================================
    # URL SIGNAL SCORING
    # ============================================================

    @classmethod
    def score_url_signals(
        cls,
        paths: list[str],
        signals: dict[str, int],
    ) -> tuple[float, list[dict[str, Any]]]:

        score = 0
        matches = []

        normalized_paths = [cls.normalize_path(path) for path in paths]

        for path in normalized_paths:

            for signal, weight in signals.items():

                signal = cls.normalize_path(signal)

                if signal == "/":
                    continue

                # Exact path
                matched = path == signal or path.startswith(signal + "/")

                if not matched:
                    continue

                score += weight

                matches.append(
                    {
                        "signal": f"url:{signal}",
                        "count": 1,
                        "weight": weight,
                        "score": weight,
                        "path": path,
                    }
                )

        return (
            score,
            matches,
        )

    # ============================================================
    # SCORE WEBSITE
    # ============================================================

    def score(
        self,
        features: dict[str, Any],
    ) -> dict[str, Any]:

        text = self.searchable_text(features)

        # --------------------------------------------------------
        # B2B
        # --------------------------------------------------------

        b2b_score, b2b_signals = self.score_signal_group(
            text,
            B2B_SIGNALS,
        )

        # --------------------------------------------------------
        # B2C
        # --------------------------------------------------------

        b2c_score, b2c_signals = self.score_signal_group(
            text,
            B2C_SIGNALS,
        )

        # --------------------------------------------------------
        # MEDIA
        # --------------------------------------------------------

        media_score, media_signals = self.score_signal_group(
            text,
            MEDIA_SIGNALS,
        )

        # --------------------------------------------------------
        # PROFESSIONAL MEDIA
        # --------------------------------------------------------

        (
            professional_media_score,
            professional_media_signals,
        ) = self.score_signal_group(
            text,
            PROFESSIONAL_MEDIA_SIGNALS,
        )

        # --------------------------------------------------------
        # EDUCATION
        # --------------------------------------------------------

        education_score, education_signals = self.score_signal_group(
            text,
            EDUCATION_SIGNALS,
        )

        # --------------------------------------------------------
        # GOVERNMENT
        # --------------------------------------------------------

        government_score, government_signals = self.score_signal_group(
            text,
            GOVERNMENT_SIGNALS,
        )

        # --------------------------------------------------------
        # NONPROFIT
        # --------------------------------------------------------

        nonprofit_score, nonprofit_signals = self.score_signal_group(
            text,
            NONPROFIT_SIGNALS,
        )

        # ========================================================
        # URL SCORES
        # ========================================================

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

        # --------------------------------------------------------
        # Add URL scores
        # --------------------------------------------------------

        b2b_score += b2b_url_score
        b2c_score += b2c_url_score
        media_score += media_url_score
        education_score += education_url_score
        government_score += government_url_score

        # ========================================================
        # STRUCTURED DATA
        # ========================================================

        structured_types = set(str(x).lower() for x in features["structured_types"])

        # --------------------------------------------------------
        # Product
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # Offer
        # --------------------------------------------------------

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

        # ========================================================
        # E-COMMERCE TECHNOLOGY
        # ========================================================

        ecommerce_detected = None

        ecommerce_matches = []

        for tech, weight in ECOMMERCE_TECH.items():

            if tech.lower() not in features["source"]:
                continue

            ecommerce_detected = tech

            b2c_score += weight

            match = {
                "signal": f"technology:{tech}",
                "count": 1,
                "weight": weight,
                "score": weight,
            }

            b2c_signals.append(match)
            ecommerce_matches.append(match)

        # ========================================================
        # RETURN SCORES
        # ========================================================

        return {
            # Business scores
            "b2b_score": b2b_score,
            "b2c_score": b2c_score,
            # Website type scores
            "media_score": media_score,
            "professional_media_score": professional_media_score,
            "education_score": education_score,
            "government_score": government_score,
            "nonprofit_score": nonprofit_score,
            # Signals
            "b2b_signals": (b2b_signals + b2b_url_signals),
            "b2c_signals": (b2c_signals + b2c_url_signals),
            "media_signals": (media_signals + media_url_signals),
            "professional_media_signals": (professional_media_signals),
            "education_signals": (education_signals + education_url_signals),
            "government_signals": (government_signals + government_url_signals),
            "nonprofit_signals": (nonprofit_signals),
            # Ecommerce
            "ecommerce_detected": ecommerce_detected,
            "ecommerce_matches": ecommerce_matches,
        }

    # ============================================================
    # WEBSITE TYPE CLASSIFICATION
    # ============================================================

    @staticmethod
    def classify_website_type(
        scores: dict[str, Any],
    ) -> tuple[str, float]:

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

        website_scores = {
            "MEDIA": media,
            "PROFESSIONAL_MEDIA": professional_media,
            "EDUCATION": education,
            "GOVERNMENT": government,
            "NONPROFIT": nonprofit,
        }

        website_type, score = max(
            website_scores.items(),
            key=lambda item: item[1],
        )

        # --------------------------------------------------------
        # No meaningful special evidence
        # --------------------------------------------------------

        if score < 30:

            return (
                "BUSINESS",
                0.0,
            )

        # --------------------------------------------------------
        # Confidence
        # --------------------------------------------------------

        confidence = min(
            0.99,
            0.60 + score / 180,
        )

        return (
            website_type,
            round(
                confidence,
                2,
            ),
        )

    # ============================================================
    # BUSINESS MODEL CLASSIFICATION
    # ============================================================

    @staticmethod
    def classify_business_model(
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

        business_total = b2b + b2c

        # --------------------------------------------------------
        # No evidence
        # --------------------------------------------------------

        if business_total <= 0:

            return (
                "UNKNOWN",
                0.0,
                "LOW_EVIDENCE",
            )

        # --------------------------------------------------------
        # Very low evidence
        # --------------------------------------------------------

        if business_total < 15:

            confidence = min(
                0.49,
                business_total / 30,
            )

            return (
                "UNKNOWN",
                round(
                    confidence,
                    2,
                ),
                "LOW_EVIDENCE",
            )

        difference = abs(b2b - b2c)

        dominant_score = max(
            b2b,
            b2c,
        )

        dominance = difference / business_total

        relative_confidence = dominant_score / business_total

        # ========================================================
        # BOTH
        # ========================================================

        if b2b >= 35 and b2c >= 35 and dominance <= 0.30:

            confidence = min(
                0.99,
                0.65 + business_total / 300,
            )

            return (
                "BOTH",
                round(
                    confidence,
                    2,
                ),
                "STRONG_BOTH",
            )

        # ========================================================
        # BALANCED
        # ========================================================

        if dominance < 0.12:

            if b2b >= 20 and b2c >= 20:

                confidence = min(
                    0.85,
                    0.55 + business_total / 250,
                )

                return (
                    "BOTH",
                    round(
                        confidence,
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

        # ========================================================
        # B2B
        # ========================================================

        if b2b > b2c:

            confidence = min(
                0.99,
                0.50
                + dominance * 0.60
                + min(
                    b2b / 300,
                    0.20,
                ),
            )

            return (
                "B2B",
                round(
                    confidence,
                    2,
                ),
                "BUSINESS",
            )

        # ========================================================
        # B2C
        # ========================================================

        confidence = min(
            0.99,
            0.50
            + dominance * 0.60
            + min(
                b2c / 300,
                0.20,
            ),
        )

        return (
            "B2C",
            round(
                confidence,
                2,
            ),
            "BUSINESS",
        )

    # ============================================================
    # NICHE CLASSIFICATION
    # ============================================================

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

                normalized_keyword = cls.normalize_text(keyword)

                if not normalized_keyword:
                    continue

                count = text.count(normalized_keyword)

                if count <= 0:
                    continue

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

        # --------------------------------------------------------
        # No niche found
        # --------------------------------------------------------

        if not scores:

            return {
                "name": None,
                "confidence": 0.0,
                "signals": [],
            }

        # --------------------------------------------------------
        # Rank niches
        # --------------------------------------------------------

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

    # ============================================================
    # MAIN ANALYZE METHOD
    # ============================================================

    async def analyze(
        self,
        domain: str,
    ) -> dict[str, Any]:

        domain = self.normalize_domain(domain)

        # --------------------------------------------------------
        # Default result
        # --------------------------------------------------------

        result = {
            "domain": domain,
            # Business model
            "b2b_b2c": "UNKNOWN",
            "business_model": "UNKNOWN",
            "business_confidence": 0.0,
            # Website type
            "website_type": "UNKNOWN",
            "website_type_confidence": 0.0,
            # Backward-compatible category field
            "category": "UNKNOWN",
            # Niche
            "niche": None,
            # Debug
            "confidence_signals": {},
            # Error
            "error": None,
        }

        try:

            # ====================================================
            # FETCH
            # ====================================================

            html, final_url = await self.fetch(domain)

            # ====================================================
            # FEATURES
            # ====================================================

            features = self.extract_features(
                html,
                final_url,
            )

            # ====================================================
            # SCORES
            # ====================================================

            scores = self.score(features)

            # ====================================================
            # WEBSITE TYPE
            # ====================================================

            (
                website_type,
                website_type_confidence,
            ) = self.classify_website_type(scores)

            # ====================================================
            # BUSINESS MODEL
            # ====================================================

            (
                business_model,
                business_confidence,
                business_reason,
            ) = self.classify_business_model(scores)

            # ====================================================
            # NICHE
            # ====================================================

            niche = self.guess_niche(features)

            # ====================================================
            # FINAL RESULT
            # ====================================================

            result.update(
                {
                    # Business model
                    "b2b_b2c": business_model,
                    "business_model": (business_model),
                    "business_confidence": (business_confidence),
                    # Website type
                    "website_type": (website_type),
                    "website_type_confidence": (website_type_confidence),
                    # Backward-compatible category
                    "category": (website_type),
                    # Niche
                    "niche": niche,
                    # Debug signals
                    "confidence_signals": {
                        # ----------------------------
                        # Raw scores
                        # ----------------------------
                        "b2b_score": (scores["b2b_score"]),
                        "b2c_score": (scores["b2c_score"]),
                        "media_score": (scores["media_score"]),
                        "professional_media_score": (
                            scores["professional_media_score"]
                        ),
                        "education_score": (scores["education_score"]),
                        "government_score": (scores["government_score"]),
                        "nonprofit_score": (scores["nonprofit_score"]),
                        # ----------------------------
                        # Classification reasons
                        # ----------------------------
                        "business_reason": (business_reason),
                        # ----------------------------
                        # Top B2B signals
                        # ----------------------------
                        "top_b2b_signals": sorted(
                            scores["b2b_signals"],
                            key=lambda x: x["score"],
                            reverse=True,
                        )[:10],
                        # ----------------------------
                        # Top B2C signals
                        # ----------------------------
                        "top_b2c_signals": sorted(
                            scores["b2c_signals"],
                            key=lambda x: x["score"],
                            reverse=True,
                        )[:10],
                        # ----------------------------
                        # Top media signals
                        # ----------------------------
                        "top_media_signals": sorted(
                            scores["media_signals"],
                            key=lambda x: x["score"],
                            reverse=True,
                        )[:10],
                        # ----------------------------
                        # Professional media
                        # ----------------------------
                        "top_professional_media_signals": sorted(
                            scores["professional_media_signals"],
                            key=lambda x: x["score"],
                            reverse=True,
                        )[:10],
                        # ----------------------------
                        # Education
                        # ----------------------------
                        "top_education_signals": sorted(
                            scores["education_signals"],
                            key=lambda x: x["score"],
                            reverse=True,
                        )[:10],
                        # ----------------------------
                        # Government
                        # ----------------------------
                        "top_government_signals": sorted(
                            scores["government_signals"],
                            key=lambda x: x["score"],
                            reverse=True,
                        )[:10],
                        # ----------------------------
                        # Nonprofit
                        # ----------------------------
                        "top_nonprofit_signals": sorted(
                            scores["nonprofit_signals"],
                            key=lambda x: x["score"],
                            reverse=True,
                        )[:10],
                        # ----------------------------
                        # Ecommerce
                        # ----------------------------
                        "ecommerce": bool(scores["ecommerce_detected"]),
                        "ecommerce_platform": (scores["ecommerce_detected"]),
                        # ----------------------------
                        # Structured data
                        # ----------------------------
                        "structured_data": (features["structured_types"]),
                        # ----------------------------
                        # URL
                        # ----------------------------
                        "final_url": (features["final_url"]),
                    },
                }
            )

        except Exception as exc:

            result["error"] = str(exc)

        return result


# ================================================================
# SINGLETON
# ================================================================

# analyzer = WebsiteAnalyzer()
