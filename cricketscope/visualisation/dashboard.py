"""
visualisation/dashboard.py

Generates a multi-panel PNG dashboard from cleaned player stats.

Charts produced:
    1. Top 10 ODI batters by total runs (horizontal bar)
    2. Batting average vs strike rate scatter (coloured by country)
    3. Format comparison — mean batting average by country (grouped bar)
    4. Top 10 bowlers by wickets (horizontal bar)

Usage (standalone):
    python -m cricketscope.visualisation.dashboard
"""

import os
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

STYLE = {
    "bg":            "#0F1923",
    "panel":         "#1A2634",
    "grid":          "#243447",
    "text_primary":  "#EAEAEA",
    "text_secondary":"#7A8FA6",
    "accent":        "#1D9E75",
    "accent2":       "#3B8BD4",
    "accent3":       "#E8593C",
    "accent4":       "#F2A623",
    "dpi":           180,
    "scatter_alpha": 0.85,
}

COUNTRY_COLOURS = {
    "IND": "#1D9E75",
    "AUS": "#F2A623",
    "ENG": "#3B8BD4",
    "PAK": "#1DB8A0",
    "NZ":  "#E8593C",
    "SA":  "#9B59B6",
    "WI":  "#E74C3C",
    "SL":  "#2ECC71",
    "BAN": "#F39C12",
    "ZIM": "#1ABC9C",
    "AFG": "#E67E22",
    "IRE": "#27AE60",
}
DEFAULT_COLOUR = "#7A8FA6"

matplotlib.rcParams.update({
    "font.family":        "DejaVu Sans",
    "font.size":          10,
    "axes.titlesize":     12,
    "axes.titleweight":   "bold",
    "axes.titlecolor":    STYLE["text_primary"],
    "axes.labelcolor":    STYLE["text_secondary"],
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.spines.left":   False,
    "axes.spines.bottom": False,
    "xtick.color":        STYLE["text_secondary"],
    "ytick.color":        STYLE["text_secondary"],
    "text.color":         STYLE["text_primary"],
    "figure.facecolor":   STYLE["bg"],
    "axes.facecolor":     STYLE["panel"],
    "grid.color":         STYLE["grid"],
    "grid.linewidth":     0.6,
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _country_colour(country: str) -> str:
    """Return a consistent colour for a given country code."""
    return COUNTRY_COLOURS.get(country, DEFAULT_COLOUR)


def _style_ax(ax: plt.Axes) -> None:
    """Apply dark-theme styling to an axes."""
    ax.set_facecolor(STYLE["panel"])
    ax.tick_params(colors=STYLE["text_secondary"], length=0)
    ax.xaxis.label.set_color(STYLE["text_secondary"])
    ax.yaxis.label.set_color(STYLE["text_secondary"])
    for spine in ax.spines.values():
        spine.set_visible(False)


# ---------------------------------------------------------------------------
# Chart functions
# ---------------------------------------------------------------------------

def plot_top_batters(
    df: pd.DataFrame,
    n: int = 10,
    fmt_label: str = "ODI",
    ax: plt.Axes = None,
) -> plt.Axes:
    """Horizontal bar chart of the top N batters by total runs."""
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 5))

    top = (
        df.dropna(subset=["runs", "player_name"])
        .nlargest(n, "runs")[["player_name", "country", "runs"]]
        .reset_index(drop=True)
    )

    colours  = [_country_colour(c) for c in top["country"]]
    max_runs = top["runs"].max()

    # Background track bars
    ax.barh(top["player_name"], [max_runs * 1.15] * len(top),
            color=STYLE["grid"], edgecolor="none", height=0.65, zorder=0)

    # Coloured bars
    ax.barh(top["player_name"], top["runs"],
            color=colours, edgecolor=STYLE["panel"],
            linewidth=0.8, height=0.65, zorder=1)

    for i, (_, row) in enumerate(top.iterrows()):
        # Run total label
        ax.text(row["runs"] + max_runs * 0.02,
                i, f"{int(row['runs']):,}",
                va="center", fontsize=9,
                color=STYLE["text_primary"], fontweight="bold")
        # Country badge inside bar
        ax.text(max_runs * 0.015, i,
                row["country"],
                va="center", fontsize=7.5,
                color=STYLE["bg"], fontweight="bold", zorder=2)

    ax.set_xlabel("Total runs", labelpad=8)
    ax.set_title(f"Top {n} {fmt_label} batters by runs", pad=12)
    ax.invert_yaxis()
    ax.set_xlim(0, max_runs * 1.22)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="x", alpha=0.25)
    _style_ax(ax)
    return ax


def plot_avg_vs_sr(
    df: pd.DataFrame,
    fmt_label: str = "ODI",
    min_innings: int = 20,
    ax: plt.Axes = None,
) -> plt.Axes:
    """Scatter — batting average vs strike rate, sized by runs, coloured by country."""
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 6))

    filtered = df.dropna(subset=["batting_avg", "strike_rate", "innings", "runs"])
    filtered = filtered[filtered["innings"] >= min_innings].copy()

    if filtered.empty:
        ax.text(0.5, 0.5, "Not enough data", transform=ax.transAxes,
                ha="center", va="center", color=STYLE["text_secondary"])
        ax.set_title(f"Avg vs strike rate — {fmt_label}", pad=12)
        _style_ax(ax)
        return ax

    size_scale = filtered["runs"] / filtered["runs"].max() * 200 + 30

    for country, group in filtered.groupby("country"):
        sizes = size_scale.loc[group.index]
        ax.scatter(group["batting_avg"], group["strike_rate"],
                   label=country, color=_country_colour(country),
                   alpha=STYLE["scatter_alpha"], edgecolors=STYLE["bg"],
                   linewidths=0.6, s=sizes, zorder=2)

    # Annotate top 6 players
    for _, row in filtered.nlargest(6, "runs").iterrows():
        ax.annotate(
            row["player_name"].split()[-1],
            xy=(row["batting_avg"], row["strike_rate"]),
            xytext=(5, 5), textcoords="offset points",
            fontsize=7.5, color=STYLE["text_primary"], fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=STYLE["text_secondary"],
                            lw=0.5, shrinkA=0, shrinkB=4),
        )

    # Median reference lines
    ax.axvline(filtered["batting_avg"].median(), color=STYLE["grid"],
               linestyle="--", linewidth=0.8, zorder=1)
    ax.axhline(filtered["strike_rate"].median(), color=STYLE["grid"],
               linestyle="--", linewidth=0.8, zorder=1)

    ax.set_xlabel("Batting average", labelpad=8)
    ax.set_ylabel("Strike rate", labelpad=8)
    ax.set_title(f"Avg vs strike rate — {fmt_label} (min {min_innings} innings)", pad=12)

    handles = [mpatches.Patch(color=_country_colour(c), label=c)
               for c in sorted(filtered["country"].unique())]
    ax.legend(handles=handles, fontsize=7, ncol=2, framealpha=0.15,
              facecolor=STYLE["panel"], edgecolor=STYLE["grid"],
              labelcolor=STYLE["text_primary"], loc="upper left")
    ax.grid(alpha=0.2, zorder=0)
    _style_ax(ax)
    return ax


def plot_format_comparison(
    dfs: dict[str, pd.DataFrame],
    ax: plt.Axes = None,
) -> plt.Axes:
    """Grouped bar — mean batting average per country across formats."""
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 5))

    summary = {}
    for fmt_label, df in dfs.items():
        summary[fmt_label] = (
            df.dropna(subset=["batting_avg", "country"])
            .groupby("country")["batting_avg"].mean()
        )

    combined = pd.DataFrame(summary).fillna(0)
    top_countries = (
        pd.concat([df["country"] for df in dfs.values()])
        .value_counts().head(10).index
    )
    combined = combined.loc[combined.index.isin(top_countries)]

    n_formats = len(combined.columns)
    x = np.arange(len(combined))
    width = 0.72 / n_formats
    fmt_colours = [STYLE["accent"], STYLE["accent2"], STYLE["accent3"]]

    for i, (fmt_label, colour) in enumerate(zip(combined.columns, fmt_colours)):
        offset = (i - n_formats / 2 + 0.5) * width
        bars = ax.bar(x + offset, combined[fmt_label], width * 0.92,
                      label=fmt_label, color=colour,
                      edgecolor=STYLE["panel"], linewidth=0.5)
        for bar in bars:
            h = bar.get_height()
            if h > 1:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.4,
                        f"{h:.1f}", ha="center", va="bottom",
                        fontsize=7, color=STYLE["text_secondary"])

    ax.set_xticks(x)
    ax.set_xticklabels(combined.index, rotation=25, ha="right", fontsize=9)
    ax.set_ylabel("Mean batting average", labelpad=8)
    ax.set_title("Mean batting average by country and format", pad=12)
    ax.legend(fontsize=8, framealpha=0.15, facecolor=STYLE["panel"],
              edgecolor=STYLE["grid"], labelcolor=STYLE["text_primary"])
    ax.grid(axis="y", alpha=0.25)
    _style_ax(ax)
    return ax


def plot_top_bowlers(
    df: pd.DataFrame,
    n: int = 10,
    fmt_label: str = "ODI",
    ax: plt.Axes = None,
) -> plt.Axes:
    """Horizontal bar chart of the top N bowlers by total wickets."""
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 5))

    top = (
        df.dropna(subset=["wickets", "player_name"])
        .nlargest(n, "wickets")[["player_name", "country", "wickets"]]
        .reset_index(drop=True)
    )

    if top.empty:
        ax.text(0.5, 0.5, "No bowling data available",
                transform=ax.transAxes, ha="center", va="center",
                color=STYLE["text_secondary"])
        ax.set_title(f"Top {n} {fmt_label} bowlers by wickets", pad=12)
        _style_ax(ax)
        return ax

    colours  = [_country_colour(c) for c in top["country"]]
    max_wkts = top["wickets"].max()

    ax.barh(top["player_name"], [max_wkts * 1.15] * len(top),
            color=STYLE["grid"], edgecolor="none", height=0.65, zorder=0)
    ax.barh(top["player_name"], top["wickets"],
            color=colours, edgecolor=STYLE["panel"],
            linewidth=0.8, height=0.65, zorder=1)

    for i, (_, row) in enumerate(top.iterrows()):
        ax.text(row["wickets"] + max_wkts * 0.02, i,
                f"{int(row['wickets'])}",
                va="center", fontsize=9,
                color=STYLE["text_primary"], fontweight="bold")
        ax.text(max_wkts * 0.015, i,
                row["country"],
                va="center", fontsize=7.5,
                color=STYLE["bg"], fontweight="bold", zorder=2)

    ax.set_xlabel("Total wickets", labelpad=8)
    ax.set_title(f"Top {n} {fmt_label} bowlers by wickets", pad=12)
    ax.invert_yaxis()
    ax.set_xlim(0, max_wkts * 1.22)
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="x", alpha=0.25)
    _style_ax(ax)
    return ax


# ---------------------------------------------------------------------------
# Dashboard composer
# ---------------------------------------------------------------------------

def save_dashboard(
    batting_odi: pd.DataFrame,
    batting_test: pd.DataFrame = None,
    batting_t20: pd.DataFrame = None,
    bowling_odi: pd.DataFrame = None,
    output_path: str = "output/dashboard.png",
) -> str:
    """
    Compose a 2x2 dashboard and save as PNG.

    Layout:
        Top-left:     Top 10 ODI batters bar
        Top-right:    Avg vs SR scatter
        Bottom-left:  Format comparison (if multi-format data provided)
        Bottom-right: Top 10 ODI bowlers bar (if bowling data provided)

    Args:
        batting_odi:  Cleaned ODI batting DataFrame (required).
        batting_test: Cleaned Test batting DataFrame (optional).
        batting_t20:  Cleaned T20 batting DataFrame (optional).
        bowling_odi:  Cleaned ODI bowling DataFrame (optional).
        output_path:  PNG output path.

    Returns:
        Absolute path to the saved file.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    fig = plt.figure(figsize=(20, 13), facecolor=STYLE["bg"])
    gs  = gridspec.GridSpec(
        2, 2, figure=fig,
        hspace=0.45, wspace=0.32,
        top=0.91, bottom=0.07, left=0.06, right=0.97,
    )

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])

    plot_top_batters(batting_odi, ax=ax1, fmt_label="ODI")
    plot_avg_vs_sr(batting_odi, ax=ax2, fmt_label="ODI")

    # Bottom-left: format comparison if we have multi-format data, else ODI only
    if batting_test is not None and batting_t20 is not None:
        plot_format_comparison(
            {"Test": batting_test, "ODI": batting_odi, "T20": batting_t20}, ax=ax3
        )
    else:
        plot_format_comparison({"ODI": batting_odi}, ax=ax3)

    # Bottom-right: bowlers if available
    if bowling_odi is not None and not bowling_odi.empty:
        plot_top_bowlers(bowling_odi, ax=ax4, fmt_label="ODI")
    else:
        # Fallback: top batters by average
        top_avg = (
            batting_odi.dropna(subset=["batting_avg", "player_name", "innings"])
            .query("innings >= 20")
            .nlargest(10, "batting_avg")[["player_name", "country", "batting_avg"]]
            .reset_index(drop=True)
        )
        colours  = [_country_colour(c) for c in top_avg["country"]]
        max_avg  = top_avg["batting_avg"].max()
        ax4.barh(top_avg["player_name"], [max_avg * 1.15] * len(top_avg),
                 color=STYLE["grid"], edgecolor="none", height=0.65, zorder=0)
        ax4.barh(top_avg["player_name"], top_avg["batting_avg"],
                 color=colours, edgecolor=STYLE["panel"],
                 linewidth=0.8, height=0.65, zorder=1)
        for i, (_, row) in enumerate(top_avg.iterrows()):
            ax4.text(row["batting_avg"] + max_avg * 0.02, i,
                     f"{row['batting_avg']:.2f}",
                     va="center", fontsize=9,
                     color=STYLE["text_primary"], fontweight="bold")
        ax4.set_xlabel("Batting average", labelpad=8)
        ax4.set_title("Top 10 ODI batters by average", pad=12)
        ax4.invert_yaxis()
        ax4.set_xlim(0, max_avg * 1.22)
        ax4.grid(axis="x", alpha=0.25)
        _style_ax(ax4)

    # Header
    fig.text(0.5, 0.972, "CricketScope",
             ha="center", va="top", fontsize=24, fontweight="bold",
             color=STYLE["accent"])
    fig.text(0.5, 0.938, "Player statistics dashboard — ESPNcricinfo",
             ha="center", va="top", fontsize=11,
             color=STYLE["text_secondary"])
    fig.add_artist(matplotlib.patches.FancyArrowPatch(
        (0.06, 0.918), (0.97, 0.918),
        transform=fig.transFigure, arrowstyle="-",
        color=STYLE["accent"], linewidth=1.2,
    ))

    fig.savefig(output_path, dpi=STYLE["dpi"], bbox_inches="tight",
                facecolor=STYLE["bg"])
    plt.close(fig)

    abs_path = os.path.abspath(output_path)
    print(f"[visualisation] Dashboard saved to {abs_path}")
    return abs_path


# ---------------------------------------------------------------------------
# Standalone smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    rng      = np.random.default_rng(42)
    countries = list(COUNTRY_COLOURS.keys())

    def _fake_batting(n=60):
        return pd.DataFrame({
            "player_name":  [f"Player {i}" for i in range(n)],
            "country":      rng.choice(countries, n),
            "innings":      rng.integers(20, 200, n).astype(float),
            "runs":         rng.integers(500, 15000, n).astype(float),
            "batting_avg":  rng.uniform(20, 65, n),
            "strike_rate":  rng.uniform(55, 140, n),
        })

    def _fake_bowling(n=60):
        return pd.DataFrame({
            "player_name":  [f"Bowler {i}" for i in range(n)],
            "country":      rng.choice(countries, n),
            "wickets":      rng.integers(50, 600, n).astype(float),
            "bowling_avg":  rng.uniform(18, 40, n),
            "economy":      rng.uniform(3.5, 6.5, n),
        })

    save_dashboard(
        batting_odi=_fake_batting(),
        batting_test=_fake_batting(),
        batting_t20=_fake_batting(),
        bowling_odi=_fake_bowling(),
        output_path="output/dashboard.png",
    )
    print("Smoke test complete — check output/dashboard.png")