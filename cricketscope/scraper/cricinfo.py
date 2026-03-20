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
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

REQUEST_DELAY   = 3.0
REQUEST_TIMEOUT = 30
MAX_RETRIES     = 3
RETRY_DELAY     = 5.0

SENTINELS = {"-", "DNB", "TDNB", "sub", ""}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_params(fmt_code: str, stat_type: str, page: int) -> dict:
    """Return query-string parameters for one stats-engine request."""
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
    Retries up to MAX_RETRIES times on timeout/503. Returns None on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                BASE_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            if not soup.find("table", class_="engineTable"):
                print("[scraper] No data table found — likely past last page.")
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
    """Return the largest engineTable on the page."""
    tables = soup.find_all("table", class_="engineTable")
    if tables:
        return max(tables, key=lambda t: len(t.find_all("tr")))
    all_tables = soup.find_all("table")
    if all_tables:
        return max(all_tables, key=lambda t: len(t.find_all("tr")))
    return None


def _get_headers(table) -> list[str]:
    """Extract column headers from a table, handling th and td variants."""
    thead = table.find("thead")
    if thead:
        ths = thead.find_all("th")
        if ths:
            return [th.get_text(strip=True) for th in ths]
    for tr in table.find_all("tr"):
        ths = tr.find_all("th")
        if ths:
            return [th.get_text(strip=True) for th in ths]
    known = {"Player", "Mat", "Runs", "Ave"}
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        texts = {td.get_text(strip=True) for td in tds}
        if known.issubset(texts):
            return [td.get_text(strip=True) for td in tds]
    return []


def _clean(value: str) -> str:
    """Return empty string for sentinel values, else strip whitespace."""
    value = value.strip()
    return "" if value in SENTINELS else value


def _parse_player_cell(cell) -> tuple[str, str]:
    """
    ESPNcricinfo encodes both name and country in the player cell:
        e.g. 'SR Tendulkar (IND)' or 'SR Tendulkar(Asia/IND)'
    Returns (player_name, country).
    """
    raw = cell.get_text(strip=True)

    # Match trailing parenthesised country code, e.g. (IND) or (Asia/ICC/SL)
    match = re.search(r"\(([^)]+)\)$", raw)
    if match:
        country_raw = match.group(1)
        player_name = raw[:match.start()].strip()
        # Take the last segment if slash-separated, e.g. Asia/ICC/SL -> SL
        country = country_raw.split("/")[-1].strip()
    else:
        player_name = raw
        country = "Unknown"

    return player_name, country


# ---------------------------------------------------------------------------
# Table parsers
# ---------------------------------------------------------------------------

def _parse_batting_table(soup: BeautifulSoup) -> list[dict]:
    """Parse the batting stats table into a list of row dicts."""
    rows = []
    table = _find_main_table(soup)
    if table is None:
        return rows

    headers = _get_headers(table)
    if not headers:
        print("[scraper] WARNING: could not detect batting headers.")
        return rows

    print(f"[scraper] Batting headers: {headers}")
    header_set = set(headers)

    # Find the index of the Player column
    try:
        player_idx = headers.index("Player")
    except ValueError:
        player_idx = 0

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue

        cell_texts = [c.get_text(strip=True) for c in cells]
        if set(cell_texts[:5]).intersection(header_set):
            continue  # skip repeated header rows

        row = {
            h: _clean(cells[i].get_text(strip=True))
            for i, h in enumerate(headers)
            if i < len(cells)
        }

        # Extract player name and country from the player cell
        player_name, country = _parse_player_cell(cells[player_idx])
        if not player_name:
            continue

        rows.append({
            "player_name":  player_name,
            "country":      country,
            "span":         row.get("Span", ""),
            "matches":      row.get("Mat",  ""),
            "innings":      row.get("Inns", ""),
            "not_outs":     row.get("NO",   ""),
            "runs":         row.get("Runs", ""),
            "high_score":   row.get("HS",   ""),
            "batting_avg":  row.get("Ave",  ""),
            "balls_faced":  row.get("BF",   ""),
            "strike_rate":  row.get("SR",   ""),
            "hundreds":     row.get("100",  ""),
            "fifties":      row.get("50",   ""),
            "ducks":        row.get("0",    ""),
        })

    return rows


def _parse_bowling_table(soup: BeautifulSoup) -> list[dict]:
    """Parse the bowling stats table into a list of row dicts."""
    rows = []
    table = _find_main_table(soup)
    if table is None:
        return rows

    headers = _get_headers(table)
    if not headers:
        print("[scraper] WARNING: could not detect bowling headers.")
        return rows

    print(f"[scraper] Bowling headers: {headers}")
    header_set = set(headers)

    try:
        player_idx = headers.index("Player")
    except ValueError:
        player_idx = 0

    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue

        cell_texts = [c.get_text(strip=True) for c in cells]
        if set(cell_texts[:5]).intersection(header_set):
            continue

        row = {
            h: _clean(cells[i].get_text(strip=True))
            for i, h in enumerate(headers)
            if i < len(cells)
        }

        player_name, country = _parse_player_cell(cells[player_idx])
        if not player_name:
            continue

        rows.append({
            "player_name":    player_name,
            "country":        country,
            "span":           row.get("Span",  ""),
            "matches":        row.get("Mat",   ""),
            "innings":        row.get("Inns",  ""),
            "overs":          row.get("Overs", ""),
            "maidens":        row.get("Mdns",  ""),
            "runs_conceded":  row.get("Runs",  ""),
            "wickets":        row.get("Wkts",  ""),
            "bowling_avg":    row.get("Ave",   ""),
            "economy":        row.get("Econ",  ""),
            "strike_rate":    row.get("SR",    ""),
            "four_wkt":       row.get("4",     ""),
            "five_wkt":       row.get("5",     ""),
            "ten_wkt":        row.get("10",    ""),
        })

    return rows


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def scrape_batting(fmt: str = "odi", pages: int = 3) -> pd.DataFrame:
    """
    Scrape batting statistics for the given format.

    Args:
        fmt:   One of 'test', 'odi', 't20'.
        pages: Number of paginated pages to fetch (25 rows each).

    Returns:
        pd.DataFrame with one row per player.
    """
    fmt_code = FORMAT_MAP.get(fmt.lower())
    if fmt_code is None:
        raise ValueError(f"Unknown format '{fmt}'. Choose from: {list(FORMAT_MAP)}")

    all_rows = []
    for page in range(1, pages + 1):
        print(f"[scraper] Fetching batting {fmt.upper()} — page {page}/{pages}")
        soup = _fetch_page(_build_params(fmt_code, "batting", page))
        if soup is None:
            break
        rows = _parse_batting_table(soup)
        if not rows:
            print(f"[scraper] No rows on page {page} — stopping.")
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
        fmt:   One of 'test', 'odi', 't20'.
        pages: Number of paginated pages to fetch (25 rows each).

    Returns:
        pd.DataFrame with one row per player.
    """
    fmt_code = FORMAT_MAP.get(fmt.lower())
    if fmt_code is None:
        raise ValueError(f"Unknown format '{fmt}'. Choose from: {list(FORMAT_MAP)}")

    all_rows = []
    for page in range(1, pages + 1):
        print(f"[scraper] Fetching bowling {fmt.upper()} — page {page}/{pages}")
        soup = _fetch_page(_build_params(fmt_code, "bowling", page))
        if soup is None:
            break
        rows = _parse_bowling_table(soup)
        if not rows:
            print(f"[scraper] No rows on page {page} — stopping.")
            break
        all_rows.extend(rows)
        if page < pages:
            time.sleep(REQUEST_DELAY)

    df = pd.DataFrame(all_rows)
    print(f"[scraper] Bowling scrape complete — {len(df)} rows collected.")
    return df


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape ESPNcricinfo stats")
    parser.add_argument("--format", default="odi", choices=["test", "odi", "t20"])
    parser.add_argument("--type", default="batting", choices=["batting", "bowling"],
                        dest="stat_type")
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    df = scrape_batting(fmt=args.format, pages=args.pages) \
         if args.stat_type == "batting" \
         else scrape_bowling(fmt=args.format, pages=args.pages)

    if args.out:
        df.to_csv(args.out, index=False)
        print(f"[scraper] Saved to {args.out}")
    else:
        print(df.to_string())