#!/usr/bin/env bash
# Rebuild everything in web/data/ and figures/ from raw/. Download first with: python pipeline/download.py
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"   # needs numpy, pandas, scipy, scikit-learn, statsmodels, matplotlib
$PY build_norway.py
$PY analyse_norway.py
$PY analyse_hard_question.py
$PY build_uk.py
$PY analyse_uk_editions.py
$PY make_figures.py
