"""
preprocessing/clean.py

Cleans and structures the raw DataFrames produced by the scraper.

Responsibilities:
    - Replace ESPNcricinfo's sentinel values ('-', 'DNB') with NaN
    - Cast all numeric columns to appropriate dtypes
    - Strip asterisks from 'not out' high-score values (e.g. '183*' -> '183')
    - Derive helper columns (e.g. career_start, career_end from span)
    - Merge batting and bowling tables on player + country for all-rounders

Usage (standalone):
    python -m cricketscope.preprocessing.clean
"""

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Sentinel values used by ESPNcricinfo to mean "no data"
# ---------------------------------------------------------------------------

SENTINELS = {"-", "DNB", "TDNB", "absent", "sub", "", "Unknown"}

# ---------------------------------------------------------------------------
# Column dtype specifications
# ---------------------------------------------------------------------------

BATTING_NUMERIC = [
    "matches", "innings", "not_outs", "runs", "high_score",
    "batting_avg", "balls_faced", "strike_rate",
    "hundreds", "fifties", "ducks",
]

BOWLING_NUMERIC = [
    "matches", "innings", "overs", "maidens", "runs_conceded",
    "wickets", "bowling_avg", "economy", "strike_rate",
    "four_wkt", "five_wkt", "ten_wkt",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _replace_sentinels(df: pd.DataFrame) -> pd.DataFrame:
    """Replace ESPNcricinfo no-data strings with NaN across the whole frame."""
    return df.replace(list(SENTINELS), np.nan)


def _strip_not_out_marker(series: pd.Series) -> pd.Series:
    """Remove the trailing '*' that marks a not-out innings (e.g. '183*' -> '183').
    Safely handles NaN values by only applying to non-null entries.
    """
    return series.where(series.isna(), series.astype(str).str.replace(r"\*$", "", regex=True))


def _cast_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Coerce a list of columns to numeric, setting unconvertible values to NaN."""
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _parse_span(df: pd.DataFrame) -> pd.DataFrame:
    """
    Split the 'span' column (e.g. '2015-2023') into two integer columns:
    career_start and career_end.
    Safely handles NaN by converting to string only where value is not null.
    """
    if "span" not in df.columns:
        return df

    # Convert only non-null values to string before extracting
    span_str = df["span"].where(df["span"].isna(), df["span"].astype(str))
    split = span_str.str.extract(r"(\d{4})-(\d{4})")
    df["career_start"] = pd.to_numeric(split[0], errors="coerce")
    df["career_end"]   = pd.to_numeric(split[1], errors="coerce")
    return df


def _clean_player_name(df: pd.DataFrame) -> pd.DataFrame:
    """Strip extra whitespace from player name and country fields.
    Safely handles NaN by converting to string only where value is not null.
    """
    for col in ["player_name", "country"]:
        if col in df.columns:
            # Only strip where value is not NaN
            df[col] = df[col].where(df[col].isna(), df[col].astype(str).str.strip())
    return df


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def clean_batting(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean a raw batting DataFrame from the scraper.

    Steps:
        1. Replace sentinel strings with NaN
        2. Strip not-out marker from high_score
        3. Cast numeric columns
        4. Parse span into career_start / career_end
        5. Clean player name whitespace
        6. Drop duplicate rows

    Args:
        df: Raw DataFrame from scraper.scrape_batting()

    Returns:
        Cleaned pd.DataFrame
    """
    df = df.copy()
    df = _replace_sentinels(df)

    if "high_score" in df.columns:
        df["high_score"] = _strip_not_out_marker(df["high_score"])

    df = _cast_numeric(df, BATTING_NUMERIC)
    df = _parse_span(df)
    df = _clean_player_name(df)
    df = df.drop_duplicates(subset=["player_name", "country"])

    print(f"[preprocessing] Batting cleaned — {len(df)} unique players.")
    return df.reset_index(drop=True)


def clean_bowling(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean a raw bowling DataFrame from the scraper.

    Steps:
        1. Replace sentinel strings with NaN
        2. Cast numeric columns
        3. Parse span into career_start / career_end
        4. Clean player name whitespace
        5. Drop duplicate rows

    Args:
        df: Raw DataFrame from scraper.scrape_bowling()

    Returns:
        Cleaned pd.DataFrame
    """
    df = df.copy()
    df = _replace_sentinels(df)
    df = _cast_numeric(df, BOWLING_NUMERIC)
    df = _parse_span(df)
    df = _clean_player_name(df)
    df = df.drop_duplicates(subset=["player_name", "country"])

    print(f"[preprocessing] Bowling cleaned — {len(df)} unique players.")
    return df.reset_index(drop=True)


def merge_player_stats(
    batting_df: pd.DataFrame,
    bowling_df: pd.DataFrame,
    min_wickets: int = 20,
    min_runs: int = 500,
) -> pd.DataFrame:
    """
    Merge batting and bowling DataFrames on player_name + country
    to produce an all-rounder profile table.

    Args:
        batting_df:   Cleaned batting DataFrame.
        bowling_df:   Cleaned bowling DataFrame.
        min_wickets:  Minimum wickets for a player to appear in merged table.
        min_runs:     Minimum runs for a player to appear in merged table.

    Returns:
        pd.DataFrame with both batting and bowling columns, suffixed
        _bat and _bowl where column names collide (e.g. matches_bat).
    """
    merged = pd.merge(
        batting_df,
        bowling_df,
        on=["player_name", "country"],
        how="inner",
        suffixes=("_bat", "_bowl"),
    )

    # Filter to players with meaningful contributions in both disciplines
    merged = merged[
        (merged["wickets"] >= min_wickets) &
        (merged["runs"] >= min_runs)
    ]

    print(f"[preprocessing] Merged all-rounders — {len(merged)} players "
          f"(>= {min_runs} runs, >= {min_wickets} wickets).")

    return merged.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Quick test with synthetic data so this can run without network access
    sample_batting = pd.DataFrame([
        {"player_name": "V Kohli",  "country": "India",     "span": "2008-2024",
         "matches": "113", "innings": "111", "not_outs": "8", "runs": "8848",
         "high_score": "183", "batting_avg": "57.32", "balls_faced": "11435",
         "strike_rate": "92.89", "hundreds": "46", "fifties": "67", "ducks": "4"},
        {"player_name": "R Sharma",  "country": "India",    "span": "2007-2024",
         "matches": "243", "innings": "239", "not_outs": "16", "runs": "9987",
         "high_score": "264", "batting_avg": "45.38", "balls_faced": "-",
         "strike_rate": "-", "hundreds": "29", "fifties": "46", "ducks": "-"},
    ])
    cleaned = clean_batting(sample_batting)
    print(cleaned.dtypes)
    print(cleaned)