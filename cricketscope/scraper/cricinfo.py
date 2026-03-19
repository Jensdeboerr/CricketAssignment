"""
scraper/cricinfo.py

Scrapes player batting and bowling statistics from the ESPNcricinfo
stats engine (stats.espncricinfo.com). Uses requests + BeautifulSoup
only — no API, no headless browser required for this endpoint.

Supported formats:
    1 = Test
    2 = ODI
    3 = T20I

Usage (standalone):
    python -m cricketscope.scraper.cricinfo --format 2 --type batting --pages 2
"""

import time
import argparse
import requests
from bs4 import BeautifulSoup
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://stats.espncricinfo.com/ci/engine/stats/index.html"

FORMAT_MAP = {
    "test": "1",
    "odi":  "2",
    "t20":  "3",
}

HEADERS = {
    # Polite browser-like header to avoid 403s
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Seconds to wait between paginated requests — be a polite scraper
REQUEST_DELAY = 2.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_params(fmt_code: str, stat_type: str, page: int) -> dict:
    """Return the query-string parameters for one stats-engine request."""
    return {
        "class":    fmt_code,
        "type":     stat_type,       # "batting" or "bowling"
        "template": "results",
        "orderby":  "runs" if stat_type == "batting" else "wickets",
        "page":     str(page),
    }


def _fetch_page(params: dict) -> BeautifulSoup | None:
    """
    Fetch one page from the stats engine and return a BeautifulSoup object.
    Returns None if the request fails or no data table is found.
    """
    try:
        response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"[scraper] Request failed: {exc}")
        return None

    soup = BeautifulSoup(response.text, "lxml")

    # The stats engine wraps data in a table with class "engineTable"
    if not soup.find("table", class_="engineTable"):
        print("[scraper] No data table found on page — likely past last page.")
        return None

    return soup


def _parse_batting_table(soup: BeautifulSoup) -> list[dict]:
    """
    Parse the batting stats table from a BeautifulSoup page.

    Columns extracted:
        player_name, country, span, matches, innings, not_outs,
        runs, high_score, batting_avg, balls_faced, strike_rate,
        hundreds, fifties, ducks
    """
    rows = []
    table = soup.find("table", class_="engineTable")
    if table is None:
        return rows

    # Header row tells us column positions — don't hard-code indices
    headers = [th.get_text(strip=True) for th in table.find_all("th")]

    for tr in table.find_all("tr", class_=["data1", "data2"]):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < len(headers):
            continue

        row = dict(zip(headers, cells))

        # Normalise key names to snake_case
        rows.append({
            "player_name":  row.get("Player", ""),
            "country":      row.get("Country", ""),
            "span":         row.get("Span", ""),
            "matches":      row.get("Mat", ""),
            "innings":      row.get("Inns", ""),
            "not_outs":     row.get("NO", ""),
            "runs":         row.get("Runs", ""),
            "high_score":   row.get("HS", ""),
            "batting_avg":  row.get("Ave", ""),
            "balls_faced":  row.get("BF", ""),
            "strike_rate":  row.get("SR", ""),
            "hundreds":     row.get("100", ""),
            "fifties":      row.get("50", ""),
            "ducks":        row.get("0", ""),
        })

    return rows


def _parse_bowling_table(soup: BeautifulSoup) -> list[dict]:
    """
    Parse the bowling stats table from a BeautifulSoup page.

    Columns extracted:
        player_name, country, span, matches, innings, overs,
        maidens, runs_conceded, wickets, bowling_avg,
        economy, strike_rate, four_wkt, five_wkt, ten_wkt
    """
    rows = []
    table = soup.find("table", class_="engineTable")
    if table is None:
        return rows

    headers = [th.get_text(strip=True) for th in table.find_all("th")]

    for tr in table.find_all("tr", class_=["data1", "data2"]):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < len(headers):
            continue

        row = dict(zip(headers, cells))

        rows.append({
            "player_name":    row.get("Player", ""),
            "country":        row.get("Country", ""),
            "span":           row.get("Span", ""),
            "matches":        row.get("Mat", ""),
            "innings":        row.get("Inns", ""),
            "overs":          row.get("Overs", ""),
            "maidens":        row.get("Mdns", ""),
            "runs_conceded":  row.get("Runs", ""),
            "wickets":        row.get("Wkts", ""),
            "bowling_avg":    row.get("Ave", ""),
            "economy":        row.get("Econ", ""),
            "strike_rate":    row.get("SR", ""),
            "four_wkt":       row.get("4", ""),
            "five_wkt":       row.get("5", ""),
            "ten_wkt":        row.get("10", ""),
        })

    return rows


# ---------------------------------------------------------------------------
# Public functions (imported by other modules)
# ---------------------------------------------------------------------------

def scrape_batting(fmt: str = "odi", pages: int = 3) -> pd.DataFrame:
    """
    Scrape batting statistics for the given format.

    Args:
        fmt:   One of 'test', 'odi', 't20'. Defaults to 'odi'.
        pages: Number of paginated result pages to fetch (25 rows each).

    Returns:
        pd.DataFrame with one row per player.
    """
    fmt_code = FORMAT_MAP.get(fmt.lower())
    if fmt_code is None:
        raise ValueError(f"Unknown format '{fmt}'. Choose from: {list(FORMAT_MAP)}")

    all_rows = []
    for page in range(1, pages + 1):
        print(f"[scraper] Fetching batting {fmt.upper()} — page {page}/{pages}")
        params = _build_params(fmt_code, "batting", page)
        soup = _fetch_page(params)
        if soup is None:
            break
        rows = _parse_batting_table(soup)
        if not rows:
            break
        all_rows.extend(rows)
        time.sleep(REQUEST_DELAY)

    df = pd.DataFrame(all_rows)
    print(f"[scraper] Batting scrape complete — {len(df)} rows collected.")
    return df


def scrape_bowling(fmt: str = "odi", pages: int = 3) -> pd.DataFrame:
    """
    Scrape bowling statistics for the given format.

    Args:
        fmt:   One of 'test', 'odi', 't20'. Defaults to 'odi'.
        pages: Number of paginated result pages to fetch (25 rows each).

    Returns:
        pd.DataFrame with one row per player.
    """
    fmt_code = FORMAT_MAP.get(fmt.lower())
    if fmt_code is None:
        raise ValueError(f"Unknown format '{fmt}'. Choose from: {list(FORMAT_MAP)}")

    all_rows = []
    for page in range(1, pages + 1):
        print(f"[scraper] Fetching bowling {fmt.upper()} — page {page}/{pages}")
        params = _build_params(fmt_code, "bowling", page)
        soup = _fetch_page(params)
        if soup is None:
            break
        rows = _parse_bowling_table(soup)
        if not rows:
            break
        all_rows.extend(rows)
        time.sleep(REQUEST_DELAY)

    df = pd.DataFrame(all_rows)
    print(f"[scraper] Bowling scrape complete — {len(df)} rows collected.")
    return df


# ---------------------------------------------------------------------------
# CLI entry point (python -m cricketscope.scraper.cricinfo ...)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape ESPNcricinfo stats")
    parser.add_argument("--format", default="odi", choices=["test", "odi", "t20"],
                        help="Match format to scrape (default: odi)")
    parser.add_argument("--type", default="batting", choices=["batting", "bowling"],
                        dest="stat_type", help="Stat type (default: batting)")
    parser.add_argument("--pages", type=int, default=3,
                        help="Number of pages to scrape (default: 3, 25 rows/page)")
    parser.add_argument("--out", default=None,
                        help="Optional CSV output path")
    args = parser.parse_args()

    if args.stat_type == "batting":
        df = scrape_batting(fmt=args.format, pages=args.pages)
    else:
        df = scrape_bowling(fmt=args.format, pages=args.pages)

    if args.out:
        df.to_csv(args.out, index=False)
        print(f"[scraper] Saved to {args.out}")
    else:
        print(df.to_string())
