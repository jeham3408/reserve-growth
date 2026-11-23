#!/usr/bin/env python3
"""Step 1 (Norway): join the Sodir FactPages tables into one tidy data set.

Outputs
    derived/norway_estimates.csv   one row per field and resource-account year
    derived/norway_fields.csv      one row per field: start year, features, appreciation factors
    derived/norway_checks.json     data-quality checks

Every column is traceable to a FactPages table/column; see the docstrings and README.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from common import DERIVED, newest, sodir

BASE_YEAR_ALL = 2004  # first resource-account year in field_reserves
COHORT_MIN_ESTIMATES = 4


def first_number(text: str, pattern: str):
    """Mean of the numbers in the first match of `pattern` (handles '2400-2600')."""
    m = re.search(pattern, text or "", flags=re.I)
    if not m:
        return np.nan
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", m.group(1).replace(",", ""))]
    return float(np.mean(nums)) if nums else np.nan


AGE_WORDS = [
    ("Pliocene", "Cenozoic"), ("Miocene", "Cenozoic"), ("Oligocene", "Cenozoic"), ("Eocene", "Cenozoic"),
    ("Paleocene", "Cenozoic"), ("Palaeocene", "Cenozoic"), ("Cretaceous", "Cretaceous"),
    ("Jurassic", "Jurassic"), ("Triassic", "Triassic or older"), ("Permian", "Triassic or older"),
    ("Carboniferous", "Triassic or older"), ("Devonian", "Triassic or older"),
]


def reservoir_age(text: str) -> str:
    """Main reservoir age = the age word mentioned first in the Sodir 'Reservoir' text."""
    best = (10**9, "Unknown")
    for word, group in AGE_WORDS:
        pos = (text or "").find(word)
        if 0 <= pos < best[0]:
            best = (pos, group)
    return best[1]


# Manual corrections to the facility rule, each read from the Sodir 'Development' text of the field.
CONCEPT_OVERRIDES = [
    ("ENOCH", "Satellite / tie-back", "one production well tied to the British Brae field; the listed jacket is the host"),
    ("SNØHVIT", "Own facility", "subsea to shore with its own LNG plant at Melkøya; not a tie-back to another field"),
    ("ORMEN LANGE", "Own facility", "subsea to shore with its own plant at Nyhamna; not a tie-back to another field"),
]


def build() -> None:
    DERIVED.mkdir(exist_ok=True)
    res = sodir("field_reserves")
    fld = sodir("field")
    sts = sodir("field_activity_status_hst")
    prod = sodir("field_production_yearly")
    inpl = sodir("field_in_place_volumes")
    desc = sodir("field_description")
    oper = sodir("field_operator_hst")
    disc = sodir("discovery")
    fac = sodir("facility_fixed")
    wlb = sodir("wellbore_exploration_all")
    inv = sodir("field_investment_yearly")
    wdev = sodir("wellbore_development_all")

    # ---------------------------------------------------------------- estimates
    res = res.rename(columns={
        "fldNpdidField": "id", "fldVersion": "year", "fldRecoverableOE": "oe", "fldRecoverableOil": "oil",
        "fldRecoverableGas": "gas", "fldRecoverableNGL": "ngl", "fldRecoverableCondensate": "cond",
        "fldRemainingOE": "remaining_oe"})
    # A recoverable volume of exactly 0 is a placeholder row (field merged or not yet reported), not an estimate.
    zero_rows = res[res.oe <= 0][["fldName", "year"]].to_dict("records")
    res = res[res.oe > 0].copy()
    est = res[["id", "year", "oe", "oil", "gas", "ngl", "cond", "remaining_oe"]].sort_values(["id", "year"])
    # canonical name: newest row (names are stable but one 2006 row had trailing white space)
    names = res.sort_values("year").groupby("id").fldName.last()

    # ---------------------------------------------------------------- production
    prod = prod.rename(columns={"prfNpdidInformationCarrier": "id", "prfYear": "year", "prfPrdOeNetMillSm3": "prod_oe",
                                "prfPrdOilNetMillSm3": "prod_oil", "prfPrdGasNetBillSm3": "prod_gas"})
    prod = prod[["id", "year", "prod_oe", "prod_oil", "prod_gas"]].sort_values(["id", "year"])
    prod["cum_prod_oe"] = prod.groupby("id").prod_oe.cumsum()
    first_prod_year = prod[prod.prod_oe > 0].groupby("id").year.min()
    est = est.merge(prod[["id", "year", "prod_oe", "cum_prod_oe"]], on=["id", "year"], how="left")

    # ---------------------------------------------------------------- start year t0
    sts["from"] = pd.to_datetime(sts.fldStatusFromDate, format="%d.%m.%Y")
    producing = sts[sts.fldStatus == "Producing"]
    t0_status = producing.groupby("fldNpdidField")["from"].min().dt.year
    n_prod_periods = producing.groupby("fldNpdidField").size()
    shut = sts[sts.fldStatus == "Shut down"].groupby("fldNpdidField")["from"].max().dt.year

    f = pd.DataFrame({"name": names})
    f["t0"] = t0_status.reindex(f.index)
    f["t0_source"] = np.where(f.t0.notna(), "field_activity_status_hst: first 'Producing' date", "")
    missing = f.t0.isna() & first_prod_year.reindex(f.index).notna()
    f.loc[missing, "t0"] = first_prod_year.reindex(f.index)[missing]
    f.loc[missing, "t0_source"] = "field_production_yearly: first year with production"
    f["first_prod_year"] = first_prod_year.reindex(f.index)
    f["restarted"] = n_prod_periods.reindex(f.index).fillna(0) > 1
    f["shut_down_year"] = shut.reindex(f.index)

    # ---------------------------------------------------------------- field info
    fld = fld.set_index("fldNpdidField")
    f["area"] = fld.fldMainArea.reindex(f.index).str.replace(" sea", " Sea")
    f["hc_type"] = fld.fldHcType.reindex(f.index)
    f["status"] = fld.fldCurrentActivitySatus.reindex(f.index)
    f["operator_now"] = fld.cmpLongName.reindex(f.index)
    f["discovery_wellbore"] = fld.wlbName.reindex(f.index)
    f["url"] = fld.fldFactPageUrl.reindex(f.index)
    f["in_field_table"] = f.index.isin(fld.index)

    # operator when production started
    oper["from"] = pd.to_datetime(oper.fldOperatorFrom, format="%d.%m.%Y")
    oper["to"] = pd.to_datetime(oper.fldOperatorTo, format="%d.%m.%Y").fillna(pd.Timestamp("2100-01-01"))
    op_start = {}
    for fid, t0 in f.t0.dropna().items():
        rows = oper[(oper.fldNpdidField == fid)].sort_values("from")
        if rows.empty:
            continue
        at = rows[(rows["from"] <= pd.Timestamp(int(t0), 12, 31)) & (rows["to"] >= pd.Timestamp(int(t0), 1, 1))]
        op_start[fid] = (at if not at.empty else rows).iloc[-1 if not at.empty else 0].cmpLongName
    f["operator_at_start"] = pd.Series(op_start)

    def op_group(name) -> str:
        n = str(name).lower()
        if any(k in n for k in ("statoil", "equinor", "norsk hydro", "den norske stats")):
            return "Equinor/Statoil/Hydro"
        if name is None or n == "nan":
            return "Unknown"
        return "Other operator"
    f["operator_group"] = f.operator_at_start.map(op_group)

    # discoveries: discovery year and deposits added to the field after start-up
    disc = disc[disc.fldNpdidField.notna()].copy()
    disc["fid"] = disc.fldNpdidField.astype(int)
    disc["incl"] = pd.to_datetime(disc.dscDateFromInclInField, format="%d.%m.%Y", errors="coerce").dt.year
    f["discovery_year"] = disc.groupby("fid").dscDiscoveryYear.min().reindex(f.index)
    f["n_discoveries"] = disc.groupby("fid").size().reindex(f.index).fillna(0).astype(int)
    added = {}
    for fid, grp in disc.groupby("fid"):
        t0 = f.t0.get(fid)
        if pd.notna(t0):
            added[fid] = int((grp.incl > t0).sum())
    f["n_discoveries_added_after_start"] = pd.Series(added).reindex(f.index).fillna(0).astype(int)

    # discovery wellbore: water depth and age/formation of the hydrocarbon-bearing level
    w = wlb.set_index("wlbNpdidWellbore")
    wid = fld.wlbNpdidWellbore.reindex(f.index)
    f["water_depth_well_m"] = wid.map(w.wlbWaterDepth)
    f["hc_age_well"] = wid.map(w.wlbAgeWithHc1)
    f["hc_formation_well"] = wid.map(w.wlbFormationWithHc1)

    # ---------------------------------------------------------------- text features (Sodir field descriptions)
    desc["h"] = desc.fldDescriptionHeading.str.strip()
    txt = desc.pivot_table(index="fldNpdidField", columns="h", values="fldDescriptionText", aggfunc="first")
    dev = txt["Development"].reindex(f.index).fillna("")
    rsv = txt["Reservoir"].reindex(f.index).fillna("")
    rec = txt["Recovery strategy"].reindex(f.index).fillna("")
    f["water_depth_text_m"] = dev.map(lambda t: first_number(t, r"water depth (?:is|varies from|ranges from|in the area is)\s*(?:about |approximately )?([\d\s\-–to]+?)(?: to more than \d+)? met"))
    f["water_depth_m"] = f.water_depth_text_m.fillna(f.water_depth_well_m)
    f["reservoir_depth_m"] = rsv.map(lambda t: first_number(t, r"depths? (?:of|is|at)\s*(?:about |approximately |between )?([\d\s\-–and]+?) met"))
    f["pdo_year"] = dev.map(lambda t: first_number(t, r"\(PDO\) was approved in (\d{4})"))
    f["lithology"] = np.where(rsv.str.contains("chalk", case=False), "Chalk",
                              np.where(rsv.str.contains("sandstone", case=False), "Sandstone",
                                       np.where(rsv.eq(""), "Unknown", "Other")))
    f["reservoir_age"] = rsv.map(reservoir_age)
    f["text_complex"] = rsv.str.contains(r"complex|segment|heterogen|compartment|poor communication|connectivity .* poor|faulted", case=False, regex=True)
    f["text_hpht"] = (rsv + dev).str.contains(r"HPHT|high pressure", case=False, regex=True)
    inj = rec.str.contains(r"water injection|gas injection|WAG|water alternating|reinject", case=False, regex=True)
    dep = rec.str.contains(r"pressure depletion|natural (?:aquifer|pressure)|aquifer drive", case=False, regex=True)
    f["recovery_strategy"] = np.where(inj, "Injection (water/gas)", np.where(dep, "Depletion / natural drive", "Unknown"))

    # facilities: a field with no surface facility of its own is a subsea development tied to a host
    fac = fac[(fac.fclBelongsToKind == "FIELD") & fac.fclBelongsToS.notna()].copy()
    fac["fid"] = fac.fclBelongsToS.astype(int)
    has_surface = fac[fac.fclSurface == "Y"].groupby("fid").size()
    has_any = fac.groupby("fid").size()
    f["n_facilities"] = has_any.reindex(f.index).fillna(0).astype(int)
    f["has_surface_facility"] = has_surface.reindex(f.index).fillna(0) > 0
    text_tie = dev.str.contains(r"tied[- ]?(?:back|in)? to|tie-?back to|tied-back to", case=False, regex=True) & dev.str.contains("subsea", case=False)
    f["text_subsea_tieback"] = text_tie
    # Development concept. Rule: a field with no surface facility of its own in facility_fixed is a
    # satellite (subsea templates tied back to a host, or wells drilled from another field's platform).
    concept = np.where(f.has_surface_facility, "Own facility", "Satellite / tie-back")
    f["concept"] = concept
    for field_name, value, why in CONCEPT_OVERRIDES:
        f.loc[f.name == field_name, "concept"] = value
    f["tieback"] = f.concept.eq("Satellite / tie-back")

    # ---------------------------------------------------------------- wells (known at the time, not hindsight)
    # Exploration and appraisal wells assigned to the field (wlbField) and finished before the start-up year.
    ex = wlb[wlb.wlbField.notna() & wlb.wlbPurpose.isin(["WILDCAT", "APPRAISAL"])].copy()
    ex["cy"] = pd.to_datetime(ex.wlbCompletionDate, format="%d.%m.%Y", errors="coerce").dt.year
    dv = wdev[wdev.wlbField.notna() & wdev.wlbPurpose.isin(["PRODUCTION", "INJECTION"])
              & ~wdev.wlbStatus.isin(["WILL NEVER BE DRILLED", "JUNKED"])].copy()
    dv["cy"] = pd.to_datetime(dv.wlbCompletionDate, format="%d.%m.%Y", errors="coerce").dt.year
    wells = {}
    for fid, row in f.iterrows():
        t0 = row.t0
        if pd.isna(t0):
            continue
        e = ex[ex.wlbField == row["name"]]
        d = dv[dv.wlbField == row["name"]]
        wells[fid] = {
            "n_expl_wells_pre": int((e.cy < t0).sum()),                       # wildcat + appraisal before the start-up year
            "n_appraisal_wells_pre": int(((e.cy < t0) & (e.wlbPurpose == "APPRAISAL")).sum()),
            "n_dev_wells_by_start": int(d[d.cy <= t0].wlbWell.nunique()),     # producers and injectors ready in the start-up year
            "n_dev_wellbores_y1_5": int(((d.cy > t0) & (d.cy <= t0 + 5)).sum()),
            "n_dev_wellbores_after_y1": int((d.cy > t0 + 1).sum()),
            "n_dev_wellbores_total": int(len(d)),
        }
    f = f.join(pd.DataFrame.from_dict(wells, orient="index"))
    good = rsv.str.contains(r"(?:very good|excellent|good) (?:reservoir )?(?:quality|properties)|quality is (?:very )?good|have good quality|has good quality|(?:good|excellent) quality", case=False, regex=True)
    poor = rsv.str.contains(r"moderate|poor|varying|variable|variabl|heterogen|low permeab|tight", case=False, regex=True)
    f["text_quality"] = np.where(poor, "Moderate / variable", np.where(good, "Good", "Not stated"))

    # ---------------------------------------------------------------- in-place volumes (snapshot 31.12.2025)
    inpl = inpl.set_index("fldNpdidField")
    inplace = (inpl.fldInplaceOil + inpl.fldInplaceAssLiquid + inpl.fldInplaceAssGas + inpl.fldInplaceFreeGas)
    f["inplace_oe"] = inplace.reindex(f.index).where(lambda s: s > 0)
    f["inplace_oil"] = inpl.fldInplaceOil.reindex(f.index)

    # investments up to and including start year (nominal NOK, not inflation-adjusted)
    inv = inv.rename(columns={"prfNpdidInformationCarrier": "id", "prfYear": "year", "prfInvestmentsMillNOK": "nok"})
    f["invest_to_start_mnok"] = pd.Series({fid: inv[(inv.id == fid) & (inv.year <= t0)].nok.sum() for fid, t0 in f.t0.dropna().items()})

    # ---------------------------------------------------------------- appreciation factors
    est["name"] = est.id.map(f.name)
    est["t0"] = est.id.map(f.t0)
    est["k"] = est.year - est.t0  # years since production start
    rows = []
    for fid, g in est.groupby("id"):
        g = g.sort_values("year")
        t0 = f.t0.get(fid)
        out = {"id": fid, "first_year": int(g.year.min()), "last_year": int(g.year.max()), "n_estimates": len(g),
               "first_oe": g.oe.iloc[0], "last_oe": g.oe.iloc[-1]}
        after = g[g.year >= t0] if pd.notna(t0) else g.iloc[0:0]
        if len(after):
            base = after.iloc[0]
            out.update(base_year=int(base.year), base_oe=base.oe, base_oil=base.oil, base_gas=base.gas,
                       base_lag=int(base.year - t0), n_after_start=len(after))
            for k in (1, 2, 3, 5, 10):
                hit = after[after.year == t0 + k]
                out[f"af{k}"] = float(hit.oe.iloc[0] / base.oe) if len(hit) else np.nan
            out["af_last"] = float(after.oe.iloc[-1] / base.oe)
            out["years_followed"] = int(after.year.iloc[-1] - t0)
            out["af_max"] = float(after.oe.max() / base.oe)
            out["af_min"] = float(after.oe.min() / base.oe)
        # estimate at approval (first row, before start) -> PDO-based factor
        before = g[g.year < t0] if pd.notna(t0) else g.iloc[0:0]
        if len(before) and len(after):
            out["pdo_base_year"] = int(before.year.iloc[0])
            out["pdo_base_oe"] = before.oe.iloc[0]
            out["af_pdo_to_start"] = float(after.oe.iloc[0] / before.oe.iloc[0])
            out["af_pdo_to_last"] = float(after.oe.iloc[-1] / before.oe.iloc[0])
        # Base B: the last estimate BEFORE the start-up year (account as of 31.12 of year t0-1).
        # This is the number the development was started on; the end-of-start-year estimate already
        # contains the first wells and months of production.
        pre = g[g.year == t0 - 1] if pd.notna(t0) else g.iloc[0:0]
        if len(pre):
            out["pre_oe"] = pre.oe.iloc[0]
            out["pre_gas"] = pre.gas.iloc[0]
            for k in (0, 1, 2, 3, 5, 10):
                hit = g[g.year == t0 + k]
                out[f"afp{k}"] = float(hit.oe.iloc[0] / pre.oe.iloc[0]) if len(hit) else np.nan
            out["afp_last"] = float(g.oe.iloc[-1] / pre.oe.iloc[0])
        b04 = g[g.year == BASE_YEAR_ALL]
        if len(b04):
            out["oe_2004"] = b04.oe.iloc[0]
            out["af_2004_to_last"] = float(g.oe.iloc[-1] / b04.oe.iloc[0])
        rows.append(out)
    f = f.join(pd.DataFrame(rows).set_index("id"))

    # cohort used for the start-up analysis
    f["cohort"] = (f.t0 >= BASE_YEAR_ALL) & (f.base_lag <= 1) & (f.n_after_start >= COHORT_MIN_ESTIMATES)
    f["cohort_pre"] = (f.t0 > BASE_YEAR_ALL) & f.pre_oe.notna() & f.afp3.notna()   # pre-start estimate and 3 years of follow-up
    f["expl_wells_per_100mmboe"] = f.n_expl_wells_pre / (f.pre_oe.fillna(f.base_oe) * 6.2898 / 100)
    f["pre2004"] = (f.t0 < BASE_YEAR_ALL) & f.oe_2004.notna()
    f["base_gas_share"] = f.base_gas / f.base_oe
    f["rf_first"] = f.base_oe / f.inplace_oe          # first estimate / in-place volume (2025 snapshot)
    f["rf_last"] = f.last_oe / f.inplace_oe
    f["lead_time_discovery_to_start"] = f.t0 - f.discovery_year

    base = est.id.map(f.base_oe)
    est["af"] = np.where(est.year >= est.t0, est.oe / base, np.nan)
    est["af_2004"] = est.oe / est.id.map(f.oe_2004)

    # ---------------------------------------------------------------- checks
    last = est.sort_values("year").groupby("id").last()
    chk = last[["name", "year", "oe", "remaining_oe"]].copy()
    cum = prod.groupby("id").apply(lambda g: g[g.year <= 2025].prod_oe.sum(), include_groups=False)
    chk["cum_prod_to_2025"] = cum.reindex(chk.index)
    chk["cum_prod_to_est_year"] = [prod[(prod.id == i) & (prod.year <= y)].prod_oe.sum() for i, y in zip(chk.index, chk.year)]
    chk["implied_sold"] = chk.oe - chk.remaining_oe
    chk["ratio"] = chk.cum_prod_to_est_year / chk.oe
    over = chk[(chk.cum_prod_to_est_year > chk.oe * 1.005) & (chk.cum_prod_to_est_year - chk.oe > 0.05)]
    totals = est.groupby("year").agg(recoverable_oe=("oe", "sum"), remaining_oe=("remaining_oe", "sum"), n_fields=("id", "nunique"))
    totals["sold_oe"] = totals.recoverable_oe - totals.remaining_oe
    cum_all = prod.groupby("year").prod_oe.sum().cumsum()
    totals["cum_production_table_oe"] = cum_all.reindex(totals.index)
    grane = est[est.name == "GRANE"].set_index("year").oil
    checks = {
        "zero_rows_dropped": zero_rows,
        "n_fields_with_estimates": int(f.shape[0]),
        "n_estimate_rows": int(len(est)),
        "fields_not_in_field_table": f[~f.in_field_table].name.tolist(),
        "grane_oil": {"2004": float(grane.get(2004)), "2025": float(grane.get(2025)), "expected": {"2004": 120.31, "2025": 150.78}},
        "production_exceeds_recoverable": over.reset_index()[["name", "year", "oe", "cum_prod_to_est_year", "ratio"]].round(3).to_dict("records"),
        "implied_sold_vs_production_table_median_abs_diff": float((chk.implied_sold - chk.cum_prod_to_est_year).abs().median()),
        "totals_by_year": totals.round(2).reset_index().to_dict("records"),
        "t0_differs_from_first_production": f[(f.t0 != f.first_prod_year) & f.first_prod_year.notna()][["name", "t0", "first_prod_year"]].to_dict("records"),
        "concept_overrides": [list(o) for o in CONCEPT_OVERRIDES],
        "cohort_fields_without_any_facility_row": f[(f.n_facilities == 0) & f.cohort].name.tolist(),
        "sources": {t: newest("sodir", t).name for t in ("field_reserves", "field", "field_activity_status_hst", "field_production_yearly",
                                                          "field_in_place_volumes", "field_description", "field_operator_hst", "discovery",
                                                          "facility_fixed", "wellbore_exploration_all", "field_investment_yearly")},
    }
    (DERIVED / "norway_checks.json").write_text(json.dumps(checks, indent=1, ensure_ascii=False, default=float))
    est.to_csv(DERIVED / "norway_estimates.csv", index=False)
    f.index.name = "id"
    f.to_csv(DERIVED / "norway_fields.csv")
    print(f"fields: {len(f)}  estimate rows: {len(est)}  cohort (start >= {BASE_YEAR_ALL}, >= {COHORT_MIN_ESTIMATES} estimates): {int(f.cohort.sum())}  pre-2004 with 2004 row: {int(f.pre2004.sum())}")
    print("production exceeds recoverable:", [r["name"] for r in checks["production_exceeds_recoverable"]])


if __name__ == "__main__":
    build()
