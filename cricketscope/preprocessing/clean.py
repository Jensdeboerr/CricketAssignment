import pandas as pd
import numpy as np

# Sentinel values used by ESPNcricinfo to mean "no data"
SENTINELS = {"-", "DNB", "TDNB", "absent", "sub", ""}

# Column dtype specifications
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
# Internal helpers
def _replace_sentinels(df: pd.DataFrame) -> pd.DataFrame:
    return df.replace(list(SENTINELS), np.nan)

def _strip_not_out_marker(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\*$", "", regex=True)

def _cast_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def _parse_span(df: pd.DataFrame) -> pd.DataFrame:

    if "span" not in df.columns:
        return df
    split = df["span"].str.extract(r"(\d{4})-(\d{4})")
    df["career_start"] = pd.to_numeric(split[0], errors="coerce")
    df["career_end"]   = pd.to_numeric(split[1], errors="coerce")
    return df


def _clean_player_name(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["player_name", "country"]:
        if col in df.columns:
            df[col] = df[col].str.strip()
    return df

# Public functions
def clean_batting(df: pd.DataFrame) -> pd.DataFrame:
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

# Standalone smoke test
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
