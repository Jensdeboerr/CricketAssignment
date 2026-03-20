# CricketScope

**Group members:** Jesper de Voogd, Wisse Seunnenga, Jens de Boer  
**Course:** DSS Advanced Programming 

---

## What this project does

CricketScope scrapes cricket player statistics from ESPNcricinfo and generates a visual dashboard. The tool collects batting and bowling stats for Test, ODI, and T20I formats, cleans the data, and produces charts showing top batters, batting average vs strike rate, and format comparisons across countries.

---

## Data

Data is scraped from the ESPNcricinfo stats engine:  
`https://stats.espncricinfo.com/ci/engine/stats/index.html`

This is a static HTML page. No official API is used. Scraping is done with `requests` and `BeautifulSoup`.

---

## Repo structure

```
cricketscope/
├── cricketscope/
│   ├── __init__.py
│   ├── scraper/
│   │   ├── __init__.py
│   │   └── cricinfo.py       ← HTML scraping
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   └── clean.py          ← Data cleaning
│   └── visualisation/
│       ├── __init__.py
│       └── dashboard.py      ← Charts and dashboard
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

All data is scraped from `stats.espncricinfo.com/ci/engine/stats/index.html` a static HTML stats engine that has been publicly available for over 20 years. The scraper:
- Sets a descriptive `User-Agent` header
- Waits 2 seconds between paginated requests to avoid overloading the server


## Expected output

Running the full pipeline for ODI batting (3 pages) should produce:
- player rows in the cleaned DataFrame
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
