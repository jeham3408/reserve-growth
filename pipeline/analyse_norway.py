#!/usr/bin/env python3
"""Step 2 (Norway): appreciation curves, tables, drivers of early revisions, literature tests.

Reads derived/norway_*.csv (from build_norway.py), writes web/data/norway.json and derived/*.csv tables.
Methods are deliberately simple: quantiles, rank correlation, group medians with bootstrap intervals,
and a small cross-validated logistic regression / decision tree. n is about 60, so intervals are wide.
"""
from __future__ import annotations

import datetime as dt
import json
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

from common import DERIVED, SM3_TO_BBL, WEB_DATA, boot_ci, write_json

warnings.filterwarnings("ignore")
RNG = np.random.default_rng(20261119)

LARGE_UP, LARGE_DOWN = 1.25, 0.80          # "large revision" = outside 0.80-1.25 (symmetric in log)
SMALL_MMBOE = 100                           # GEO ExPro 2021 threshold for a "small" field
SMALL_MSM3 = SMALL_MMBOE / SM3_TO_BBL       # = 15.9 million Sm3 o.e.


def q(series, p):
    return float(np.quantile(series, p)) if len(series) else float("nan")


def classify(af: float) -> str:
    if pd.isna(af):
        return "n/a"
    return "up" if af >= LARGE_UP else ("down" if af <= LARGE_DOWN else "stable")


def hc_group(hc: str) -> str:
    return {"OIL": "Oil", "OIL/CONDENSATE": "Oil", "OIL/GAS": "Oil and gas", "GAS": "Gas", "GAS/CONDENSATE": "Gas"}.get(hc, "Unknown")


def size_class(v: float) -> str:
    if pd.isna(v):
        return "n/a"
    return "Small (<100 MMboe)" if v < SMALL_MSM3 else ("Medium (100-300 MMboe)" if v < 3 * SMALL_MSM3 else "Large (>300 MMboe)")


def spearman_boot(x, y, n_boot=4000):
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    rho, p = stats.spearmanr(x, y)
    idx = RNG.integers(0, len(x), size=(n_boot, len(x)))
    boots = np.array([stats.spearmanr(x[i], y[i])[0] for i in idx])
    lo, hi = np.nanquantile(boots, [0.05, 0.95])
    return {"n": int(len(x)), "rho": float(rho), "p": float(p), "ci90": [float(lo), float(hi)]}


def group_table(df, col, af_col, order=None):
    out = []
    groups = order or sorted(df[col].dropna().unique(), key=str)
    samples = []
    for g in groups:
        s = df[df[col] == g][af_col].dropna()
        if len(s) == 0:
            continue
        samples.append(np.log(s.values))
        lo, hi = boot_ci(s.values)
        cls = s.map(classify)
        out.append({"group": str(g), "n": int(len(s)), "median_af": float(s.median()), "ci90": [lo, hi],
                    "p25": q(s, .25), "p75": q(s, .75),
                    "share_large": float((cls != "stable").mean()), "share_down": float((cls == "down").mean()),
                    "share_up": float((cls == "up").mean()),
                    "median_abs_log": float(np.abs(np.log(s)).median()),
                    "values": [float(v) for v in s.values], "names": df.loc[s.index, "name"].tolist()})
    test = None
    big = [s for s in samples if len(s) >= 3]
    if len(big) >= 2:
        if len(big) == 2:
            stat, p = stats.mannwhitneyu(big[0], big[1], alternative="two-sided")
            test = {"test": "Mann-Whitney U", "p": float(p)}
            stat2, p2 = stats.mannwhitneyu(np.abs(big[0]), np.abs(big[1]), alternative="two-sided")
            test["p_magnitude"] = float(p2)
        else:
            stat, p = stats.kruskal(*big)
            test = {"test": "Kruskal-Wallis", "p": float(p)}
            stat2, p2 = stats.kruskal(*[np.abs(s) for s in big])
            test["p_magnitude"] = float(p2)
    return {"groups": out, "test": test}


def model_block(df, target_col, features, label):
    """Cross-validated logistic regression and depth-2 tree for a binary target."""
    d = df.dropna(subset=[target_col]).copy()
    X = d[features].astype(float)
    X = X.fillna(X.median())
    y = d[target_col].astype(int).values
    base_rate = float(y.mean())
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=40, random_state=7)
    logit = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000))
    auc = cross_val_score(logit, X, y, cv=cv, scoring="roc_auc")
    acc = cross_val_score(logit, X, y, cv=cv, scoring="accuracy")
    auc_by_repeat = auc.reshape(40, 5).mean(axis=1)
    # permutation null: shuffle the labels, same CV
    null = []
    cv_small = RepeatedStratifiedKFold(n_splits=5, n_repeats=4, random_state=7)
    observed_small = cross_val_score(logit, X, y, cv=cv_small, scoring="roc_auc").mean()
    for _ in range(300):
        yp = RNG.permutation(y)
        null.append(cross_val_score(logit, X, yp, cv=cv_small, scoring="roc_auc").mean())
    null = np.array(null)
    p_perm = float((np.sum(null >= observed_small) + 1) / (len(null) + 1))
    logit.fit(X, y)
    coefs = dict(zip(features, logit[-1].coef_[0]))
    tree = DecisionTreeClassifier(max_depth=2, min_samples_leaf=8, random_state=0)
    tree_acc = cross_val_score(tree, X, y, cv=cv, scoring="accuracy")
    tree.fit(X, y)
    return {
        "label": label, "n": int(len(y)), "positives": int(y.sum()), "base_rate": base_rate,
        "majority_accuracy": float(max(base_rate, 1 - base_rate)),
        "logit_cv_auc_mean": float(auc.mean()), "logit_cv_auc_range90": [q(auc_by_repeat, .05), q(auc_by_repeat, .95)],
        "logit_cv_accuracy": float(acc.mean()),
        "permutation_null_auc_mean": float(null.mean()), "permutation_null_auc_p95": q(null, .95), "permutation_p": p_perm,
        "logit_std_coefficients": {k: float(v) for k, v in sorted(coefs.items(), key=lambda kv: -abs(kv[1]))},
        "tree_cv_accuracy": float(tree_acc.mean()), "tree_rules": export_text(tree, feature_names=features, decimals=2),
        "features": features,
    }


def sodir_prod_totals():
    from common import sodir
    py = sodir("field_production_yearly")
    return py.groupby("prfYear").prfPrdOeNetMillSm3.sum().to_dict()


def main() -> None:
    f = pd.read_csv(DERIVED / "norway_fields.csv")
    est = pd.read_csv(DERIVED / "norway_estimates.csv")
    checks = json.loads((DERIVED / "norway_checks.json").read_text())
    f["hc_group"] = f.hc_type.map(hc_group)
    f["size_class"] = f.base_oe.map(size_class)
    f["log_size"] = np.log10(f.base_oe)
    for k in (3, 5):
        f[f"class{k}"] = f[f"af{k}"].map(classify)
        f[f"large{k}"] = np.where(f[f"af{k}"].notna(), f[f"class{k}"] != "stable", np.nan)
        f[f"down{k}"] = np.where(f[f"af{k}"].notna(), f[f"class{k}"] == "down", np.nan)
    c = f[f.cohort].copy()
    ce = est[est.id.isin(c.id) & (est.k >= 0)].copy()

    # ------------------------------------------------------------ 1. curves
    curve = []
    for k, g in ce.groupby("k"):
        if len(g) >= 5:
            curve.append({"k": int(k), "n": int(len(g)), "p10": q(g.af, .1), "p25": q(g.af, .25), "median": q(g.af, .5),
                          "p75": q(g.af, .75), "p90": q(g.af, .9), "mean": float(g.af.mean()),
                          "weighted": float(g.oe.sum() / g.id.map(c.set_index("id").base_oe).sum())})
    # same curve with a fixed set of fields (those followed at least 10 years), to separate drift from changing sample
    long_ids = c[c.years_followed >= 10].id
    curve_fixed = []
    for k, g in ce[ce.id.isin(long_ids) & (ce.k <= 10)].groupby("k"):
        curve_fixed.append({"k": int(k), "n": int(len(g)), "p10": q(g.af, .1), "median": q(g.af, .5), "p90": q(g.af, .9)})

    def headline(k):
        s = c[f"af{k}"].dropna()
        cls = s.map(classify)
        ids = c.loc[s.index, "id"]
        w_base = c.loc[s.index, "base_oe"].sum()
        w_now = (s * c.loc[s.index, "base_oe"]).sum()
        big = c.loc[s.index].sort_values("base_oe", ascending=False).head(2)
        rest = c.loc[s.index].drop(big.index)
        return {"k": k, "n": int(len(s)), "median": float(s.median()), "median_ci90": list(boot_ci(s.values)),
                "p10": q(s, .1), "p25": q(s, .25), "p75": q(s, .75), "p90": q(s, .9),
                "share_down": float((cls == "down").mean()), "share_up": float((cls == "up").mean()),
                "share_large": float((cls != "stable").mean()),
                "share_large_ci90": list(boot_ci((cls != "stable").astype(float).values, stat=np.mean)),
                "n_down": int((cls == "down").sum()), "n_up": int((cls == "up").sum()), "n_stable": int((cls == "stable").sum()),
                "median_abs_change": float((s - 1).abs().median()),
                "volume_weighted_af": float(w_now / w_base), "sum_base_oe": float(w_base), "sum_now_oe": float(w_now),
                "volume_weighted_af_without_two_largest": float((rest[f"af{k}"] * rest.base_oe).sum() / rest.base_oe.sum()),
                "two_largest": big.name.tolist()}
    head = {f"af{k}": headline(k) for k in (1, 3, 5, 10)}
    s = c.af_last
    head["latest"] = {"n": int(len(s)), "median": float(s.median()), "median_ci90": list(boot_ci(s.values)), "p10": q(s, .1), "p90": q(s, .9),
                      "share_down": float((s <= LARGE_DOWN).mean()), "share_up": float((s >= LARGE_UP).mean()),
                      "volume_weighted_af": float(c.last_oe.sum() / c.base_oe.sum()),
                      "sum_base_oe": float(c.base_oe.sum()), "sum_last_oe": float(c.last_oe.sum())}

    # ------------------------------------------------------------ 2. tables
    cols = ["name", "t0", "base_oe", "last_oe", "af3", "af5", "af_last", "years_followed", "hc_type", "area", "concept"]
    c["abs_change"] = c.last_oe - c.base_oe
    tables = {
        "largest_up_ratio": c.sort_values("af_last", ascending=False).head(10)[cols + ["abs_change"]].to_dict("records"),
        "largest_down_ratio": c.sort_values("af_last").head(10)[cols + ["abs_change"]].to_dict("records"),
        "largest_up_volume": c.sort_values("abs_change", ascending=False).head(10)[cols + ["abs_change"]].to_dict("records"),
        "largest_down_volume": c.sort_values("abs_change").head(10)[cols + ["abs_change"]].to_dict("records"),
    }
    c.sort_values("af_last", ascending=False)[["name", "t0", "base_year", "base_oe", "af1", "af3", "af5", "af_last", "last_oe", "abs_change",
                                               "years_followed", "hc_type", "area", "concept", "operator_at_start"]].round(3).to_csv(DERIVED / "table_cohort_revisions.csv", index=False)

    # ------------------------------------------------------------ 3. drivers
    numeric = {
        "log_size": "Field size (first estimate, log)",
        "base_gas_share": "Gas share of first estimate",
        "rf_first": "First estimate / in-place volume (2025 snapshot)",
        "water_depth_m": "Water depth (m)",
        "reservoir_depth_m": "Reservoir depth (m)",
        "t0": "Start-up year",
        "lead_time_discovery_to_start": "Years from discovery to start-up",
        "n_discoveries_added_after_start": "Discoveries added to the field after start-up",
    }
    categorical = {
        "size_class": ("Field size", ["Small (<100 MMboe)", "Medium (100-300 MMboe)", "Large (>300 MMboe)"]),
        "hc_group": ("Hydrocarbon type", ["Oil", "Oil and gas", "Gas"]),
        "area": ("Area", ["North Sea", "Norwegian Sea", "Barents Sea"]),
        "concept": ("Development concept", ["Own facility", "Satellite / tie-back"]),
        "operator_group": ("Operator at start-up", ["Equinor/Statoil/Hydro", "Other operator"]),
        "reservoir_age": ("Main reservoir age", ["Cenozoic", "Cretaceous", "Jurassic", "Triassic or older"]),
        "recovery_strategy": ("Recovery strategy", ["Depletion / natural drive", "Injection (water/gas)"]),
        "text_complex": ("Described as complex / segmented (today's text)", [False, True]),
        "text_hpht": ("High pressure / HPHT (today's text)", [False, True]),
        "start_era": ("Start-up period", ["2004-2009", "2010-2014", "2015-2022"]),
    }
    c["start_era"] = pd.cut(c.t0, [2003, 2009, 2014, 2030], labels=["2004-2009", "2010-2014", "2015-2022"]).astype(str)
    drivers = {"numeric": [], "categorical": []}
    for k in (3, 5):
        y = np.log(c[f"af{k}"].values.astype(float))
        for col, label in numeric.items():
            x = c[col].values.astype(float)
            drivers["numeric"].append({"feature": col, "label": label, "horizon": k,
                                       "signed": spearman_boot(x, y), "magnitude": spearman_boot(x, np.abs(y))})
        for col, (label, order) in categorical.items():
            t = group_table(c, col, f"af{k}", order)
            drivers["categorical"].append({"feature": col, "label": label, "horizon": k, **t})
    n_tests = len(drivers["numeric"]) * 2 + len(drivers["categorical"]) * 2
    drivers["n_tests"] = n_tests
    drivers["note"] = (f"{n_tests} tests were run; with a 5 % threshold about {n_tests * 0.05:.0f} would look significant by chance alone.")

    # models
    c["is_tieback"] = c.tieback.astype(float)
    c["is_gas"] = (c.hc_group == "Gas").astype(float)
    c["is_norwegian_sea"] = (c.area == "Norwegian Sea").astype(float)
    c["is_other_operator"] = (c.operator_group == "Other operator").astype(float)
    c["is_complex_text"] = c.text_complex.astype(float)
    c["is_injection"] = (c.recovery_strategy == "Injection (water/gas)").astype(float)
    feats = ["log_size", "rf_first", "is_tieback", "is_gas", "is_norwegian_sea", "is_other_operator", "water_depth_m",
             "reservoir_depth_m", "t0", "is_injection"]
    models = [
        model_block(c, "large5", feats, "Large revision (outside 0.80-1.25) within 5 years"),
        model_block(c, "down5", feats, "Downgrade of 20 % or more within 5 years"),
        model_block(c, "large3", feats, "Large revision (outside 0.80-1.25) within 3 years"),
        model_block(c, "down3", feats, "Downgrade of 20 % or more within 3 years"),
    ]

    # dispersion by size: is the spread larger for small fields? (ratio of |log AF| medians, bootstrap)
    small = np.abs(np.log(c[c.base_oe < SMALL_MSM3].af5.dropna().values))
    big = np.abs(np.log(c[c.base_oe >= SMALL_MSM3].af5.dropna().values))
    diffs = [np.median(RNG.choice(small, len(small))) - np.median(RNG.choice(big, len(big))) for _ in range(4000)]
    size_spread = {"n_small": int(len(small)), "n_other": int(len(big)),
                   "median_abs_change_small": float(np.exp(np.median(small)) - 1), "median_abs_change_other": float(np.exp(np.median(big)) - 1),
                   "diff_abs_log_ci90": [q(diffs, .05), q(diffs, .95)],
                   "mannwhitney_p": float(stats.mannwhitneyu(small, big).pvalue)}

    # early warning: does the first-year revision predict the 5-year revision?
    ok = c.af1.notna() & c.af5.notna()
    persistence = spearman_boot(np.log(c.af1[ok].values), np.log(c.af5[ok].values))
    same_dir = c[ok & ((c.af1 - 1).abs() >= 0.05)]
    persistence["n_moved_5pct_in_year1"] = int(len(same_dir))
    persistence["share_same_direction_at_5y"] = float((np.sign(same_dir.af1 - 1) == np.sign(same_dir.af5 - 1)).mean())
    # momentum: does the first-year revision predict the change that comes AFTER it (year 1 -> year 5)?
    later = np.log(c.af5[ok].values / c.af1[ok].values)
    persistence["momentum_year1_vs_later_change"] = spearman_boot(np.log(c.af1[ok].values), later)
    ok35 = c.af3.notna() & c.af_last.notna() & (c.years_followed >= 8)
    persistence["momentum_year3_vs_later_change"] = spearman_boot(np.log(c.af3[ok35].values), np.log(c.af_last[ok35].values / c.af3[ok35].values))
    ok3 = c.af3.notna() & c.af_last.notna() & (c.years_followed >= 8)
    persistence["af3_vs_latest_min8y"] = spearman_boot(np.log(c.af3[ok3].values), np.log(c.af_last[ok3].values))

    # ------------------------------------------------------------ 4. literature tests
    lit = {}
    # GEO ExPro / Wittemann 2021: small fields started since 2010, PDO estimate vs latest
    g = f[(f.t0 >= 2010) & f.af_pdo_to_last.notna()].copy()
    g["small_pdo"] = g.pdo_base_oe < SMALL_MSM3
    def geo(sub):
        s = sub.af_pdo_to_last
        return {"n": int(len(s)), "median": float(s.median()), "median_ci90": list(boot_ci(s.values)),
                "share_below_1": float((s < 1).mean()), "share_down_20": float((s <= LARGE_DOWN).mean()),
                "share_up_25": float((s >= LARGE_UP).mean()), "share_down_60": float((s <= 0.4).mean()),
                "sum_pdo": float(sub.pdo_base_oe.sum()), "sum_last": float(sub.last_oe.sum()),
                "weighted": float(sub.last_oe.sum() / sub.pdo_base_oe.sum()),
                "down_60_names": sub[s <= 0.4].name.tolist()}
    lit["geoexpro_small_fields"] = {
        "claim": "Fields under 100 MMboe that started since 2010 tend to shrink after start-up; large fields are more predictable (Wittemann / GEO ExPro, May 2021).",
        "our_test": "Start-up 2010 or later, first Sodir estimate before start-up (approx. PDO) compared with the latest estimate.",
        "threshold_msm3": SMALL_MSM3,
        "small": geo(g[g.small_pdo]), "not_small": geo(g[~g.small_pdo]), "all": geo(g),
        "mannwhitney_p": float(stats.mannwhitneyu(np.log(g[g.small_pdo].af_pdo_to_last), np.log(g[~g.small_pdo].af_pdo_to_last)).pvalue),
        "same_test_start_2004_2009": {"small": geo(f[(f.t0 >= 2004) & (f.t0 < 2010) & f.af_pdo_to_last.notna() & (f.pdo_base_oe < SMALL_MSM3)]),
                                      "not_small": geo(f[(f.t0 >= 2004) & (f.t0 < 2010) & f.af_pdo_to_last.notna() & (f.pdo_base_oe >= SMALL_MSM3)])},
        "fields": g[["name", "t0", "pdo_base_year", "pdo_base_oe", "last_oe", "af_pdo_to_last", "small_pdo"]].to_dict("records"),
    }
    # where does the shrinkage of small fields happen: between approval and start-up, or after start-up?
    g2 = g.copy()
    g2["af_start_to_last"] = g2.af_last
    lit["geoexpro_small_fields"]["split"] = {
        name: {"n": int(len(sub)), "median_pdo_to_start": float(sub.af_pdo_to_start.median()), "median_start_to_last": float(sub.af_start_to_last.median()),
               "median_pdo_to_last": float(sub.af_pdo_to_last.median()),
               "median_years_pdo_row_to_start": float((sub.t0 - sub.pdo_base_year).median())}
        for name, sub in (("small", g2[g2.small_pdo]), ("not_small", g2[~g2.small_pdo]))}
    # chalk: fields on stream before 2004, change 2004 -> latest
    p = f[f.pre2004].copy()
    p["active"] = p.status.eq("Producing")
    def grp(sub):
        s = sub.af_2004_to_last
        return {"n": int(len(s)), "median": float(s.median()), "median_ci90": list(boot_ci(s.values)), "p25": q(s, .25), "p75": q(s, .75),
                "weighted": float(sub.last_oe.sum() / sub.oe_2004.sum()), "sum_2004": float(sub.oe_2004.sum()), "sum_last": float(sub.last_oe.sum()),
                "fields": sub.sort_values("af_2004_to_last", ascending=False)[["name", "t0", "oe_2004", "last_oe", "af_2004_to_last", "status"]].to_dict("records")}
    lit["chalk"] = {
        "claim": "Chalk fields grow the most in per cent.",
        "our_test": "Fields on stream before 2004: latest estimate / estimate at 31.12.2004, chalk against sandstone. This enters mid-life; growth before 2004 is not in the Sodir table (see the Watkins comparison for that).",
        "chalk_all": grp(p[p.lithology == "Chalk"]), "sandstone_all": grp(p[p.lithology == "Sandstone"]),
        "chalk_producing": grp(p[(p.lithology == "Chalk") & p.active]), "sandstone_producing": grp(p[(p.lithology == "Sandstone") & p.active]),
    }
    a, b = p[(p.lithology == "Chalk") & p.active].af_2004_to_last, p[(p.lithology == "Sandstone") & p.active].af_2004_to_last
    lit["chalk"]["mannwhitney_p_producing"] = float(stats.mannwhitneyu(a, b).pvalue)

    # ------------------------------------------------------------ 5. mid-life (2004 base) summary
    s = p.af_2004_to_last
    pa = p[p.active]
    mid = {"n": int(len(p)), "median": float(s.median()), "median_ci90": list(boot_ci(s.values)), "p10": q(s, .1), "p90": q(s, .9),
           "weighted": float(p.last_oe.sum() / p.oe_2004.sum()), "sum_2004": float(p.oe_2004.sum()), "sum_last": float(p.last_oe.sum()),
           "n_still_producing": int(len(pa)), "median_still_producing": float(pa.af_2004_to_last.median()),
           "weighted_still_producing": float(pa.last_oe.sum() / pa.oe_2004.sum()),
           "share_up_25_still_producing": float((pa.af_2004_to_last >= LARGE_UP).mean()),
           "share_below_1_still_producing": float((pa.af_2004_to_last < 1).mean())}

    # ------------------------------------------------------------ robustness and published totals
    # Sodir notice of 26.02.2026: the first publication of the 31.12.2025 field figures had wrong *remaining* reserves.
    # We use recoverable volumes, but repeat the headline with the 2024 accounts as the last year.
    e24 = est[(est.year <= 2024) & est.id.isin(c.id) & (est.k >= 0)].sort_values("year").groupby("id").last()
    af24 = (e24.oe / e24.index.map(c.set_index("id").base_oe)).dropna()
    robust = {"latest_using_2024_accounts": {"n": int(len(af24)), "median": float(af24.median()), "p10": q(af24, .1), "p90": q(af24, .9),
                                             "share_down": float((af24 <= LARGE_DOWN).mean()), "share_up": float((af24 >= LARGE_UP).mean())},
              "rows_2025_with_2024_date": ["FRØY", "LILLE-FRIGG"]}
    tot = {int(r["year"]): r for r in checks["totals_by_year"]}
    prod_all = sodir_prod_totals()
    published = []
    for year, total, sold_pct, res_pct, prod_pub, url in (
            (2025, 15722, 57, 14, 243, "https://www.sodir.no/en/whats-new/news/general-news/2026/high-production-and-increase-in-petroleum-resources/"),
            (2024, 15611, 56, 15, 239, "https://www.sodir.no/en/whats-new/news/general-news/2025/minor-increase-in-oil-and-gas-resources-on-the-ncs/")):
        t = tot[year]
        published.append({"year": year, "published_total_resources": total, "published_sold_pct": sold_pct, "published_reserves_pct": res_pct,
                          "published_production": prod_pub, "our_sold": t["sold_oe"], "our_remaining": t["remaining_oe"],
                          "our_sold_pct": 100 * t["sold_oe"] / total, "our_reserves_pct": 100 * t["remaining_oe"] / total,
                          "our_production": float(prod_all.get(year, np.nan)), "source": url,
                          "production_source": url.replace("/news/general-news/", "/publications/reports/resource-accounts/") if False else
                          f"https://www.sodir.no/en/whats-new/publications/reports/resource-accounts/resource-accounts-{year}/resource-accounts/"})
    # Sleipner area: the production table books Sleipner Vest and Gungne gas on Sleipner Øst. Compare the three together.
    from common import sodir as _sodir
    _py = _sodir("field_production_yearly"); _py = _py[_py.prfYear <= 2025]
    _trio = ["SLEIPNER ØST", "SLEIPNER VEST", "GUNGNE"]
    _last = est[est.name.isin(_trio)].sort_values("year").groupby("name").last()
    checks["sleipner_area"] = {"fields": _trio,
                               "production_table_sum": float(_py[_py.prfInformationCarrier.isin(_trio)].prfPrdOeNetMillSm3.sum()),
                               "recoverable_minus_remaining_sum": float((_last.oe - _last.remaining_oe).sum())}
    checks["published_totals"] = published
    checks["robustness"] = robust
    checks["sodir_notice_2026_02_26"] = ("Sodir, 26.02.2026: the field reserve figures as of 31.12.2025 published on 20.02.2026 contained incorrect numbers for remaining "
                                         "reserves and were being updated. Our download of 19.11.2026 has 31.12.2025 figures for all fields except Frøy and Lille-Frigg.")

    # ------------------------------------------------------------ 6. field records for the web page
    prod = pd.read_csv(DERIVED / "norway_estimates.csv")
    from common import sodir
    py = sodir("field_production_yearly").rename(columns={"prfNpdidInformationCarrier": "id", "prfYear": "year", "prfPrdOeNetMillSm3": "p"})
    fields = []
    for _, r in f.sort_values("name").iterrows():
        g = est[est.id == r.id].sort_values("year")
        pr = py[py.id == r.id].sort_values("year")
        rec = {"id": int(r.id), "name": r["name"], "t0": r.t0, "area": r.area, "hc": r.hc_type, "hcg": r.hc_group, "status": r.status,
               "op": r.operator_now, "op0": r.operator_at_start, "opg": r.operator_group, "disc": r.discovery_year, "pdo": r.pdo_year,
               "wd": r.water_depth_m, "rd": r.reservoir_depth_m, "lith": r.lithology, "age": r.reservoir_age, "concept": r.concept,
               "rec": r.recovery_strategy, "inplace": r.inplace_oe, "rf0": r.rf_first, "rfl": r.rf_last,
               "cohort": bool(r.cohort), "pre2004": bool(r.pre2004), "by": r.base_year, "b": r.base_oe, "sz": r.size_class,
               "af1": r.af1, "af3": r.af3, "af5": r.af5, "afl": r.af_last, "afpdo": r.af_pdo_to_last, "af04": r.af_2004_to_last,
               "pre": r.pre_oe, "afp1": r.afp1, "afp3": r.afp3, "afp5": r.afp5, "afpl": r.afp_last,
               "nexp": r.n_expl_wells_pre, "ndev0": r.n_dev_wells_by_start, "ndevl": r.n_dev_wellbores_after_y1,
               "c3": r.class3, "c5": r.class5, "added": r.n_discoveries_added_after_start, "restart": bool(r.restarted),
               "url": r.url,
               "y": g.year.tolist(), "oe": g.oe.tolist(), "oil": g.oil.tolist(), "gas": g.gas.tolist(),
               "ngl": g.ngl.tolist(), "cond": g.cond.tolist(), "rem": g.remaining_oe.tolist(),
               "py": pr.year.tolist(), "p": pr.p.round(3).tolist()}
        fields.append(rec)

    out = {
        "meta": {"generated": dt.date.today().isoformat(), "source": "Sodir FactPages (NLOD)", "raw_files": checks["sources"],
                 "unit": "million Sm3 oil equivalents (recoverable, originally)", "n_fields": int(len(f)), "n_rows": int(len(est)),
                 "years": [int(est.year.min()), int(est.year.max())], "cohort_n": int(len(c)), "pre2004_n": int(len(p)),
                 "large_thresholds": [LARGE_DOWN, LARGE_UP], "small_msm3": SMALL_MSM3, "sm3_to_bbl": SM3_TO_BBL},
        "headline": head, "curve": curve, "curve_fixed": curve_fixed, "tables": tables, "drivers": drivers, "models": models,
        "size_spread": size_spread, "persistence": persistence, "literature": lit, "midlife": mid, "checks": checks, "fields": fields,
    }
    write_json(WEB_DATA / "norway.json", out)
    write_json(DERIVED / "norway_summary.json", {k: v for k, v in out.items() if k != "fields"})

    # console summary
    for k in ("af3", "af5", "af10", "latest"):
        h = head[k]
        print(k, {x: (round(v, 3) if isinstance(v, float) else v) for x, v in h.items() if x not in ("two_largest",)})
    print("midlife", {x: round(v, 3) if isinstance(v, float) else v for x, v in mid.items()})
    print("size_spread", size_spread)
    print("published", [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items() if "source" not in k} for r in published])
    print("robust", robust)
    print("split", lit["geoexpro_small_fields"]["split"])
    print("persistence", persistence)
    for d in drivers["numeric"]:
        if d["horizon"] == 5:
            print(f"  {d['label'][:45]:45s} signed rho={d['signed']['rho']:+.2f} [{d['signed']['ci90'][0]:+.2f},{d['signed']['ci90'][1]:+.2f}] p={d['signed']['p']:.3f} | magnitude rho={d['magnitude']['rho']:+.2f} [{d['magnitude']['ci90'][0]:+.2f},{d['magnitude']['ci90'][1]:+.2f}] p={d['magnitude']['p']:.3f}")
    for d in drivers["categorical"]:
        if d["horizon"] == 5:
            print(" ", d["label"], d["test"])
            for g in d["groups"]:
                print(f"      {g['group'][:28]:28s} n={g['n']:2d} median={g['median_af']:.2f} [{g['ci90'][0]:.2f},{g['ci90'][1]:.2f}] large={g['share_large']:.0%} down={g['share_down']:.0%} up={g['share_up']:.0%}")
    for m in models:
        print(m["label"], "n", m["n"], "pos", m["positives"], "AUC", round(m["logit_cv_auc_mean"], 2), m["logit_cv_auc_range90"], "null p95", round(m["permutation_null_auc_p95"], 2), "p", round(m["permutation_p"], 3), "tree acc", round(m["tree_cv_accuracy"], 2), "majority", round(m["majority_accuracy"], 2))
        print("   ", {k: round(v, 2) for k, v in list(m["logit_std_coefficients"].items())[:5]})
        print(m["tree_rules"])
    ge = lit["geoexpro_small_fields"]
    print("GEO small", {k: v for k, v in ge["small"].items()}, "\nnot small", ge["not_small"], "p", ge["mannwhitney_p"])
    print("2004-2009", ge["same_test_start_2004_2009"])
    for k in ("chalk_all", "sandstone_all", "chalk_producing", "sandstone_producing"):
        print(k, {x: v for x, v in lit["chalk"][k].items() if x != "fields"})
    print("chalk p", lit["chalk"]["mannwhitney_p_producing"])


if __name__ == "__main__":
    main()
