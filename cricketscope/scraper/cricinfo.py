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
    python -m cricketscope.scraper.cricinfo --format odi --type batting --pages 2
"""

import re
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
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_DELAY = 2.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_params(fmt_code: str, stat_type: str, page: int) -> dict:
    return {
        "class":    fmt_code,
        "type":     stat_type,
        "template": "results",
        "orderby":  "runs" if stat_type == "batting" else "wickets",
        "page":     str(page),
    }


def _fetch_page(params: dict) -> BeautifulSoup | None:
    try:
        response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"[scraper] Request failed: {exc}")
        return None

    soup = BeautifulSoup(response.text, "lxml")

    if not soup.find("table", class_="engineTable"):
        print("[scraper] No data table found on page — likely past last page.")
        return None

    return soup


def _split_player_country(cell_text: str) -> tuple[str, str]:
    """
    ESPNcricinfo puts player and country in one cell: 'SR Tendulkar(IND)'
    Split into ('SR Tendulkar', 'IND').
    """
    match = re.match(r"^(.*?)\(([A-Z]{2,4})\)$", cell_text.strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return cell_text.strip(), ""


def _get_stats_table(soup: BeautifulSoup) -> BeautifulSoup | None:
    """
    The page has 6 engineTables; the stats data is always table index 2
    (51 rows: 1 header + 50 data rows).
    """
    tables = soup.find_all("table", class_="engineTable")
    for t in tables:
        rows = t.find_all("tr")
        if len(rows) > 5:  # header + data rows
            first_cells = [td.get_text(strip=True) for td in rows[0].find_all("td")]
            if "Player" in first_cells:
                return t
    return None


def _parse_batting_table(soup: BeautifulSoup) -> list[dict]:
    rows = []
    table = _get_stats_table(soup)
    if table is None:
        return rows

    all_rows = table.find_all("tr")

    # First row is the header row (uses td, not th)
    header_cells = [td.get_text(strip=True) for td in all_rows[0].find_all("td")]

    for tr in all_rows[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < len(header_cells):
            continue

        row = dict(zip(header_cells, cells))

        player_raw = row.get("Player", "")
        player_name, country = _split_player_country(player_raw)

        rows.append({
            "player_name":  player_name,
            "country":      country,
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
    rows = []
    table = _get_stats_table(soup)
    if table is None:
        return rows

    all_rows = table.find_all("tr")
    header_cells = [td.get_text(strip=True) for td in all_rows[0].find_all("td")]

    for tr in all_rows[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < len(header_cells):
            continue

        row = dict(zip(header_cells, cells))

        player_raw = row.get("Player", "")
        player_name, country = _split_player_country(player_raw)

        rows.append({
            "player_name":    player_name,
            "country":        country,
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
# Public functions
# ---------------------------------------------------------------------------

def scrape_batting(fmt: str = "odi", pages: int = 3) -> pd.DataFrame:
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
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape ESPNcricinfo stats")
    parser.add_argument("--format", default="odi", choices=["test", "odi", "t20"],
                        help="Match format to scrape (default: odi)")
    parser.add_argument("--type", default="batting", choices=["batting", "bowling"],
                        dest="stat_type", help="Stat type (default: batting)")
    parser.add_argument("--pages", type=int, default=3,
                        help="Number of pages to scrape (default: 3, 50 rows/page)")
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
