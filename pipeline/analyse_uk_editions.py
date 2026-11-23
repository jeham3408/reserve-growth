#!/usr/bin/env python3
"""UK, second pass: annual per-field estimates from five consecutive Brown Book web editions, and the final outcome.

Sources
  * Brown Book web editions 1998, 1999, 2000, 2001 (dbd-data.co.uk) and the last web update (2002), all from the
    Wayback Machine: operator's estimate of recoverable reserves originally present, per field, as of the end
    of 1997, 1998, 1999, 2000 and 2001.
  * Watkins (2000): the estimate at start-up for fields that started before 1997 (million barrels).
  * NSTA PPRS: production per field 1975-2026. For a field that has stopped producing, cumulative production is
    the final answer that every earlier estimate was trying to predict.

Tests (written down before running, see analyse_hard_question.py for the Norwegian ones)
  U1  Realised outcome: final production / first estimate for fields that have ceased. Is the error larger for small fields?
  U2  Revisions 1997-2000: are they larger for fields in their first years than for mature fields, and for small fields?

Output: web/data/uk_editions.json, derived/uk_editions_long.csv, derived/uk_outcome.csv
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from scipy import stats

from build_uk import ALIASES, key
from common import DERIVED, SM3_TO_BBL, WEB_DATA, boot_ci, write_json
from uk_sources import brown_book_editions, nsta_fields, nsta_production, watkins_tables

RNG = np.random.default_rng(20261120)
SMALL_MT = 13.6          # about 100 million barrels at 7.35 barrels per tonne
SMALL_MMBBL = 100.0
UP, DOWN = 1.25, 0.80


def summ(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) == 0:
        return {"n": 0}
    lo, hi = boot_ci(r.values) if len(r) >= 5 else (float("nan"), float("nan"))
    return {"n": int(len(r)), "median": float(r.median()), "ci90": [lo, hi], "typical_change": float(np.exp(np.abs(np.log(r)).median()) - 1),
            "share_down": float((r <= DOWN).mean()), "share_up": float((r >= UP).mean()), "p10": float(r.quantile(.1)), "p90": float(r.quantile(.9))}


def mwu(a, b) -> float:
    a, b = pd.Series(a).dropna(), pd.Series(b).dropna()
    return float(stats.mannwhitneyu(a, b).pvalue) if len(a) > 2 and len(b) > 2 else float("nan")


def rho(x, y) -> dict:
    d = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(d) < 6:
        return {"n": int(len(d))}
    r, p = stats.spearmanr(d.x, d.y)
    return {"n": int(len(d)), "rho": float(r), "p": float(p)}


def main() -> None:
    ed = brown_book_editions()
    update_check = ed.attrs.get("update2002_check", {})
    ed.to_csv(DERIVED / "uk_editions_long.csv", index=False)
    oil = ed[ed.offshore & ed.oil_mt.notna() & (ed.oil_mt > 0)].copy()
    wide = oil.pivot_table(index="file", columns="year", values="oil_mt", aggfunc="first")
    meta = oil.sort_values("year").groupby("file").agg(name=("name", "last"), start_year=("start_year", "last"), kind=("kind", "last"),
                                                       discovery_year=("discovery_year", "last"), water_depth_m=("water_depth_m", "last"))
    # production and status
    yearly, info = nsta_production()
    yearly["PERIODYR"] = yearly.PERIODYR.astype(int)
    nsta_key = {}
    for n in info.FIELDNAME:
        nsta_key.setdefault(key(n), []).append(n)
    nf = nsta_fields().set_index("FIELDNAME")
    status_key = {key(n): n for n in nf.index}

    def production(name):
        names = ALIASES.get(name) or nsta_key.get(key(name))
        if not names:
            return None
        g = yearly[yearly.FIELDNAME.isin(names)]
        pos = g[g.OILPRODMAS > 0]
        st = [nf.STATUS.get(status_key.get(key(x))) for x in names]
        st = [s for s in st if isinstance(s, str)]
        return {"cum_mt": float(g.OILPRODMAS.sum() / 1e6), "cum_mmbbl": float(g.OILPRODM3.sum() * SM3_TO_BBL / 1e6),
                "first_oil_year": int(pos.PERIODYR.min()) if len(pos) else None, "last_oil_year": int(pos.PERIODYR.max()) if len(pos) else None,
                "status": "; ".join(sorted(set(st))), "ceased": bool(st) and all(("CEASED" in s or "POST-COP" in s) for s in st)}

    # ---------------------------------------------------------------- field records
    wat = watkins_tables()
    wat = wat[wat.sector == "UK"].copy()
    wat_key = {("A:" + n if n in ALIASES else key(n)): r for n, r in zip(wat.name, wat.to_dict("records"))}
    recs = []
    for f, row in wide.iterrows():
        m = meta.loc[f]
        ser = row.dropna()
        if ser.empty:
            continue
        pr = production(m["name"])
        w = wat_key.get("A:" + m["name"] if m["name"] in ALIASES else key(m["name"]))
        rec = {"file": f, "name": m["name"], "start_year": m.start_year, "kind": m.kind, "water_depth_m": m.water_depth_m,
               "years": [int(y) for y in ser.index], "oil_mt": [float(v) for v in ser.values],
               "first_year": int(ser.index[0]), "first_mt": float(ser.iloc[0]), "last_year": int(ser.index[-1]), "last_mt": float(ser.iloc[-1]),
               "n_estimates": int(len(ser)), "w_initial_mmbbl": w["initial_mmbbl"] if w else None, "w_1996_mmbbl": w["last_mmbbl"] if w else None,
               "w_start_year": w["start_year"] if w else None}
        if pr:
            rec.update(pr)
        recs.append(rec)
    d = pd.DataFrame(recs)
    d["start"] = d.start_year.fillna(d.w_start_year)
    d["covered"] = d.first_oil_year.notna() & (d.first_oil_year <= d.start + 1)
    d["window_ratio"] = np.where(d.n_estimates >= 2, d.last_mt / d.first_mt, np.nan)
    d["span"] = d.last_year - d.first_year
    d["age_at_first"] = d.first_year - d.start                       # years on stream when first seen in the editions
    d["young"] = d.age_at_first <= 3                                 # started 1994 or later (or not yet started)
    d["small"] = d.first_mt < SMALL_MT

    # ---------------------------------------------------------------- U2 revisions inside the editions (1997-2000)
    w2 = d[(d.n_estimates >= 2) & (d.span >= 2)].copy()
    w2["abs"] = np.abs(np.log(w2.window_ratio))
    groups = {}
    for lab, sub in (("young", w2[w2.young]), ("mature", w2[~w2.young]), ("young_small", w2[w2.young & w2.small]), ("young_large", w2[w2.young & ~w2.small]),
                     ("all_small", w2[w2.small]), ("all_large", w2[~w2.small])):
        groups[lab] = {**summ(sub.window_ratio), "share_unchanged": float((sub["abs"] < 0.01).mean()) if len(sub) else None}
    step_rows = []
    for a, b in ((1997, 1998), (1998, 1999), (1999, 2000), (1997, 2000)):
        if a in wide.columns and b in wide.columns:
            x = (wide[b] / wide[a]).dropna()
            if len(x) >= 5:
                step_rows.append({"from": a, "to": b, "n": int(len(x)), "share_changed": float((np.abs(np.log(x)) > 0.01).mean()),
                                  "share_changed_10pct": float((np.abs(np.log(x)) > np.log(1.1)).mean()), "median": float(x.median()),
                                  "typical_change": float(np.exp(np.abs(np.log(x)).median()) - 1)})
    revisions = {"n": int(len(w2)), "groups": groups, "steps": step_rows,
                 "p_young_vs_mature_magnitude": mwu(w2[w2.young]["abs"], w2[~w2.young]["abs"]),
                 "p_small_vs_large_magnitude_young": mwu(w2[w2.young & w2.small]["abs"], w2[w2.young & ~w2.small]["abs"]),
                 "p_small_vs_large_magnitude_all": mwu(w2[w2.small]["abs"], w2[~w2.small]["abs"]),
                 "rho_size_magnitude_all": rho(np.log(w2.first_mt), w2["abs"]), "rho_size_magnitude_young": rho(np.log(w2[w2.young].first_mt), w2[w2.young]["abs"]),
                 "definition": "last edition estimate / first edition estimate, fields with at least two estimates two or more years apart; young = on stream three years or less when first listed"}

    # ---------------------------------------------------------------- U1 realised outcome for ceased fields
    # (a) Watkins' start-up estimate (million barrels) against final production, start-ups before 1997
    wa, dropped, rounded_out = [], [], []
    for _, r in wat.iterrows():
        pr = production(r["name"])
        if not pr or not pr["ceased"] or pr["first_oil_year"] is None or pr["first_oil_year"] > r.start_year + 1:
            continue
        if r.initial_mmbbl < 5:          # Watkins' table is rounded to whole million barrels: too coarse for the smallest fields
            rounded_out.append(r["name"])
            continue
        # same guard as in build_uk.py: NSTA production to 1996 must reproduce at least 80 % of Watkins' cumulative figure
        names = ALIASES.get(r["name"]) or nsta_key.get(key(r["name"]))
        to96 = yearly[yearly.FIELDNAME.isin(names) & (yearly.PERIODYR <= 1996)].OILPRODM3.sum() * SM3_TO_BBL / 1e6
        if r.cum_prod_last_mmbbl > 5 and to96 / r.cum_prod_last_mmbbl < 0.8:
            dropped.append(r["name"])
            continue
        wa.append({"name": r["name"], "start": int(r.start_year), "estimate": r.initial_mmbbl, "unit": "million barrels", "final": pr["cum_mmbbl"],
                   "size_mmbbl": r.initial_mmbbl, "source": "Watkins (estimate at start-up)", "last_oil_year": pr["last_oil_year"]})
    # (b) first Brown Book edition estimate for fields that started 1997 or later (or are not in Watkins' table)
    have = {key(x["name"]) for x in wa}
    for _, r in d.iterrows():
        if not bool(r.get("ceased")) or not r.covered or key(r["name"]) in have or pd.isna(r.start) or r.age_at_first > 1:
            continue
        wa.append({"name": r["name"], "start": int(r.start), "estimate": r.first_mt, "unit": "million tonnes", "final": r.cum_mt,
                   "size_mmbbl": r.first_mt * 7.35, "source": f"Brown Book, end of {int(r.first_year)}", "last_oil_year": r.last_oil_year})
    out_df = pd.DataFrame(wa)
    out_df["ratio"] = out_df.final / out_df.estimate
    out_df["abs"] = np.abs(np.log(out_df.ratio))
    out_df["small"] = out_df.size_mmbbl < SMALL_MMBBL
    out_df.sort_values("ratio").to_csv(DERIVED / "uk_outcome.csv", index=False)
    a, b = out_df[out_df.small], out_df[~out_df.small]
    bs = [np.median(RNG.choice(a["abs"].values, len(a))) / max(1e-9, np.median(RNG.choice(b["abs"].values, len(b)))) for _ in range(5000)] if len(a) > 3 and len(b) > 3 else [np.nan]
    outcome = {"n": int(len(out_df)), "all": summ(out_df.ratio), "small": summ(a.ratio), "large": summ(b.ratio),
               "p_magnitude": mwu(a["abs"], b["abs"]), "p_direction": mwu(np.log(a.ratio), np.log(b.ratio)),
               "rho_size_magnitude": rho(np.log(out_df.size_mmbbl), out_df["abs"]), "rho_size_direction": rho(np.log(out_df.size_mmbbl), np.log(out_df.ratio)),
               "ratio_typical_small_over_large": float(np.median(a["abs"]) / np.median(b["abs"])) if len(a) and len(b) else None,
               "ratio_ci90": [float(np.nanquantile(bs, .05)), float(np.nanquantile(bs, .95))],
               "by_source": out_df.groupby("source").size().to_dict(), "dropped_incomplete_production": dropped, "dropped_rounded_estimate_under_5_mmbbl": rounded_out,
               "n_watkins": int(out_df.source.str.startswith("Watkins").sum()), "n_editions": int((~out_df.source.str.startswith("Watkins")).sum()),
               "points": out_df[["name", "start", "size_mmbbl", "ratio", "source", "last_oil_year"]].to_dict("records"),
               "definition": "final cumulative oil production (NSTA) / the estimate at start-up, for UK offshore oil fields that have stopped producing and whose production series starts within a year of start-up"}

    fields = [{"name": r["name"], "start": r.start, "y": r.years, "mt": r.oil_mt, "kind": r.kind, "cum_mt": r.get("cum_mt"), "status": r.get("status"),
               "ceased": bool(r.get("ceased")) if r.get("ceased") is not None and not pd.isna(r.get("ceased")) else None, "covered": bool(r.covered),
               "w0": r.w_initial_mmbbl, "w96": r.w_1996_mmbbl} for _, r in d.iterrows()]
    out = {"meta": {"generated": dt.date.today().isoformat(), "editions": ed.groupby("year").file.nunique().to_dict(),
                    "oil_estimates_by_year": {int(k): int(v) for k, v in wide.notna().sum().items()}, "n_oil_fields": int(len(d)),
                    "n_with_two_or_more": int((d.n_estimates >= 2).sum()), "n_with_three_or_more": int((d.n_estimates >= 3).sum()),
                    "small_mt": SMALL_MT, "pages_parsed": int(len(ed)), "update2002_check": update_check,
                    "source": "DTI 'Development of UK Oil and Gas Resources' (Brown Book) web editions 1998-2001 on dbd-data.co.uk and the 2002 update on og.dti.gov.uk, via the Internet Archive"},
           "revisions": revisions, "outcome": outcome, "fields": fields}
    write_json(WEB_DATA / "uk_editions.json", out)
    print("update2002 check", update_check)
    print("oil estimates by year", out["meta"]["oil_estimates_by_year"], "fields", len(d), ">=2", out["meta"]["n_with_two_or_more"], ">=3", out["meta"]["n_with_three_or_more"])
    for k, v in groups.items():
        print("  rev", k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items() if a != "ci90"})
    print("  p young/mature", revisions["p_young_vs_mature_magnitude"], "p small/large young", revisions["p_small_vs_large_magnitude_young"], "all", revisions["p_small_vs_large_magnitude_all"], revisions["rho_size_magnitude_all"], revisions["rho_size_magnitude_young"])
    for r in step_rows:
        print("  step", r)
    print("outcome n", outcome["n"], outcome["by_source"])
    for k in ("all", "small", "large"):
        print("  ", k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in outcome[k].items()})
    print("  p_mag", outcome["p_magnitude"], "p_dir", outcome["p_direction"], outcome["rho_size_magnitude"], outcome["rho_size_direction"], "ratio", outcome["ratio_typical_small_over_large"], outcome["ratio_ci90"])
    print(out_df.sort_values("ratio")[["name", "start", "estimate", "unit", "final", "ratio", "source"]].round(2).to_string())


if __name__ == "__main__":
    main()
