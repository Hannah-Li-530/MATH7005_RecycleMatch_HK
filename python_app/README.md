# RecycleMatch HK — Python web app

This is the Python web-app version of the project prototype. It reads the frozen cleaned dataset at `../data/RecycleMatch_HK_public_points_clean.csv` and runs locally in a browser.

## Run on Windows

1. Install Python 3.10 or newer and extract the complete project archive.
2. Keep `python_app` and `data` together inside the project folder.
3. Close any older app running on port 8501, then double-click `start_windows.bat`. Open [localhost:8501](http://localhost:8501) if the browser does not open automatically.

To start it from PowerShell in the `python_app` folder:

```powershell
py -3.12 -m pip install "pandas>=2.0,<3"
py -3.12 web_app.py --open-browser
```

The main interface is in `web/`. Python loads the CSV and runs the recommendation methods in `app.py`, with `web_app.py` serving the page and JSON endpoints. The older Streamlit entry point is `app.py` and can be opened separately with `python -m streamlit run app.py` after installing `requirements.txt`.

## Features in this prototype

- Search a Hong Kong address or landmark through the Lands Department location search and coordinate transformation services.
- Use browser location, or enter latitude and longitude manually.
- Filter public recycling points by accepted materials.
- Rank matching points by Haversine straight-line distance.
- Search by distance with no radius limit by default. Advanced options offer 500 m, 1 km, or 3 km.
- Show which requested materials are available anywhere within the radius, which are missing, and which each recommended stop accepts.
- Generate an approximate fewer-stops suggestion using a greedy material-coverage heuristic.
- Find nearby reverse vending machines from a separate official snapshot. Cards show published hours and operator contact. The page shows the eligible bottle rebate and snapshot dates.
- Open an external Google Maps walking route for a selected point.

## Analyses in this folder

Beyond the interactive prototype, the folder ships the course-analysis code
(hand-written, no external data-mining library):

- `apriori.py` — classic Apriori frequent-itemset mining on accepted material
  combinations (candidate generation, downward-closure pruning, support
  counting), plus association rules with confidence and lift.
- `analysis_district.py` — per-district supply profile (point count, material
  categories, material combinations, opening-hours coverage).
- `run_analysis.py` — runs both on the frozen dataset and writes results to
  `output/` (frequent_itemsets.csv, association_rules.csv,
  district_supply_summary.csv, analysis_report.txt).
- `test_recyclematch.py` — small-sample verification of distances, nearest /
  fewer-stops recommendation (tie-breaking, duplicates, no-match, coverage),
  Apriori on a hand-computable example, and district aggregation.
- `smoke_app.py` — headless run of the older `app.py` interface via Streamlit's
  AppTest framework.

Run them from the `python_app` folder, e.g.:

   ```powershell
   py -3.12 run_analysis.py
   py -3.12 test_recyclematch.py
   py -3.12 smoke_app.py
   ```

## Limits to record in the report

- The app is a local decision-support prototype, not a real-time prediction system.
- Distances shown are straight-line distances, while Google Maps supplies the external walking route.
- Public point records do not confirm live opening status or current bin capacity.
- Address lookup requires an internet connection. Manual coordinates work without address lookup.
- The greedy fewer-stops method is a heuristic; it does not guarantee the mathematically optimal route.
- Apriori finds co-occurrence patterns in static data; it is descriptive, not a live recommender.
- Select a place from the address search results to fill in the latitude and longitude inputs. Before presenting, test address lookup and the full flow on the demo computer and network.
