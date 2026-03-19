"""
scraper/cricinfo.py - ESPNcricinfo stats scraper using pandas read_html
"""

import re
import time
import argparse
import requests
import pandas as pd
from io import StringIO

BASE_URL = "https://stats.espncricinfo.com/ci/engine/stats/index.html"
FORMAT_MAP = {"test": "1", "odi": "2", "t20": "3"}
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
REQUEST_DELAY = 2.0


def _split_player_country(text):
    m = re.match(r"^(.*?)\(([A-Z]{2,4})\)$", str(text).strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return str(text).strip(), ""


def _fetch_html(fmt_code, stat_type, page):
    params = {
        "class": fmt_code,
        "type": stat_type,
        "template": "results",
        "orderby": "runs" if stat_type == "batting" else "wickets",
        "page": str(page),
    }
    try:
        r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        print(f"[scraper] Request failed: {e}")
        return None


def _extract_stats_table(html):
    """Find the table that has a 'Player' column."""
    try:
        tables = pd.read_html(StringIO(html))
    except Exception as e:
        print(f"[scraper] Failed to parse tables: {e}")
        return None
    for t in tables:
        if "Player" in t.columns:
            return t
    return None


def scrape_batting(fmt="odi", pages=3):
    fmt_code = FORMAT_MAP.get(fmt.lower())
    if not fmt_code:
        raise ValueError(f"Unknown format '{fmt}'")

    all_rows = []
    for page in range(1, pages + 1):
        print(f"[scraper] Fetching batting {fmt.upper()} — page {page}/{pages}")
        html = _fetch_html(fmt_code, "batting", page)
        if html is None:
            break
        df = _extract_stats_table(html)
        if df is None or df.empty:
            break

        for _, row in df.iterrows():
            player_raw = str(row.get("Player", ""))
            if player_raw in ("nan", "Player", ""):
                continue
            name, country = _split_player_country(player_raw)
            all_rows.append({
                "player_name":  name,
                "country":      country,
                "span":         str(row.get("Span", "")),
                "matches":      str(row.get("Mat", "")),
                "innings":      str(row.get("Inns", "")),
                "not_outs":     str(row.get("NO", "")),
                "runs":         str(row.get("Runs", "")),
                "high_score":   str(row.get("HS", "")),
                "batting_avg":  str(row.get("Ave", "")),
                "balls_faced":  str(row.get("BF", "")),
                "strike_rate":  str(row.get("SR", "")),
                "hundreds":     str(row.get("100", "")),
                "fifties":      str(row.get("50", "")),
                "ducks":        str(row.get("0", "")),
            })
        time.sleep(REQUEST_DELAY)

    df_out = pd.DataFrame(all_rows)
    print(f"[scraper] Batting scrape complete — {len(df_out)} rows collected.")
    return df_out


def scrape_bowling(fmt="odi", pages=3):
    fmt_code = FORMAT_MAP.get(fmt.lower())
    if not fmt_code:
        raise ValueError(f"Unknown format '{fmt}'")

    all_rows = []
    for page in range(1, pages + 1):
        print(f"[scraper] Fetching bowling {fmt.upper()} — page {page}/{pages}")
        html = _fetch_html(fmt_code, "bowling", page)
        if html is None:
            break
        df = _extract_stats_table(html)
        if df is None or df.empty:
            break

        for _, row in df.iterrows():
            player_raw = str(row.get("Player", ""))
            if player_raw in ("nan", "Player", ""):
                continue
            name, country = _split_player_country(player_raw)
            all_rows.append({
                "player_name":    name,
                "country":        country,
                "span":           str(row.get("Span", "")),
                "matches":        str(row.get("Mat", "")),
                "innings":        str(row.get("Inns", "")),
                "overs":          str(row.get("Overs", "")),
                "maidens":        str(row.get("Mdns", "")),
                "runs_conceded":  str(row.get("Runs", "")),
                "wickets":        str(row.get("Wkts", "")),
                "bowling_avg":    str(row.get("Ave", "")),
                "economy":        str(row.get("Econ", "")),
                "strike_rate":    str(row.get("SR", "")),
                "four_wkt":       str(row.get("4", "")),
                "five_wkt":       str(row.get("5", "")),
                "ten_wkt":        str(row.get("10", "")),
            })
        time.sleep(REQUEST_DELAY)

    df_out = pd.DataFrame(all_rows)
    print(f"[scraper] Bowling scrape complete — {len(df_out)} rows collected.")
    return df_out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape ESPNcricinfo stats")
    parser.add_argument("--format", default="odi", choices=["test", "odi", "t20"])
    parser.add_argument("--type", default="batting", choices=["batting", "bowling"], dest="stat_type")
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    df = scrape_batting(fmt=args.format, pages=args.pages) if args.stat_type == "batting" \
        else scrape_bowling(fmt=args.format, pages=args.pages)

    if args.out:
        df.to_csv(args.out, index=False)
        print(f"[scraper] Saved to {args.out}")
    else:
        print(df.to_string())
