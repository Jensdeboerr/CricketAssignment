import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np
import matplotlib

# Style defaults — override here to change the look of all charts
STYLE = {
    "figure_facecolor": "#FAFAFA",
    "axes_facecolor":   "#F4F4F4",
    "bar_color":        "#1D9E75",   # teal — matches CricketScope brand
    "scatter_alpha":    0.75,
    "font_size":        11,
    "title_size":       13,
    "dpi":              150,
}

plt.rcParams.update({
    "font.size":       STYLE["font_size"],
    "axes.titlesize":  STYLE["title_size"],
    "axes.spines.top":    False,
    "axes.spines.right":  False,
})

# Individual chart functions
def plot_top_batters(
    df: pd.DataFrame,
    n: int = 10,
    fmt_label: str = "ODI",
    ax: plt.Axes = None,
) -> plt.Axes:

    if ax is None:
        _, ax = plt.subplots(figsize=(8, 5))

    top = (
        df.dropna(subset=["runs", "player_name"])
        .nlargest(n, "runs")[["player_name", "country", "runs"]]
    )

    bars = ax.barh(
        top["player_name"],
        top["runs"],
        color=STYLE["bar_color"],
        edgecolor="white",
        linewidth=0.5,
    )

    # Annotate bars with run totals
    for bar, val in zip(bars, top["runs"]):
        ax.text(
            bar.get_width() + 30, bar.get_y() + bar.get_height() / 2,
            f"{int(val):,}", va="center", fontsize=9, color="#444",
        )

    ax.set_xlabel("Total runs")
    ax.set_title(f"Top {n} batters by runs — {fmt_label}")
    ax.invert_yaxis()
    ax.set_facecolor(STYLE["axes_facecolor"])

    return ax


def plot_avg_vs_sr(
    df: pd.DataFrame,
    fmt_label: str = "ODI",
    min_innings: int = 20,
    ax: plt.Axes = None,
) -> plt.Axes:
    
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 6))

    filtered = df.dropna(subset=["batting_avg", "strike_rate", "innings"])
    filtered = filtered[filtered["innings"] >= min_innings]

    # Assign a colour per country
    countries = filtered["country"].unique()
    cmap = matplotlib.colormaps.get_cmap("tab20").resampled(len(countries))
    colour_map = {c: cmap(i) for i, c in enumerate(countries)}

    for country, group in filtered.groupby("country"):
        ax.scatter(
            group["batting_avg"],
            group["strike_rate"],
            label=country,
            color=colour_map[country],
            alpha=STYLE["scatter_alpha"],
            edgecolors="white",
            linewidths=0.4,
            s=60,
        )

    # Label a few standout players (top 5 by runs)
    top5 = filtered.nlargest(5, "runs")
    for _, row in top5.iterrows():
        ax.annotate(
            row["player_name"].split()[-1],   # surname only for brevity
            xy=(row["batting_avg"], row["strike_rate"]),
            xytext=(4, 4), textcoords="offset points",
            fontsize=8, color="#333",
        )

    ax.set_xlabel("Batting average")
    ax.set_ylabel("Strike rate")
    ax.set_title(f"Batting average vs strike rate — {fmt_label} (min {min_innings} innings)")
    ax.legend(fontsize=7, ncol=2, framealpha=0.5)
    ax.set_facecolor(STYLE["axes_facecolor"])

    return ax

def plot_format_comparison(
    dfs: dict[str, pd.DataFrame],
    ax: plt.Axes = None,
) -> plt.Axes:
    """
    Grouped bar chart comparing mean batting average across formats
    for the top 10 countries by player count.

    Args:
        dfs: Dict mapping format label to cleaned batting DataFrame.
             e.g. {"Test": df_test, "ODI": df_odi, "T20": df_t20}
        ax:  Existing Axes to draw on (creates new figure if None).

    Returns:
        matplotlib Axes object.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 5))

    # Compute mean batting_avg per country per format
    # Skip any DataFrames that are empty or missing required columns
    summary = {}
    for fmt_label, df in dfs.items():
        if df.empty or "batting_avg" not in df.columns or "country" not in df.columns:
            print(f"[visualisation] Skipping {fmt_label} — no data available.")
            continue
        summary[fmt_label] = (
            df.dropna(subset=["batting_avg", "country"])
            .groupby("country")["batting_avg"]
            .mean()
        )

    if not summary:
        ax.text(0.5, 0.5, "No format comparison data available",
                ha="center", va="center", transform=ax.transAxes, fontsize=12)
        ax.set_title("Mean batting average by country and format")
        return ax

    combined = pd.DataFrame(summary).fillna(0)

    # Keep top countries by total player representation (only from non-empty frames)
    valid_dfs = [df for df in dfs.values()
                 if not df.empty and "country" in df.columns]
    top_countries = (
        pd.concat([df["country"] for df in valid_dfs])
        .value_counts()
        .head(10)
        .index
    )
    combined = combined.loc[combined.index.isin(top_countries)]

    n_formats = len(combined.columns)
    x = np.arange(len(combined))
    width = 0.8 / n_formats
    colours = ["#1D9E75", "#3B8BD4", "#D85A30"]

    for i, (fmt_label, colour) in enumerate(zip(combined.columns, colours)):
        offset = (i - n_formats / 2 + 0.5) * width
        ax.bar(x + offset, combined[fmt_label], width * 0.9,
               label=fmt_label, color=colour, edgecolor="white", linewidth=0.4)

    ax.set_xticks(x)
    ax.set_xticklabels(combined.index, rotation=30, ha="right")
    ax.set_ylabel("Mean batting average")
    ax.set_title("Mean batting average by country and format")
    ax.legend()
    ax.set_facecolor(STYLE["axes_facecolor"])

    return ax


# ---------------------------------------------------------------------------
# Dashboard composer
# ---------------------------------------------------------------------------

def save_dashboard(
    batting_odi: pd.DataFrame,
    batting_test: pd.DataFrame = None,
    batting_t20: pd.DataFrame = None,
    output_path: str = "output/dashboard.png",
) -> str:
    """
    Compose a 2x2 dashboard figure and save it to disk.

    Always includes:
        - Top 10 ODI batters bar chart (top-left)
        - ODI avg vs SR scatter (top-right)

    If Test and T20 DataFrames are also provided:
        - Format comparison grouped bar (bottom row, full width)

    Args:
        batting_odi:  Cleaned ODI batting DataFrame (required).
        batting_test: Cleaned Test batting DataFrame (optional).
        batting_t20:  Cleaned T20 batting DataFrame (optional).
        output_path:  File path to save the PNG. Directory is created
                      automatically if it does not exist.

    Returns:
        Absolute path to the saved file.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    has_multi = (
        batting_test is not None and not batting_test.empty and
        batting_t20 is not None and not batting_t20.empty
    )

    if has_multi:
        fig = plt.figure(figsize=(16, 11), facecolor=STYLE["figure_facecolor"])
        ax1 = fig.add_subplot(2, 2, 1)
        ax2 = fig.add_subplot(2, 2, 2)
        ax3 = fig.add_subplot(2, 1, 2)
    else:
        fig, (ax1, ax2) = plt.subplots(
            1, 2, figsize=(16, 6), facecolor=STYLE["figure_facecolor"]
        )

    plot_top_batters(batting_odi, ax=ax1, fmt_label="ODI")
    plot_avg_vs_sr(batting_odi, ax=ax2, fmt_label="ODI")

    if has_multi:
        plot_format_comparison(
            {"Test": batting_test, "ODI": batting_odi, "T20": batting_t20},
            ax=ax3,
        )

    fig.suptitle("CricketScope — player statistics dashboard", fontsize=15, y=1.01)
    fig.tight_layout()
    fig.savefig(output_path, dpi=STYLE["dpi"], bbox_inches="tight")
    plt.close(fig)

    abs_path = os.path.abspath(output_path)
    print(f"[visualisation] Dashboard saved to {abs_path}")
    return abs_path


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Generate synthetic data so this can run without a network connection
    rng = np.random.default_rng(42)
    countries = ["India", "Australia", "England", "Pakistan", "New Zealand",
                 "South Africa", "West Indies", "Sri Lanka"]

    def _fake_batting(n=50):
        return pd.DataFrame({
            "player_name":  [f"Player {i}" for i in range(n)],
            "country":      rng.choice(countries, n),
            "innings":      rng.integers(20, 200, n).astype(float),
            "runs":         rng.integers(500, 15000, n).astype(float),
            "batting_avg":  rng.uniform(20, 65, n),
            "strike_rate":  rng.uniform(55, 140, n),
        })

    df_odi  = _fake_batting(80)
    df_test = _fake_batting(80)
    df_t20  = _fake_batting(80)

    save_dashboard(df_odi, df_test, df_t20, output_path="output/dashboard.png")
    print("Smoke test complete — check output/dashboard.png")
