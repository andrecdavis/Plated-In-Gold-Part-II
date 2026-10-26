PY ?= python

.PHONY: all setup data bridge figures notebook app audit check test pdf serve
all: figures notebook app

setup:
	$(PY) -m pip install -r requirements.txt

data:            ## raw collection database -> data/public/ (needs data/raw/ and PIG2_SELLER_SALT)
	$(PY) -m src.prepare

bridge:          ## Part I per-model asking prices (needs a clone of Plated-In-Gold next to this repo)
	$(PY) scripts/part1_bridge.py --part1 ../Plated-In-Gold

figures:         ## regenerate images/ and docs/results.json
	$(PY) scripts/make_figures.py --refresh

notebook:        ## generate and execute the analysis notebook
	$(PY) scripts/make_notebook.py
	cd notebooks && $(PY) -m jupyter nbconvert --to notebook --execute --inplace 01_from_asking_to_selling.ipynb

app:             ## rebuild app/data.js
	$(PY) app/build_data.py

audit:           ## check every README number against docs/results.json; writes docs/claims_audit.md
	$(PY) scripts/audit_claims.py

check:           ## headless-browser smoke test + screenshots (needs requirements-dev.txt)
	$(PY) scripts/check_app.py

test:            ## unit tests (needs requirements-dev.txt)
	$(PY) -m pytest -q

pdf:             ## build reports/…pdf and copy to app/report.pdf (needs Chrome; pandoc optional)
	$(PY) scripts/make_pdf.py

serve:
	cd app && $(PY) -m http.server 8000
