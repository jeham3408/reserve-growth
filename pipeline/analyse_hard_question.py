#!/usr/bin/env python3
"""Second pass at the hard question: what characterises the fields whose estimates change a lot?

Change against the first pass (analyse_norway.py):
  * The base is the last estimate BEFORE the start-up year (resource account 31.12 of year t0-1), i.e. the
    number the field was started on. The first pass used the estimate at the end of the start-up year, which
    already contains the first wells and months of production, and so hid the start-up revision.
  * New field characteristics that are not hindsight: exploration/appraisal wells before start-up and
    development wells by start-up and afterwards (Sodir wellbore tables).

Hypotheses, written down before testing (H1, H2, H5 and H7 come from the literature):
  H1  Small fields (< 100 MMboe) are revised down / revised more than larger fields  (GEO ExPro 2021)
  H2  Fields with few exploration and appraisal wells before start-up are revised more (GEO ExPro's explanation)
  H3  Developments with few wells at start-up have a wider spread (no averaging across wells)
  H4  Upward revisions after the first years go together with wells drilled after start-up
  H5  Deep / HPHT / complex reservoirs are revised down (Dromgoole & Speers 1997)
  H6  Downward revisions come earlier than upward revisions
  H7  The size effect is also present in Watkins' fields, UK and Norway, start-ups 1971-1995

Output: web/data/hard.json
"""
from __future__ import annotations

import datetime as dt
import re
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from common import DERIVED, SM3_TO_BBL, WEB_DATA, boot_ci, sodir, write_json
from uk_sources import watkins_tables

warnings.filterwarnings("ignore")
RNG = np.random.default_rng(20261120)
SMALL = 100 / SM3_TO_BBL     # 100 million barrels o.e. in million Sm3 o.e.
UP, DOWN = 1.25, 0.80
MIN_FOLLOW = 6               # years of follow-up required for the timing and drilling tests


def summ(af: pd.Series) -> dict:
    af = af.dropna()
    lo, hi = boot_ci(af.values)
    a = np.abs(np.log(af))
    return {"n": int(len(af)), "median": float(af.median()), "ci90": [lo, hi],
            "share_down": float((af <= DOWN).mean()), "share_up": float((af >= UP).mean()),
            "share_large": float(((af <= DOWN) | (af >= UP)).mean()),
            "n_down": int((af <= DOWN).sum()), "n_up": int((af >= UP).sum()),
            "typical_change": float(np.exp(a.median()) - 1), "p10": float(af.quantile(.1)), "p90": float(af.quantile(.9))}


def spearman(x, y) -> dict:
    d = pd.DataFrame({"x": x, "y": y}).dropna()
    r, p = stats.spearmanr(d.x, d.y)
    idx = RNG.integers(0, len(d), size=(3000, len(d)))
    bs = [stats.spearmanr(d.x.values[i], d.y.values[i])[0] for i in idx]
    return {"n": int(len(d)), "rho": float(r), "p": float(p), "ci90": [float(np.nanquantile(bs, .05)), float(np.nanquantile(bs, .95))]}


def mwu(a, b) -> float:
    a, b = pd.Series(a).dropna(), pd.Series(b).dropna()
    return float(stats.mannwhitneyu(a, b).pvalue) if len(a) > 2 and len(b) > 2 else float("nan")


def main() -> None:
    f = pd.read_csv(DERIVED / "norway_fields.csv")
    e = pd.read_csv(DERIVED / "norway_estimates.csv")
    c = f[f.cohort_pre].copy()
    c["small"] = c.pre_oe < SMALL
    L = np.log

    # ------------------------------------------------------------------ overall, from the pre-start estimate
    overall = {f"y{k}": summ(c[f"afp{k}"]) for k in (0, 1, 3, 5)}
    overall["latest"] = summ(c.afp_last)
    for k in (3, 5):
        x = c[f"afp{k}"].dropna()
        overall[f"y{k}"]["volume_weighted"] = float((x * c.loc[x.index, "pre_oe"]).sum() / c.loc[x.index, "pre_oe"].sum())
        overall[f"y{k}"]["wilcoxon_p"] = float(stats.wilcoxon(L(x)).pvalue)
    overall["start_year_step"] = {"share_changed_20pct": float((np.abs(L(c.afp0)) > L(1.25)).mean()),
                                  "n_changed_20pct": int((np.abs(L(c.afp0)) > L(1.25)).sum()),
                                  "names_down_20pct": c[c.afp0 <= DOWN].sort_values("afp0").name.tolist()}

    # ------------------------------------------------------------------ H1 size
    size = {"threshold_msm3": SMALL, "n_small": int(c.small.sum()), "n_large": int((~c.small).sum()), "at": {}}
    for k in (1, 3, 5):
        col = f"afp{k}"
        a, b = c[c.small][col].dropna(), c[~c.small][col].dropna()
        size["at"][str(k)] = {"small": summ(a), "large": summ(b), "p_direction": mwu(L(a), L(b)), "p_magnitude": mwu(np.abs(L(a)), np.abs(L(b)))}
    a, b = np.abs(L(c[c.small].afp3)).values, np.abs(L(c[~c.small].afp3)).values
    bs = [np.median(RNG.choice(a, len(a))) / np.median(RNG.choice(b, len(b))) for _ in range(5000)]
    size["ratio_typical_3y"] = {"ratio": float(np.median(a) / np.median(b)), "ci90": [float(np.quantile(bs, .05)), float(np.quantile(bs, .95))]}
    size["rho_size_vs_magnitude_3y"] = spearman(L(c.pre_oe), np.abs(L(c.afp3)))
    big = c[c.pre_oe >= 1]
    size["rho_size_vs_magnitude_3y_excluding_under_1msm3"] = spearman(L(big.pre_oe), np.abs(L(big.afp3)))
    size["rho_size_vs_direction_3y"] = spearman(L(c.pre_oe), L(c.afp3))
    steps = []
    for label, a_col, b_col in (("Start-up year", None, "afp0"), ("Year 1", "afp0", "afp1"), ("Years 2-3", "afp1", "afp3"), ("Years 4-5", "afp3", "afp5"),
                                ("Up to end of year 1", None, "afp1"), ("Year 1 to year 5", "afp1", "afp5")):
        d = c.dropna(subset=[b_col] + ([a_col] if a_col else []))
        st = np.abs(L(d[b_col]) if a_col is None else L(d[b_col] / d[a_col]))
        s_, l_ = st[d.small], st[~d.small]
        steps.append({"label": label, "small_typical": float(np.exp(s_.median()) - 1), "large_typical": float(np.exp(l_.median()) - 1),
                      "small_share_over_25pct": float((s_ > L(1.25)).mean()), "large_share_over_25pct": float((l_ > L(1.25)).mean()),
                      "n_small": int(len(s_)), "n_large": int(len(l_)), "p": mwu(s_, l_)})
    size["steps"] = steps
    size["points"] = [{"name": r["name"], "size": r.pre_oe, "afp1": r.afp1, "afp3": r.afp3, "afp5": r.afp5, "t0": r.t0, "tieback": bool(r.tieback)} for _, r in c.iterrows()]

    # ------------------------------------------------------------------ H7 Watkins replication (start-up -> 1996)
    w = watkins_tables()
    w = w[w.years_on_production >= 2].copy()          # fields that started in 1996 have no revision yet
    w["small"] = w.initial_mmbbl < 100
    w["abs"] = np.abs(L(w.af_1996))
    X = sm.add_constant(pd.DataFrame({"log_size": L(w.initial_mmbbl), "log_years": L(w.years_on_production), "norway": (w.sector == "Norway").astype(float)}))
    m_abs = sm.OLS(w["abs"], X).fit(cov_type="HC3")
    m_dir = sm.OLS(L(w.af_1996), X).fit(cov_type="HC3")
    groups = []
    for sec in ("UK", "Norway"):
        for lab, lo, hi in (("2-6 years on stream", 2, 6), ("7 years or more", 7, 99)):
            d = w[(w.sector == sec) & w.years_on_production.between(lo, hi)]
            a, b = d[d.small], d[~d.small]
            groups.append({"sector": sec, "history": lab, "n_small": int(len(a)), "n_large": int(len(b)),
                           "small_typical": float(np.exp(a["abs"].median()) - 1) if len(a) else None,
                           "large_typical": float(np.exp(b["abs"].median()) - 1) if len(b) else None,
                           "small_median": float(a.af_1996.median()) if len(a) else None, "large_median": float(b.af_1996.median()) if len(b) else None})
    by_sector = {}
    for sec in ("UK", "Norway"):
        ws = w[w.sector == sec]
        ms = sm.OLS(ws["abs"], sm.add_constant(pd.DataFrame({"log_size": L(ws.initial_mmbbl), "log_years": L(ws.years_on_production)}))).fit(cov_type="HC3")
        by_sector[sec] = {"n": int(len(ws)), "coef": float(ms.params["log_size"]), "p": float(ms.pvalues["log_size"]),
                          "small_typical": float(np.exp(ws[ws.small]["abs"].median()) - 1), "large_typical": float(np.exp(ws[~ws.small]["abs"].median()) - 1)}
    watkins = {"by_sector": by_sector, "n": int(len(w)), "n_uk": int((w.sector == "UK").sum()), "n_norway": int((w.sector == "Norway").sum()),
               "magnitude_coef_log_size": float(m_abs.params["log_size"]), "magnitude_p": float(m_abs.pvalues["log_size"]),
               "magnitude_ci95": [float(v) for v in m_abs.conf_int().loc["log_size"]],
               "direction_coef_log_size": float(m_dir.params["log_size"]), "direction_p": float(m_dir.pvalues["log_size"]),
               "groups": groups,
               "note": "Regression of |log(appreciation factor to 1996)| on log initial size, log years on production and a Norway dummy, robust standard errors."}

    # ------------------------------------------------------------------ H2, H3, H5 and the rest: what did not hold
    def rho_row(label, col, hyp):
        return {"hypothesis": hyp, "label": label, "direction_3y": spearman(c[col], L(c.afp3)), "magnitude_3y": spearman(c[col], np.abs(L(c.afp3))),
                "direction_5y": spearman(c[col], L(c.afp5)), "magnitude_5y": spearman(c[col], np.abs(L(c.afp5)))}
    c["expl_per_100mmboe"] = c.n_expl_wells_pre / (c.pre_oe * SM3_TO_BBL / 100)
    other = [rho_row("Exploration and appraisal wells before start-up", "n_expl_wells_pre", "H2"),
             rho_row("…per 100 MMboe of first estimate", "expl_per_100mmboe", "H2"),
             rho_row("Production and injection wells ready at start-up", "n_dev_wells_by_start", "H3"),
             rho_row("Reservoir depth", "reservoir_depth_m", "H5"),
             rho_row("Water depth", "water_depth_m", "-"),
             rho_row("Years from discovery to start-up", "lead_time_discovery_to_start", "-"),
             rho_row("Start-up year", "t0", "-")]
    d = c.dropna(subset=["afp3"]).copy()
    Xs = sm.add_constant(pd.DataFrame({"log_size": L(d.pre_oe), "log_expl_wells": np.log1p(d.n_expl_wells_pre),
                                       "log_wells_at_start": np.log1p(d.n_dev_wells_by_start), "tieback": d.tieback.astype(float)}))
    m_multi = sm.OLS(np.abs(L(d.afp3)), Xs).fit(cov_type="HC3")
    m_size = sm.OLS(np.abs(L(d.afp3)), sm.add_constant(L(d.pre_oe).rename("log_size"))).fit(cov_type="HC3")
    cats = []
    for col, label in (("tieback", "Satellite / tie-back"), ("text_hpht", "High pressure / HPHT (today's text)"), ("text_complex", "Complex / segmented (today's text)")):
        a, b = c[c[col] == True].afp3, c[c[col] == False].afp3
        cats.append({"label": label, "yes": summ(a), "no": summ(b), "p_direction": mwu(L(a), L(b)), "p_magnitude": mwu(np.abs(L(a)), np.abs(L(b)))})
    few = c.n_dev_wells_by_start <= 3
    wells_split = {"few": summ(c[few].afp3), "more": summ(c[~few].afp3), "p_magnitude": mwu(np.abs(L(c[few].afp3)), np.abs(L(c[~few].afp3))),
                   "definition": "three or fewer production and injection wells ready in the start-up year"}
    regress = {"size_only": {"coef": float(m_size.params["log_size"]), "p": float(m_size.pvalues["log_size"])},
               "with_wells_and_concept": {k: {"coef": float(m_multi.params[k]), "p": float(m_multi.pvalues[k])} for k in m_multi.params.index if k != "const"},
               "note": "Outcome: |log change| three years after start-up. With size, wells and concept together no single variable is clear: they are strongly correlated (small fields are tie-backs with few wells)."}

    # ------------------------------------------------------------------ can the large revisions be predicted now?
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    models = []
    for label, target, feats in (
            ("Large revision (outside 0.80-1.25) within 3 years: size and concept only", "large3", ["log_size", "is_tieback"]),
            ("Large revision within 3 years: size, concept, wells, depth", "large3", ["log_size", "is_tieback", "log_wells_at_start", "log_expl_wells", "reservoir_depth_m"]),
            ("Downgrade of 20 % or more within 3 years: size, concept, wells, depth", "down3", ["log_size", "is_tieback", "log_wells_at_start", "log_expl_wells", "reservoir_depth_m"])):
        dm = c.copy()
        dm["log_size"] = L(dm.pre_oe); dm["is_tieback"] = dm.tieback.astype(float)
        dm["log_wells_at_start"] = np.log1p(dm.n_dev_wells_by_start); dm["log_expl_wells"] = np.log1p(dm.n_expl_wells_pre)
        dm["large3"] = ((dm.afp3 <= DOWN) | (dm.afp3 >= UP)).astype(int); dm["down3"] = (dm.afp3 <= DOWN).astype(int)
        Xm = dm[feats].astype(float); Xm = Xm.fillna(Xm.median()); ym = dm[target].values
        pipe = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000))
        auc = cross_val_score(pipe, Xm, ym, cv=RepeatedStratifiedKFold(n_splits=5, n_repeats=40, random_state=7), scoring="roc_auc")
        cv_small = RepeatedStratifiedKFold(n_splits=5, n_repeats=4, random_state=7)
        obs = cross_val_score(pipe, Xm, ym, cv=cv_small, scoring="roc_auc").mean()
        null = np.array([cross_val_score(pipe, Xm, RNG.permutation(ym), cv=cv_small, scoring="roc_auc").mean() for _ in range(300)])
        models.append({"label": label, "n": int(len(ym)), "positives": int(ym.sum()), "base_rate": float(ym.mean()), "cv_auc": float(auc.mean()),
                       "cv_auc_range90": [float(np.quantile(auc.reshape(40, 5).mean(axis=1), q)) for q in (.05, .95)],
                       "null_auc_p95": float(np.quantile(null, .95)), "permutation_p": float((np.sum(null >= obs) + 1) / (len(null) + 1)), "features": feats})

    # ------------------------------------------------------------------ H6 timing
    g = f[(f.t0 > 2004) & f.pre_oe.notna() & ((2025 - f.t0) >= MIN_FOLLOW)].copy()
    g["dirn"] = np.where(g.afp_last <= DOWN, "down", np.where(g.afp_last >= UP, "up", "flat"))
    path = {"down": [], "up": []}
    per_field = {}
    for _, r in g.iterrows():
        x = e[(e.id == r.id) & (e.year >= r.t0)].sort_values("year")
        per_field[r.id] = {int(y - r.t0): float(np.log(v / r.pre_oe) / np.log(r.afp_last)) for y, v in zip(x.year, x.oe)} if r.dirn != "flat" else {}
    for dn in ("down", "up"):
        ids = g[g.dirn == dn].id
        for k in range(0, MIN_FOLLOW + 1):
            v = [per_field[i][k] for i in ids if k in per_field[i]]
            path[dn].append({"k": k, "n": len(v), "median": float(np.median(v)), "p25": float(np.quantile(v, .25)), "p75": float(np.quantile(v, .75))})
    sh1 = {dn: pd.Series([per_field[i].get(1, np.nan) for i in g[g.dirn == dn].id]) for dn in ("down", "up")}
    sh3 = {dn: pd.Series([per_field[i].get(3, np.nan) for i in g[g.dirn == dn].id]) for dn in ("down", "up")}

    def biggest_step(fid, t0):
        x = e[(e.id == fid) & (e.year >= t0 - 1)].sort_values("year")
        st = np.log(x.oe).diff().dropna()
        return float(x.loc[st.abs().idxmax(), "year"] - t0) if len(st) else np.nan
    g["k_big"] = [biggest_step(i, t) for i, t in zip(g.id, g.t0)]
    # what does the state three years after start-up say about the end state?
    g3 = g[g.afp3.notna()]
    nd, dn3 = g3[g3.afp3 > DOWN], g3[g3.afp3 <= DOWN]
    after3 = {"not_down_at_year3": {"n": int(len(nd)), "ended_down": int((nd.afp_last <= DOWN).sum()), "ended_up": int((nd.afp_last >= UP).sum()),
                                    "ended_down_names": nd[nd.afp_last <= DOWN].name.tolist()},
              "down_at_year3": {"n": int(len(dn3)), "still_down": int((dn3.afp_last <= DOWN).sum()),
                                "recovered_names": dn3[dn3.afp_last > DOWN].name.tolist()}}
    timing = {"after_year3": after3, "min_years_followed": MIN_FOLLOW, "n": int(len(g)), "n_down": int((g.dirn == "down").sum()), "n_up": int((g.dirn == "up").sum()), "n_flat": int((g.dirn == "flat").sum()),
              "path": path,
              "share_of_final_change_after_year1": {dn: float(sh1[dn].median()) for dn in ("down", "up")},
              "share_of_final_change_after_year3": {dn: float(sh3[dn].median()) for dn in ("down", "up")},
              "half_reached_by_year1": {dn: float((sh1[dn] >= .5).mean()) for dn in ("down", "up")},
              "half_reached_by_year3": {dn: float((sh3[dn] >= .5).mean()) for dn in ("down", "up")},
              "p_year1": mwu(sh1["down"], sh1["up"]), "p_year3": mwu(sh3["down"], sh3["up"]),
              "year_of_largest_step_median": {dn: float(g[g.dirn == dn].k_big.median()) for dn in ("down", "up")},
              "names": {dn: g[g.dirn == dn].sort_values("afp_last").name.tolist() for dn in ("down", "up")}}

    # ------------------------------------------------------------------ H4 drilling and growth
    h = g.dropna(subset=["afp1"]).copy()
    h["later"] = L(h.afp_last / h.afp1)
    h["rel"] = h.n_dev_wellbores_after_y1 / np.maximum(h.n_dev_wells_by_start, 1)
    none, some = h[h.n_dev_wellbores_after_y1 == 0], h[h.n_dev_wellbores_after_y1 > 0]
    Xd = sm.add_constant(pd.DataFrame({"log_later_wells": np.log1p(h.n_dev_wellbores_after_y1), "log_size": L(h.pre_oe),
                                       "discoveries_added": h.n_discoveries_added_after_start.astype(float)}))
    m_d = sm.OLS(h.later, Xd).fit(cov_type="HC3")
    new_fields = {"n": int(len(h)), "no_later_wells": {"n": int(len(none)), "median_later_change": float(np.exp(none.later.median())), "share_up_25": float((np.exp(none.later) >= UP).mean())},
                  "with_later_wells": {"n": int(len(some)), "median_later_change": float(np.exp(some.later.median())), "share_up_25": float((np.exp(some.later) >= UP).mean())},
                  "p": mwu(none.later, some.later), "rho_relative_drilling": spearman(h.rel, h.later),
                  "regression_coef_log_wells": float(m_d.params["log_later_wells"]), "regression_p": float(m_d.pvalues["log_later_wells"]),
                  "definition": "change from the end of year 1 to the latest estimate, against development wellbores completed after year 1"}
    wd = sodir("wellbore_development_all")
    wd = wd[wd.wlbPurpose.isin(["PRODUCTION", "INJECTION"]) & ~wd.wlbStatus.isin(["WILL NEVER BE DRILLED", "JUNKED"])].copy()
    wd["cy"] = pd.to_datetime(wd.wlbCompletionDate, format="%d.%m.%Y", errors="coerce").dt.year
    o = f[f.pre2004].copy()
    o["wells_2005_2025"] = [int(((wd.wlbField == n) & (wd.cy >= 2005)).sum()) for n in o.name]
    o["wells_before_2005"] = [int(((wd.wlbField == n) & (wd.cy < 2005)).sum()) for n in o.name]
    o["rel"] = o.wells_2005_2025 / np.maximum(o.wells_before_2005, 1)
    op = o[o.status == "Producing"].copy()                    # fields that shut down have frozen estimates and no wells
    op["tercile"] = pd.qcut(op.rel, 3, labels=["Least new drilling", "Middle", "Most new drilling"])
    old_fields = {"n_all": int(len(o)), "n_producing": int(len(op)),
                  "rho_all": spearman(o.rel, L(o.af_2004_to_last)), "rho_producing": spearman(op.rel, L(op.af_2004_to_last)),
                  "terciles_producing": [{"label": str(k), "n": int(len(v)), "median_growth": float(v.af_2004_to_last.median()),
                                          "ci90": list(boot_ci(v.af_2004_to_last.values)), "median_new_wells_per_old_well": float(v.rel.median())}
                                         for k, v in op.groupby("tercile", observed=True)],
                  "points": [{"name": r["name"], "rel": r.rel, "wells_new": r.wells_2005_2025, "wells_old": r.wells_before_2005, "af": r.af_2004_to_last, "producing": r.status == "Producing"} for _, r in o.iterrows()],
                  "definition": "development wellbores completed 2005-2025 per wellbore completed before 2005, against growth in the estimate 2004-2025"}
    # checks on the drilling result for older fields: absolute well counts, size as a confounder, added deposits
    Xo = sm.add_constant(pd.DataFrame({"log_rel": np.log1p(op.rel), "log_size": L(op.oe_2004)}))
    m_o = sm.OLS(L(op.af_2004_to_last), Xo).fit(cov_type="HC3")
    old_fields["checks"] = {"rho_absolute_new_wells": spearman(op.wells_2005_2025.astype(float), L(op.af_2004_to_last)),
                            "rho_discoveries_added": spearman(op.n_discoveries_added_after_start.astype(float), L(op.af_2004_to_last)),
                            "rho_size": spearman(L(op.oe_2004), L(op.af_2004_to_last)),
                            "regression_with_size": {k: {"coef": float(m_o.params[k]), "p": float(m_o.pvalues[k])} for k in ("log_rel", "log_size")},
                            "note": "In percentage terms small older fields grew most, and they also have the most new wells per old well. With size in the regression the drilling term stays positive but is no longer clear."}
    drilling = {"new_fields": new_fields, "old_fields": old_fields,
                "caveat": "Wells and reserves move together by construction of the accounts: reserves are booked when a well or project is decided. The data show that growth is drilled, not which way the causality runs."}

    # ------------------------------------------------------------------ robustness of the three results
    rob = {"size_thresholds_mmboe": []}
    for thr in (50, 100, 200, 300):
        sm_ = c.pre_oe * SM3_TO_BBL < thr
        a_, b_ = np.abs(L(c[sm_].afp3)), np.abs(L(c[~sm_].afp3))
        rob["size_thresholds_mmboe"].append({"threshold": thr, "n_small": int(sm_.sum()), "n_large": int((~sm_).sum()),
                                             "small_typical": float(np.exp(a_.median()) - 1), "large_typical": float(np.exp(b_.median()) - 1), "p": mwu(a_, b_)})
    rob["size_rho_by_horizon"] = {str(k): spearman(L(c.pre_oe), np.abs(L(c[f"afp{k}"]))) for k in (1, 3, 5)}
    act = c[c.status == "Producing"]
    rob["size_rho_3y_fields_still_producing"] = spearman(L(act.pre_oe), np.abs(L(act.afp3)))
    loo = []
    for i in c.index:
        dd = c.drop(i)
        loo.append(mwu(np.abs(L(dd[dd.small].afp3)), np.abs(L(dd[~dd.small].afp3))))
    rob["size_leave_one_out_p_range"] = [float(min(loo)), float(max(loo))]
    gg = f[(f.t0 > 2004) & f.pre_oe.notna()]
    rob["timing_variants"] = []
    for follow in (5, 6, 8):
        for dn_thr, up_thr in ((0.8, 1.25), (0.85, 1.15), (0.7, 1.4)):
            x = gg[(2025 - gg.t0) >= follow]
            dn, up = x[x.afp_last <= dn_thr], x[x.afp_last >= up_thr]
            sd, su = (L(dn.afp1) / L(dn.afp_last)).dropna(), (L(up.afp1) / L(up.afp_last)).dropna()
            rob["timing_variants"].append({"min_years": follow, "down_at_most": dn_thr, "up_at_least": up_thr, "n_down": int(len(sd)), "n_up": int(len(su)),
                                           "down_share_year1": float(sd.median()), "up_share_year1": float(su.median()), "p": mwu(sd, su)})

    out = {"meta": {"generated": dt.date.today().isoformat(), "n": int(len(c)), "small_msm3": SMALL,
                    "base": "last estimate before the start-up year (resource account 31.12 of year t0-1)",
                    "fields_without_pre_start_estimate": f[(f.t0 >= 2004) & f.pre_oe.isna() & f.cohort].name.tolist(),
                    "hypotheses": {"H1": "small fields revised down / revised more", "H2": "few exploration and appraisal wells -> larger revisions",
                                   "H3": "few wells at start-up -> wider spread", "H4": "later growth goes with later drilling",
                                   "H5": "deep / HPHT / complex -> revised down", "H6": "downgrades come earlier than upgrades",
                                   "H7": "size effect also in Watkins' fields"}},
           "overall": overall, "size": size, "watkins": watkins, "other": other, "categories": cats, "wells_at_start": wells_split,
           "regression": regress, "models": models, "timing": timing, "drilling": drilling, "robustness": rob}
    write_json(WEB_DATA / "hard.json", out)

    o3 = overall["y3"]
    print(f"overall 3y: n={o3['n']} median {o3['median']:.3f} {np.round(o3['ci90'], 2)} down {o3['n_down']} up {o3['n_up']} large {o3['share_large']:.2f}; 5y median {overall['y5']['median']:.3f} large {overall['y5']['share_large']:.2f}")
    s3 = size["at"]["3"]
    print(f"size 3y: small typical {s3['small']['typical_change']:.2f} down {s3['small']['share_down']:.2f} | large typical {s3['large']['typical_change']:.2f} down {s3['large']['share_down']:.2f} | p_mag {s3['p_magnitude']:.3f} p_dir {s3['p_direction']:.3f}; ratio {size['ratio_typical_3y']}")
    print("watkins", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in watkins.items() if k not in ("groups", "note")})
    print("timing", {k: v for k, v in timing.items() if k not in ("path", "names")})
    print("drilling new", {k: v for k, v in new_fields.items() if k != "definition"})
    print("drilling old producing", old_fields["rho_producing"], [(t["label"], t["n"], round(t["median_growth"], 3)) for t in old_fields["terciles_producing"]])
    print("wells at start", wells_split["few"]["typical_change"], wells_split["more"]["typical_change"], wells_split["p_magnitude"])
    print("regress", regress)
    for mm in models:
        print("  model", mm["label"], "n", mm["n"], "pos", mm["positives"], "AUC", round(mm["cv_auc"], 2), np.round(mm["cv_auc_range90"], 2), "null95", round(mm["null_auc_p95"], 2), "p", round(mm["permutation_p"], 3))
    for r in other:
        print(f"  {r['label'][:48]:48s} dir3 {r['direction_3y']['rho']:+.2f} p={r['direction_3y']['p']:.2f} | mag3 {r['magnitude_3y']['rho']:+.2f} p={r['magnitude_3y']['p']:.2f} | dir5 {r['direction_5y']['rho']:+.2f} p={r['direction_5y']['p']:.2f} | mag5 {r['magnitude_5y']['rho']:+.2f} p={r['magnitude_5y']['p']:.2f}")
    for r in cats:
        print(f"  {r['label'][:40]:40s} yes n={r['yes']['n']} med {r['yes']['median']:.2f} typ {r['yes']['typical_change']:.2f} | no n={r['no']['n']} med {r['no']['median']:.2f} typ {r['no']['typical_change']:.2f} | p_dir {r['p_direction']:.2f} p_mag {r['p_magnitude']:.2f}")


if __name__ == "__main__":
    main()
