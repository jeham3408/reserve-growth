# Reserve growth: how wrong are the first reserve estimates?

A hackathon project from the FORCE VibeCode Hackathon (Stavanger, 19–20 November 2026).
It follows the estimate of recoverable oil and gas for every Norwegian field, year by year, and asks which
fields end up far from where they started. The UK is a cross-check.

The question came from a geologist who asked about the UK sector. The UK regulator publishes sector totals
only, so a year-by-year estimate per UK field is not open today. We found it for four years: the annual
"Brown Book" was published on the web from 1998 to 2001 with the operator's estimate for every field, and
those editions survive in the Internet Archive. Norway publishes the full table for 2004–2025, so the main
analysis is Norwegian.

## What we found

Numbers are from `web/data/*.json`, built on 19 November 2026. `python pipeline/key_numbers.py` prints them.

**How much do the estimates move?** For 55 Norwegian fields that started in 2005 or later, measured from
the last estimate before start-up, the median field is at −9 % three years after start-up (90 % interval
−20 % to +2 %). 31 of the 55 had moved by more than −20 % / +25 % (20 down, 11 up). Weighted by volume the
change is −4 %.

**What characterises the fields that change a lot?** Three things held up.

1. **They are small.** Fields under 100 million barrels o.e. had typically moved 44 % after three years,
   larger fields 19 % (ratio 2.1, 90 % interval 1.2–4.6, p = 0.03). The gap opens in the start-up year and
   year 1; after that small and large fields move alike. 35 of the 37 small fields are tie-backs to another
   field's facility, so size and concept cannot be told apart. The same relation between size and the size of
   the revision is in Watkins' 109 UK and Norwegian fields that started 1971–1995 (p = 0.004).
2. **Downgrades come fast, upgrades come slowly.** Fields that ended 20 % or more down had 76 % of the loss
   in the estimate one year after start-up. None of the fields that ended 25 % or more up had reached half of
   their gain by then (p < 0.001). Of 31 fields that were not down 20 % three years after start-up, one ended
   that low and 14 ended 25 % or more up.
3. **Upgrades follow continued drilling.** New fields with wells drilled after year 1 grew +27 % from year 1
   to today, those without +3 % (p = 0.04 with field size held constant).

What did not separate the fields: oil or gas, area, operator, water depth, reservoir age, and the number of
exploration and appraisal wells before start-up. A cross-validated model with size and concept reaches AUC
0.64 (0.5 is chance): a small tie-back has an uncertain estimate, but the data do not say which way it will go.

**Older fields grow.** The 59 fields already producing before 2004 grew 17 % in total from 2004 to 2025.
For 28 oil fields that can be followed from start-up through Watkins (2000), the estimate has doubled (×1.99).

**UK.** For 35 UK oil fields that have stopped producing, total production can be compared with the
estimate at start-up: the median field produced 14 % more than estimated (90 % interval −5 % to +22 %), and
the typical miss was 28 %. In the Brown Book editions, fields in their first years were revised three times
as much as mature fields over 1997–2000 (19 % against 6 %, p < 0.001). Size gets mixed support in the UK:
clear in Watkins' 80 UK fields (p = 0.006), borderline in the Brown Book editions (15 % against 7 %,
p = 0.07), and absent in the outcome test (28 % against 27 %).

Literature claims tested: Watkins' factors (1.22 UK, 1.47 Norway to 1996) are reproduced from his tables;
the GEO ExPro claim that small fields started since 2010 shrink holds for those years, and the firmer result
is that small fields move more in both directions; chalk fields grew most only for the giants before 2004.

### Two passes, stated openly

The first pass measured from the estimate at the end of the start-up year and found no characteristic that
separated the fields (72 group tests, model AUC 0.41–0.67). The second pass changed the base to the last
estimate before start-up, added well counts, and tested seven hypotheses written down in advance in
`pipeline/analyse_hard_question.py`. Three held (size for the size of the change, timing, later drilling);
appraisal wells, wells at start-up and reservoir depth did not hold on their own. Both passes are on the
page. The base matters because 13 fields were revised by more than 20 % already in the start-up year.

## Run the web page

No build step. The page works offline.

```bash
cd web
python3 -m http.server 8000 --bind 127.0.0.1
```

Then open http://127.0.0.1:8000.

## Reproduce

Python 3.11+ with numpy, pandas, scipy, scikit-learn, statsmodels and matplotlib. `pdftotext` (poppler) is
needed once to read the Watkins tables. The download step uses only the standard library.

```bash
python3 pipeline/download.py     # raw/ + raw/MANIFEST.tsv; the Internet Archive part is slow (one request every 4 s)
pipeline/run_all.sh              # derived/, web/data/*.json, figures/*.png
```

With uv instead of an existing environment:

```bash
PYTHON="uv run --with numpy --with pandas --with scipy --with scikit-learn --with statsmodels --with matplotlib python" pipeline/run_all.sh
```

Browser test with screenshots at desktop and mobile width (server must be running):

```bash
uv run --with playwright python tests/screenshot.py http://127.0.0.1:8000
```

| Path | Content |
|---|---|
| `pipeline/download.py` | Downloads all raw inputs, writes `raw/MANIFEST.tsv` (URL, date, bytes, md5) |
| `pipeline/build_norway.py` | Joins the Sodir tables: start year, features, well counts, appreciation factors, checks |
| `pipeline/analyse_norway.py` | First pass: curves, tables, group tests, literature tests → `web/data/norway.json` |
| `pipeline/analyse_hard_question.py` | Second pass: size, timing, drilling, robustness → `web/data/hard.json` |
| `pipeline/build_uk.py`, `uk_sources.py` | Watkins tables, Brown Book pages, NSTA production → `web/data/uk.json` |
| `pipeline/analyse_uk_editions.py` | UK estimates 1997–2000 and the realised outcome → `web/data/uk_editions.json` |
| `pipeline/make_figures.py`, `key_numbers.py` | Static figures for slides in `figures/`; all key numbers as text |
| `derived/` | Intermediate tables, including the UK name table, unmatched names and the UK outcome table |
| `web/` | Static page: `index.html`, `style.css`, `app.js`, `data/*.json` |
| `talk/` | Talk script and slide outline (Norwegian) |
| `docs/problemet_forklart.md` | The problem explained simply (Norwegian) |

## Definitions

- **Estimate:** `fldRecoverableOE` in Sodir's `field_reserves`, originally recoverable oil equivalents per field
  and resource-account year (`fldVersion` 2004–2025, as of 31 December). It includes past production.
- **Start-up year:** first date with status "Producing" in `field_activity_status_hst`.
- **Base for new fields:** the last estimate before the start-up year (main results). The first pass used the
  estimate at the end of the start-up year. Fields on stream before 2004 use the 2004 estimate, so they enter
  mid-life.
- **Typical change:** median absolute change on a ratio scale. **Large revision:** outside 0.80–1.25.
  **Small field:** under 100 million barrels o.e. (15.9 million Sm³), the threshold used by GEO ExPro (2021).
- **Tie-back:** no surface facility of its own in `facility_fixed`, with three manual corrections listed in
  `pipeline/build_norway.py`.
- **Wells:** counted by field name in Sodir's wellbore tables: exploration and appraisal wells finished before
  the start-up year, production and injection wells finished by the start-up year, and wellbores finished later.
- **UK outcome:** total oil production (NSTA) ÷ the estimate at start-up, for fields that have ceased and whose
  production series starts within a year of start-up.

## Sources and licences

| Source | Used for | Licence as stated by the source |
|---|---|---|
| Sodir FactPages (Norwegian Offshore Directorate), downloaded 2026-11-19 | Norwegian estimates, production, wells, field information | Norwegian Licence for Open Government Data (NLOD), per https://www.sodir.no/en/facts/data-and-analyses/open-data/ |
| NSTA "Offshore hydrocarbon fields" feature service | UK field status | "NSTA Open User Licence" in the item metadata |
| NSTA "UKCS hydrocarbon field production reports (PPRS)" feature service | UK production 1975–2026 | No licence stated in the item metadata |
| DTI Brown Book field pages: web editions 1998, 1999, 2000 and 2001 (dbd-data.co.uk) and the 2002 update (og.dti.gov.uk), via the Internet Archive | UK estimates per field as of the end of 1997–2000 | Crown copyright; no licence stated on the pages |
| Watkins, G.C. (2000), MIT CEEPR WP 00-008, Tables D-1 and D-2 | Start-up and 1996 estimates, 96 UK and 30 Norwegian oil fields | Copyright of the author; cited, not redistributed |
| GEO ExPro, 11 May 2021, "The size of small fields tends to be overestimated" | Claim tested, size threshold | Cited only |

Contains data under the Norwegian licence for Open Government data (NLOD) distributed by the Norwegian
Offshore Directorate. Only the Sodir tables are stored in this repository. The NSTA download, the archived
Brown Book pages and the Watkins PDF are fetched by `pipeline/download.py` and are not redistributed here.

## Checks

- Grane oil is 120.31 million Sm³ in 2004 and 150.78 in 2025, as on FactPages.
- Summing the field rows gives 57.1 % sold and 13.8 % remaining reserves of Sodir's total resources for
  2025 (Sodir: about 57 % and 14 %), and 55.9 % and 14.5 % for 2024 (Sodir: about 56 % and 15 %).
- Cumulative production exceeds the latest recoverable estimate for six fields. Sleipner Øst is a booking
  effect (Sleipner Øst, Sleipner Vest and Gungne together match); the rest are within 10 %.
- Watkins' factors 1.22 and 1.47 are reproduced from the PDF tables; Piper is 636 → 1017 million barrels.
- UK name matching: for 53 matched fields, NSTA production to 1996 is ×1.01 of Watkins' cumulative
  production (median).
- The 2002 Brown Book web update repeats the 2001 edition's reserve figures (145 of 145 fields identical), so
  the UK series ends with the estimate as of the end of 2000.
- Robustness of the size result: p = 0.004 and 0.002 with the line at 200 and 300 million barrels; leaving
  out any single field gives p between 0.01 and 0.06; among fields still producing the relation is weaker
  (rank correlation −0.19, p = 0.22). The timing result holds for every variant tried (p ≤ 0.001).
- The page was opened in headless Chromium at 1280 and 390 px, in light and dark mode, without console
  errors or horizontal overflow.

## Limits

- Only 22 annual accounts are open for Norway. Revisions before 2004 and before the last pre-start estimate
  are not visible.
- 55 new fields is a small sample. The base was changed between the two passes after seeing the first
  result; the hypotheses of the second pass were fixed before testing, but the reader should know.
- Size and development concept describe nearly the same fields, so the data cannot say which one matters.
- Wells and reserves move together by construction: reserves are booked when a well or project is decided.
  For older fields the drilling relation is not clear once field size is held constant (p = 0.23).
- A changed estimate is not always a wrong estimate: new wells, added deposits, injection, price and
  shut-down decisions all move it. The data do not say why an estimate changed.
- In-place volumes are a single 2025 snapshot. Field descriptions are written with hindsight.
- Sodir announced on 26 February 2026 that the first publication of the 31 December 2025 field figures had
  wrong remaining reserves. Our download has 2025 figures for all fields except Frøy and Lille-Frigg.
- UK: per-field estimates are open for four year-ends only (1997–2000). The outcome test covers fields that
  have ceased (35), which are not a random sample; fields still producing are not in it. 80 of 228 field
  names have no rows in the NSTA production service, fields with an incomplete production series are dropped,
  and Watkins' estimates under 5 million barrels are left out because his table is rounded.
- Oil equivalents for Norway; oil only for the UK and for the Watkins comparison.

## About

Made during the hackathon by two students, with AI assistance (Claude Code) for research, code, analysis
and text. Not investment advice.
