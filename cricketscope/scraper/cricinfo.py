"""
scraper/cricinfo.py

Scrapes player batting and bowling statistics from the ESPNcricinfo
stats engine (stats.espncricinfo.com). Uses requests + BeautifulSoup
only — no API, no headless browser required for this endpoint.

Supported formats:
    test = Test
    odi  = ODI
    t20  = T20I

Usage (standalone):
    python -m cricketscope.scraper.cricinfo --format odi --type batting --pages 2
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
    # Polite browser-like headers to avoid 403s and timeouts
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

# Seconds to wait between paginated requests — be a polite scraper
REQUEST_DELAY = 3.0

# Timeout per request in seconds
REQUEST_TIMEOUT = 30

# Retries on timeout
MAX_RETRIES = 3
RETRY_DELAY = 5.0

# Values that mean "no data" on ESPNcricinfo
SENTINELS = {"-", "DNB", "TDNB", "sub", ""}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_params(fmt_code: str, stat_type: str, page: int) -> dict:
    """Return the query-string parameters for one stats-engine request."""
    return {
        "class":    fmt_code,
        "type":     stat_type,
        "template": "results",
        "orderby":  "runs" if stat_type == "batting" else "wickets",
        "page":     str(page),
    }


def _fetch_page(params: dict) -> BeautifulSoup | None:
    """
    Fetch one page from the stats engine and return a BeautifulSoup object.
    Retries up to MAX_RETRIES times on timeout. Returns None on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                BASE_URL,
                params=params,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            if not soup.find("table", class_="engineTable"):
                print("[scraper] No data table found on page — likely past last page.")
                return None

            return soup

        except requests.exceptions.Timeout:
            print(f"[scraper] Timeout (attempt {attempt}/{MAX_RETRIES}) — retrying in {RETRY_DELAY}s")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        except requests.RequestException as exc:
            print(f"[scraper] Request failed: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    print(f"[scraper] All {MAX_RETRIES} attempts failed — skipping page.")
    return None


def _find_main_table(soup: BeautifulSoup):
    """
    Find the main data table on the page.
    ESPNcricinfo has multiple engineTables — take the one with the most rows.
    """
    tables = soup.find_all("table", class_="engineTable")
    if tables:
        return max(tables, key=lambda t: len(t.find_all("tr")))
    # Fallback: largest table on page
    all_tables = soup.find_all("table")
    if all_tables:
        return max(all_tables, key=lambda t: len(t.find_all("tr")))
    return None


def _get_headers(table) -> list[str]:
    """
    Extract column headers from a table.
    ESPNcricinfo sometimes uses <th>, sometimes <td> for headers.
    Also checks for a <thead> block.
    """
    # Try <thead> with <th>
    thead = table.find("thead")
    if thead:
        ths = thead.find_all("th")
        if ths:
            return [th.get_text(strip=True) for th in ths]

    # Try any <tr> containing <th> elements
    for tr in table.find_all("tr"):
        ths = tr.find_all("th")
        if ths:
            return [th.get_text(strip=True) for th in ths]

    # Fallback: first <tr> with <td> that looks like a header row
    known_batting  = {"Player", "Mat", "Inns", "Runs", "Ave"}
    known_bowling  = {"Player", "Mat", "Wkts", "Econ", "Ave"}
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        texts = {td.get_text(strip=True) for td in tds}
        if known_batting.issubset(texts) or known_bowling.issubset(texts):
            return [td.get_text(strip=True) for td in tds]

    return []


def _clean(value: str) -> str:
    """Return empty string for sentinel/missing values, otherwise strip whitespace."""
    value = value.strip()
    return "" if value in SENTINELS else value


def _parse_batting_table(soup: BeautifulSoup) -> list[dict]:
    """
    Parse the batting stats table from a BeautifulSoup page.

    Columns extracted:
        player_name, country, span, matches, innings, not_outs,
        runs, high_score, batting_avg, balls_faced, strike_rate,
        hundreds, fifties, ducks
    """
    rows = []
    table = _find_main_table(soup)
    if table is None:
        return rows

    headers = _get_headers(table)
    if not headers:
        print("[scraper] WARNING: could not detect batting column headers.")
        return rows

    print(f"[scraper] Batting headers: {headers}")
    header_set = set(headers)

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue

        # Skip repeated header rows that appear mid-table
        cell_texts = [c.get_text(strip=True) for c in cells]
        if set(cell_texts[:5]).intersection(header_set):
            continue

        # Map header name -> cell text
        row = {h: _clean(cells[i].get_text(strip=True)) for i, h in enumerate(headers) if i < len(cells)}

        player_name = row.get("Player", "")
        if not player_name:
            continue

        rows.append({
            "player_name":  player_name,
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
    table = _find_main_table(soup)
    if table is None:
        return rows

    headers = _get_headers(table)
    if not headers:
        print("[scraper] WARNING: could not detect bowling column headers.")
        return rows

    print(f"[scraper] Bowling headers: {headers}")
    header_set = set(headers)

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue

        cell_texts = [c.get_text(strip=True) for c in cells]
        if set(cell_texts[:5]).intersection(header_set):
            continue

        row = {h: _clean(cells[i].get_text(strip=True)) for i, h in enumerate(headers) if i < len(cells)}

        player_name = row.get("Player", "")
        if not player_name:
            continue

        rows.append({
            "player_name":    player_name,
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
# Public functions (imported by main.py and other modules)
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
            print(f"[scraper] No rows parsed on page {page} — stopping.")
            break
        all_rows.extend(rows)
        if page < pages:
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
            print(f"[scraper] No rows parsed on page {page} — stopping.")
            break
        all_rows.extend(rows)
        if page < pages:
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