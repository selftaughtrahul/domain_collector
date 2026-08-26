"""
classify_batch.py
=================

Run the classifier over a list of domains and print WHY each one got its
label. Use this every time you add patterns — it's the fastest way to see
whether a change helped or quietly broke something else.

    python -m classifier.classify_batch domains.txt
    python -m classifier.classify_batch domains.txt --csv out.csv
    python -m classifier.classify_batch reisreporter.be conjur.com.br
    python -m classifier.classify_batch domains.txt --shallow    # homepage only
    python -m classifier.classify_batch domains.txt --explain    # per-domain signals

The REASON column is the important one. It tells you which branch of the
decision layer fired:

    COMMERCIAL_SIGNALS      real buying/selling language decided it
    ECOMMERCE_PLATFORM      Shopify/VTEX/WooCommerce etc. detected
    AUDIENCE_FROM_MEDIA     no commercial motion, but it's clearly a publisher
    AUDIENCE_FROM_*         same idea for education / government / nonprofit
    WEAK_EVIDENCE           a hint only — treat as low confidence
    THIN_CONTENT            page is JS-rendered or bot-walled; nothing to read
    FETCH_FAILED            we never got the page
    NO_EVIDENCE             we read it and found nothing at all (rare now)

If you see lots of THIN_CONTENT or FETCH_FAILED, the fix is rendering or
headers — not more keywords.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from pathlib import Path

try:
    from .website_analyzer import analyzer
except ImportError:  # running the file directly
    from website_analyzer import analyzer  # type: ignore


def load_domains(args: list[str]) -> list[str]:
    domains: list[str] = []
    for item in args:
        path = Path(item)
        if path.exists():
            domains.extend(
                line.strip() for line in path.read_text().splitlines() if line.strip()
            )
        else:
            domains.append(item)
    return [d for d in domains if not d.startswith("#")]


def print_table(results: list[dict]) -> None:
    width = max((len(r["domain"]) for r in results), default=10) + 2
    header = (
        f"{'DOMAIN':<{width}}{'MODEL':<17}{'CONF':<7}"
        f"{'REASON':<27}{'TYPE':<15}{'NICHE':<14}PAGES"
    )
    print(header)
    print("-" * len(header))

    for r in results:
        niche = (r.get("niche") or {}).get("name") or "-"
        print(
            f"{r['domain']:<{width}}"
            f"{r['business_model']:<17}"
            f"{r['business_confidence']:<7}"
            f"{r.get('business_reason', '-'):<27}"
            f"{r['website_type']:<15}"
            f"{niche:<14}"
            f"{r.get('pages_analyzed', 0)}"
        )
        if r.get("error"):
            print(f"{'':<{width}}  ! {r['error'][:100]}")

    print()
    summary: dict[str, int] = {}
    for r in results:
        summary[r["business_model"]] = summary.get(r["business_model"], 0) + 1
    print("  ".join(f"{k}={v}" for k, v in sorted(summary.items())))


def print_explanations(results: list[dict]) -> None:
    for r in results:
        signals = r.get("confidence_signals", {})
        print("\n" + "=" * 72)
        print(f"{r['domain']}  ->  {r['business_model']} ({r['business_confidence']})")
        print("=" * 72)
        if r.get("error"):
            print(f"  error: {r['error']}")
            continue
        print(f"  scores   : {signals.get('scores')}")
        print(f"  coverage : {signals.get('coverage')}")
        print(
            f"  language : {r.get('language')}   text: {signals.get('text_length')} chars"
        )
        for key in ("top_b2b_signals", "top_b2c_signals", "top_media_signals"):
            top = signals.get(key) or []
            if top:
                shown = ", ".join(f"{m['signal']}({m['score']})" for m in top[:6])
                print(
                    f"  {key.replace('top_', '').replace('_signals', ''):<12}: {shown}"
                )


def write_csv(results: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "domain",
                "business_model",
                "confidence",
                "reason",
                "website_type",
                "type_confidence",
                "niche",
                "pages",
                "error",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r["domain"],
                    r["business_model"],
                    r["business_confidence"],
                    r.get("business_reason", ""),
                    r["website_type"],
                    r["website_type_confidence"],
                    (r.get("niche") or {}).get("name") or "",
                    r.get("pages_analyzed", 0),
                    r.get("error") or "",
                ]
            )
    print(f"\nwrote {path}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch website classifier")
    parser.add_argument("inputs", nargs="+", help="domains, or a file of domains")
    parser.add_argument("--csv", help="also write results to this CSV")
    parser.add_argument(
        "--shallow", action="store_true", help="homepage only, no crawl"
    )
    parser.add_argument("--explain", action="store_true", help="print matched signals")
    parser.add_argument("--concurrency", type=int, default=8)
    args = parser.parse_args()

    domains = load_domains(args.inputs)
    if not domains:
        sys.exit("no domains given")

    print(
        f"classifying {len(domains)} domains "
        f"({'homepage only' if args.shallow else 'with deep crawl'})...\n"
    )

    results = await analyzer.analyze_many(
        domains, concurrency=args.concurrency, deep=not args.shallow
    )

    print_table(results)
    if args.explain:
        print_explanations(results)
    if args.csv:
        write_csv(results, args.csv)


if __name__ == "__main__":
    asyncio.run(main())
