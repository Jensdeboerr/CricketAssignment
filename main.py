"""
main.py — CricketScope entry point

Orchestrates the full pipeline:
    scrape -> clean -> visualise

Usage examples:
    # Scrape ODI batting only, show dashboard
    python main.py --format odi --type batting --pages 3

    # Scrape all three formats (batting + bowling) and save CSVs
    python main.py --format all --type all --pages 3 --save-csv

    # Use pre-saved CSVs (skip scraping)
    python main.py --load-csv data/processed/batting_odi.csv --type batting
"""

import argparse
import os
import pandas as pd

from cricketscope.scraper      import scrape_batting, scrape_bowling
from cricketscope.preprocessing import clean_batting, clean_bowling
from cricketscope.visualisation import save_dashboard

FORMATS    = ["test", "odi", "t20"]
PROCESSED  = "data/processed"
OUTPUT_DIR = "output"


def run_pipeline(
    fmt: str        = "odi",
    stat_type: str  = "batting",
    pages: int      = 3,
    save_csv: bool  = False,
) -> dict[str, pd.DataFrame]:
    """
    Run the full scrape -> clean pipeline for one format and stat type.

    Returns a dict with keys like 'batting_odi', 'bowling_t20', etc.
    """
    results = {}
    target_formats = FORMATS if fmt == "all" else [fmt]
    target_types   = ["batting", "bowling"] if stat_type == "all" else [stat_type]

    for f in target_formats:
        for t in target_types:
            print(f"\n{'='*50}")
            print(f"  Pipeline: {t.upper()} — {f.upper()}")
            print(f"{'='*50}")

            # 1. Scrape
            if t == "batting":
                raw = scrape_batting(fmt=f, pages=pages)
                cleaned = clean_batting(raw)
            else:
                raw = scrape_bowling(fmt=f, pages=pages)
                cleaned = clean_bowling(raw)

            key = f"{t}_{f}"
            results[key] = cleaned

            # 2. Optionally save CSV
            if save_csv:
                os.makedirs(PROCESSED, exist_ok=True)
                path = os.path.join(PROCESSED, f"{key}.csv")
                cleaned.to_csv(path, index=False)
                print(f"[main] Saved {path}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="CricketScope — scrape and visualise ESPNcricinfo stats"
    )
    parser.add_argument(
        "--format", default="odi",
        choices=["test", "odi", "t20", "all"],
        help="Format to scrape. Use 'all' for all three. (default: odi)"
    )
    parser.add_argument(
        "--type", default="batting",
        choices=["batting", "bowling", "all"],
        dest="stat_type",
        help="Stat type to scrape. Use 'all' for both. (default: batting)"
    )
    parser.add_argument(
        "--pages", type=int, default=3,
        help="Pages per request (25 rows/page). (default: 3)"
    )
    parser.add_argument(
        "--save-csv", action="store_true",
        help="Save cleaned DataFrames as CSVs to data/processed/"
    )
    parser.add_argument(
        "--load-csv", default=None,
        help="Skip scraping — load a pre-saved cleaned CSV instead."
    )
    parser.add_argument(
        "--no-plot", action="store_true",
        help="Skip dashboard generation."
    )
    args = parser.parse_args()

    # --- Load or scrape ---
    if args.load_csv:
        print(f"[main] Loading from {args.load_csv}")
        df = pd.read_csv(args.load_csv)
        results = {f"{args.stat_type}_{args.format}": df}
    else:
        results = run_pipeline(
            fmt=args.format,
            stat_type=args.stat_type,
            pages=args.pages,
            save_csv=args.save_csv,
        )

    # --- Visualise ---
    if not args.no_plot:
        batting_odi  = results.get("batting_odi")
        batting_test = results.get("batting_test")
        batting_t20  = results.get("batting_t20")

        if batting_odi is not None:
            save_dashboard(
                batting_odi=batting_odi,
                batting_test=batting_test,
                batting_t20=batting_t20,
                output_path=os.path.join(OUTPUT_DIR, "dashboard.png"),
            )
        else:
            print("[main] No ODI batting data — skipping dashboard. "
                  "Run with --format odi --type batting to generate it.")


if __name__ == "__main__":
    main()
