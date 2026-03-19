# CricketScope

A Python tool that scrapes player statistics from [ESPNcricinfo](https://stats.espncricinfo.com) and generates a visual dashboard. All data is collected via HTML scraping using `requests` and `BeautifulSoup` — no official API is used.

---

## What it does

1. **Scrapes** batting and bowling stats for Test, ODI, and T20I formats from the ESPNcricinfo stats engine
2. **Cleans** the raw data (handles missing values, casts types, derives career span columns)
3. **Visualises** the results as a multi-panel PNG dashboard:
   - Top 10 batters by runs (bar chart)
   - Batting average vs strike rate scatter (coloured by country)
   - Format comparison — mean batting average by country across formats

---

## Repo structure

```
cricketscope/
├── cricketscope/
│   ├── __init__.py
│   ├── scraper/
│   │   ├── __init__.py
│   │   └── cricinfo.py       ← HTML scraping (Person A)
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   └── clean.py          ← Data cleaning (Person B)
│   └── visualisation/
│       ├── __init__.py
│       └── dashboard.py      ← Charts and dashboard (Person C)
├── data/
│   ├── raw/                  ← gitignored
│   └── processed/            ← gitignored
├── output/                   ← gitignored (generated PNGs go here)
├── main.py                   ← CLI entry point
├── requirements.txt
└── README.md
```

---

## Setup

**1. Clone the repo**

```bash
git clone https://github.com/<your-username>/cricketscope.git
cd cricketscope
```

**2. Create and activate a virtual environment** (recommended)

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

---

## Usage

### Run the full pipeline (scrape → clean → dashboard)

```bash
# ODI batting stats, 3 pages (~75 players)
python main.py --format odi --type batting --pages 3

# All three formats, batting only, save CSVs to data/processed/
python main.py --format all --type batting --pages 3 --save-csv

# All formats and both batting + bowling
python main.py --format all --type all --pages 3 --save-csv
```

The dashboard PNG is saved to `output/dashboard.png`.

### Load from a saved CSV (skip scraping)

```bash
python main.py --load-csv data/processed/batting_odi.csv --format odi --type batting
```

### Run individual modules

```bash
# Scraper standalone
python -m cricketscope.scraper.cricinfo --format t20 --type batting --pages 2 --out data/raw/t20_batting.csv

# Preprocessing standalone (smoke test with synthetic data)
python -m cricketscope.preprocessing.clean

# Visualisation standalone (smoke test with synthetic data)
python -m cricketscope.visualisation.dashboard
```

---

## Data source

All data is scraped from `stats.espncricinfo.com/ci/engine/stats/index.html` — a static HTML stats engine that has been publicly available for over 20 years. The scraper:
- Sets a descriptive `User-Agent` header
- Waits 2 seconds between paginated requests to avoid overloading the server

---

## Variables collected

### Batting

| Column | Description |
|---|---|
| `player_name` | Player full name |
| `country` | Representing nation |
| `span` | Career span (e.g. 2015-2023) |
| `matches` | Matches played |
| `innings` | Innings batted |
| `not_outs` | Not-out innings |
| `runs` | Total runs scored |
| `high_score` | Highest individual score |
| `batting_avg` | Batting average |
| `balls_faced` | Total balls faced |
| `strike_rate` | Strike rate |
| `hundreds` | Centuries scored |
| `fifties` | Half-centuries scored |
| `ducks` | Duck dismissals |

### Bowling

| Column | Description |
|---|---|
| `player_name` | Player full name |
| `country` | Representing nation |
| `span` | Career span |
| `matches` | Matches played |
| `overs` | Overs bowled |
| `wickets` | Total wickets taken |
| `bowling_avg` | Bowling average |
| `economy` | Economy rate |
| `strike_rate` | Bowling strike rate |
| `five_wkt` | Five-wicket hauls |

---

## Expected output

Running the full pipeline for ODI batting (3 pages) should produce:
- ~75 player rows in the cleaned DataFrame
- `output/dashboard.png` — a 16×11 inch PNG with two or three chart panels

Exact values will vary with ESPNcricinfo's live data.

---

## Dependencies

See `requirements.txt`. Key libraries:

| Library | Purpose |
|---|---|
| `requests` | HTTP requests for scraping |
| `beautifulsoup4` + `lxml` | HTML parsing |
| `pandas` | Data manipulation |
| `numpy` | Numeric operations |
| `matplotlib` | Charts and dashboard |
