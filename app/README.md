# Plated in Gold, Part II: interactive app

A static site built with Plotly.js. Live version: https://andrecdavis.github.io/Plated-In-Gold-Part-II/

- **Run locally:** `cd app && python -m http.server 8000`, then open http://localhost:8000.
- **Build the data:** from the repo root, run `python app/build_data.py` (writes `data.js`, aggregates only).
- **Test:** `python scripts/check_app.py` loads the app in headless Chromium in light and dark mode, on desktop and mobile, checks that every chart renders, saves screenshots to `app/screenshots/` and fails on any JavaScript error.
