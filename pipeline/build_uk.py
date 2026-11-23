#!/usr/bin/env python3
"""UK cross-check: three snapshots plus a production-based indicator.

There is no open year-by-year reserve estimate per UK field. What exists:
  1. Watkins (2000), Table D-1: initial reserves at start-up and at the last observation year (1996), 96 oil fields.
  2. Brown Book field pages archived by the Wayback Machine: operator's estimate of recoverable reserves
     originally present, edition with licence interests "at end of 2000 / February 2002" (called c. 2001 here).
  3. NSTA PPRS: monthly production per field, 1975-2026.
Indicator: cumulative oil production to 2026 divided by the old estimate. A ratio above 1 proves that the old
estimate was too low. For fields that have stopped producing, the ratio is the realised outcome.

Outputs: web/data/uk.json, derived/uk_name_table.csv, derived/uk_unmatched.csv, derived/uk_fields.csv
"""
from __future__ import annotations

import datetime as dt
import difflib
import re

import numpy as np
import pandas as pd

from common import DERIVED, SM3_TO_BBL, WEB_DATA, boot_ci, sodir, write_json
from uk_sources import brown_book_pages, nsta_fields, nsta_production, watkins_tables

# Manual name links, each checked by hand against the three sources. Value = NSTA PPRS field name(s).
ALIASES = {
    "Arboath": ["ARBROATH"],                       # spelling in Watkins' table
    "Beryl A&B": ["BERYL"],
    "Guillemot West & Guillemot Northwest": ["GUILLEMOT WEST", "GUILLEMOT NORTH WEST"],
}
# Watkins' Norwegian names -> Sodir field names
NORWAY_ALIASES = {
    "Froey": "FRØY", "Statfjord N": "STATFJORD NORD", "Statfjord Oe": "STATFJORD ØST", "Statfjord Unit": "STATFJORD",
    "Tommeliten G": "TOMMELITEN GAMMA", "Troll V (ph2)": "TROLL", "Valhall(A)": "VALHALL", "Ekofisk V": "VEST EKOFISK",
    "Lille-Frigg": "LILLE-FRIGG",
}
NORWAY_SCOPE_NOTES = {
    "STATFJORD": "Watkins lists the whole Statfjord Unit; Sodir lists the Norwegian share. Excluded from the chained factors.",
    "TROLL": "Watkins lists Troll West phase 2 oil only; Sodir lists all Troll oil. Excluded from the chained factors.",
}


def key(name: str) -> str:
    n = name.upper().replace("&", " AND ")
    n = re.sub(r"\(.*?\)|\[.*?\]", " ", n)
    n = re.sub(r"[^A-Z0-9 ]", " ", n)
    toks = [t for t in n.split() if t not in ("FIELD", "FIELDS", "AND", "THE", "UNIT", "AREA")]
    return " ".join(sorted(toks))


def dist(values, with_values=False):
    v = pd.Series(values).dropna()
    if len(v) == 0:
        return {"n": 0}
    out = {"n": int(len(v)), "median": float(v.median()), "median_ci90": list(boot_ci(v.values)),
           "p10": float(v.quantile(.1)), "p25": float(v.quantile(.25)), "p75": float(v.quantile(.75)), "p90": float(v.quantile(.9)),
           "share_above_1": float((v > 1).mean()), "share_above_1_25": float((v >= 1.25).mean()), "share_below_0_8": float((v <= 0.8).mean())}
    if with_values:
        out["values"] = [float(x) for x in v.values]
    return out


def main() -> None:
    w_all = watkins_tables()
    w = w_all[w_all.sector == "UK"].copy()
    bb = brown_book_pages()
    yearly, info = nsta_production()
    nf = nsta_fields()
    nsta_key = {}
    for n in info.FIELDNAME:
        nsta_key.setdefault(key(n), []).append(n)
    status = nf.set_index("FIELDNAME")
    status_key = {key(n): n for n in nf.FIELDNAME}

    def match(name):
        if name in ALIASES:
            return ALIASES[name], "manual alias"
        k = key(name)
        if k in nsta_key:
            return nsta_key[k], "exact (normalised)"
        return None, "no PPRS rows"

    cum = yearly.copy()
    cum["PERIODYR"] = cum.PERIODYR.astype(int)

    def production(names, to_year=2100):
        g = cum[cum.FIELDNAME.isin(names) & (cum.PERIODYR <= to_year)]
        return float(g.OILPRODM3.sum()), float(g.OILPRODMAS.sum()), float(g.DGASPROKSM.sum() + g.AGASPROKSM.sum())

    last_period = int(info.last_period.astype(int).max())
    rows, unmatched = [], []
    names = {}
    for _, r in w.iterrows():
        names.setdefault(key(r["name"]) if r["name"] not in ALIASES else "A:" + r["name"], {})["watkins"] = r
    bbo = bb[bb.offshore & (bb.oil_mt.notna() | bb.gas_bcm.notna())]
    for _, r in bbo.iterrows():
        names.setdefault(key(r["name"]) if r["name"] not in ALIASES else "A:" + r["name"], {})["bb"] = r
    for k, src in names.items():
        wr, br = src.get("watkins"), src.get("bb")
        label = (br["name"] if br is not None else wr["name"])
        m, how = match(wr["name"] if wr is not None else br["name"])
        if m is None and br is not None and wr is not None:
            m, how = match(br["name"])
        rec = {"field": label, "watkins_name": wr["name"] if wr is not None else None, "brown_book_name": br["name"] if br is not None else None,
               "brown_book_file": br["file"] if br is not None else None, "nsta_names": "; ".join(m) if m else None, "match": how}
        if wr is not None:
            rec.update(w_start_year=int(wr.start_year), w_initial_mmbbl=wr.initial_mmbbl, w_1996_mmbbl=wr.last_mmbbl,
                       w_cum_1996_mmbbl=wr.cum_prod_last_mmbbl, w_af_1996=wr.af_1996, w_formation=wr.formation)
        if br is not None:
            rec.update(bb_oil_mt=br.oil_mt, bb_gas_bcm=br.gas_bcm, bb_start_year=br.start_year, bb_kind=br.kind, bb_operator=br.operator)
        if m:
            m3, t, gas = production(m)
            m3_96, _, _ = production(m, 1996)
            sub = info[info.FIELDNAME.isin(m)]
            pos = cum[cum.FIELDNAME.isin(m) & (cum.OILPRODMAS > 0)]
            rec["first_oil_year"] = int(pos.PERIODYR.min()) if len(pos) else np.nan
            rec.update(cum_oil_mmbbl=m3 * SM3_TO_BBL / 1e6, cum_oil_mt=t / 1e6, cum_gas_bcm=gas / 1e6,
                       cum_oil_1996_mmbbl=m3_96 * SM3_TO_BBL / 1e6, density=(t / m3 if m3 > 0 else np.nan),
                       first_period=int(sub.first_period.astype(int).min()), last_period=int(sub.last_period.astype(int).max()))
            st = [status.STATUS.get(status_key.get(key(x))) for x in m]
            st = [s for s in st if isinstance(s, str)]
            rec["nsta_status"] = "; ".join(sorted(set(st))) if st else None
            rec["still_reporting"] = rec["last_period"] >= last_period - 100  # reported within the last 12 months
            rec["ceased"] = bool(st) and all(("CEASED" in s or "POST-COP" in s) for s in st)
        else:
            close = difflib.get_close_matches(key(label), list(nsta_key), 3, 0.6)
            unmatched.append({"field": label, "source": "+".join(s for s in ("watkins", "bb") if src.get(s) is not None),
                              "closest_pprs_names": "; ".join(nsta_key[c][0] for c in close)})
        rows.append(rec)
    u = pd.DataFrame(rows)
    # indicators
    u["bbl_per_tonne"] = SM3_TO_BBL / u.density
    u["ratio_w1996"] = u.cum_oil_mmbbl / u.w_1996_mmbbl                  # production to 2026 / estimate in 1996
    u["ratio_bb2001"] = u.cum_oil_mt / u.bb_oil_mt                       # production to 2026 / estimate c. 2001 (mass, no conversion)
    u["bb_mmbbl"] = u.bb_oil_mt * u.bbl_per_tonne
    u["af_1996_to_2001"] = u.bb_mmbbl / u.w_1996_mmbbl
    u["lower_bound_af_from_start"] = np.fmax(u.cum_oil_mmbbl, np.fmax(u.w_1996_mmbbl.fillna(0), u.bb_mmbbl.fillna(0))) / u.w_initial_mmbbl
    u = u.sort_values("field").reset_index(drop=True)
    u[["field", "watkins_name", "brown_book_name", "brown_book_file", "nsta_names", "match"]].to_csv(DERIVED / "uk_name_table.csv", index=False)
    pd.DataFrame(unmatched).to_csv(DERIVED / "uk_unmatched.csv", index=False)

    u["check_cum1996_ratio"] = u.cum_oil_1996_mmbbl / u.w_cum_1996_mmbbl
    # Coverage guard: PPRS must start within a year of the field's start-up, otherwise early production is missing
    # (e.g. Kittiwake: on stream 1990, PPRS rows only from much later).
    # Rule 1: the first year with oil in PPRS must be within a year of start-up.
    # Rule 2: where Watkins gives cumulative production to 1996, PPRS must reproduce at least 80 % of it.
    bad_check = u.check_cum1996_ratio < 0.8
    u["covered_bb"] = (u.first_oil_year <= u.bb_start_year + 1) & ~bad_check
    u["covered_w"] = (u.first_oil_year <= u.w_start_year + 1) & ~bad_check
    dropped_cover = u[(u.bb_oil_mt.notna() & u.cum_oil_mt.notna() & (u.covered_bb == False)) |
                      (u.w_1996_mmbbl.notna() & u.cum_oil_mmbbl.notna() & (u.covered_w == False))].field.tolist()
    oil_bb = u[u.bb_oil_mt.notna() & (u.bb_oil_mt >= 0.5) & u.cum_oil_mt.notna() & (u.bb_start_year >= 1975) & u.covered_bb]
    oil_w = u[u.w_1996_mmbbl.notna() & u.cum_oil_mmbbl.notna() & u.covered_w]
    u.to_csv(DERIVED / "uk_fields.csv", index=False)
    both = u[u.af_1996_to_2001.notna()]
    chk = oil_w[oil_w.w_cum_1996_mmbbl > 5].check_cum1996_ratio

    # ------------------------------------------------------------ Norway with the same indicator
    res = sodir("field_reserves").rename(columns={"fldNpdidField": "id", "fldVersion": "year"})
    res = res[res.fldRecoverableOE > 0]
    nf_no = pd.read_csv(DERIVED / "norway_fields.csv").set_index("id")
    py = sodir("field_production_yearly").rename(columns={"prfNpdidInformationCarrier": "id", "prfYear": "year"})
    cum_oil_no = py[py.year <= 2025].groupby("id").prfPrdOilNetMillSm3.sum()
    r04 = res[res.year == 2004].set_index("id").fldRecoverableOil
    last_year = res.groupby("id").year.max()
    rlast = res.sort_values("year").groupby("id").fldRecoverableOil.last()
    no = pd.DataFrame({"name": nf_no.name, "t0": nf_no.t0, "status": nf_no.status, "oil_2004": r04, "oil_last": rlast, "cum_oil_2025": cum_oil_no}).dropna(subset=["oil_2004"])
    no = no[(no.oil_2004 >= 0.6) & (no.t0 < 2004)]       # oil fields on stream before 2004 (>= 0.6 MSm3, about 0.5 Mt)
    no["ratio_2004"] = no.cum_oil_2025 / no.oil_2004     # same indicator as the UK
    no["true_af"] = no.oil_last / no.oil_2004            # what the indicator tries to approximate
    no["shut"] = no.status.ne("Producing")

    # Watkins' Norwegian fields followed into the Sodir table (oil only)
    wn = w_all[w_all.sector == "Norway"].copy()
    wn["sodir_name"] = wn.name.map(lambda n: NORWAY_ALIASES.get(n, n.upper()))
    by_name = res.assign(n=res.fldName.str.strip())
    chain = []
    for _, r in wn.iterrows():
        g = by_name[by_name.n == r.sodir_name].sort_values("year")
        rec = {"watkins_name": r["name"], "sodir_name": r.sodir_name, "start_year": int(r.start_year), "formation": r.formation,
               "initial_mmbbl": r.initial_mmbbl, "y1996_mmbbl": r.last_mmbbl, "note": NORWAY_SCOPE_NOTES.get(r.sodir_name)}
        if len(g):
            g04 = g[g.year == 2004]
            rec["y2004_mmbbl"] = float(g04.fldRecoverableOil.iloc[0] * SM3_TO_BBL) if len(g04) else np.nan
            rec["latest_mmbbl"] = float(g.fldRecoverableOil.iloc[-1] * SM3_TO_BBL)
            rec["latest_year"] = int(g.year.iloc[-1])
        else:
            rec["note"] = "no row in Sodir field_reserves"
        chain.append(rec)
    ch = pd.DataFrame(chain)
    ch["af_1996"] = ch.y1996_mmbbl / ch.initial_mmbbl
    ch["af_2004"] = ch.y2004_mmbbl / ch.initial_mmbbl
    ch["af_latest"] = ch.latest_mmbbl / ch.initial_mmbbl
    ok = ch[ch.latest_mmbbl.notna() & ch.y2004_mmbbl.notna() & ch.note.isna()]
    chalk = ok[ok.formation.str.contains("Chalk")]
    sand = ok[~ok.formation.str.contains("Chalk")]

    def agg(d):
        return {"n": int(len(d)), "initial": float(d.initial_mmbbl.sum()), "y1996": float(d.y1996_mmbbl.sum()), "y2004": float(d.y2004_mmbbl.sum()),
                "latest": float(d.latest_mmbbl.sum()), "af_1996": float(d.y1996_mmbbl.sum() / d.initial_mmbbl.sum()),
                "af_2004": float(d.y2004_mmbbl.sum() / d.initial_mmbbl.sum()), "af_latest": float(d.latest_mmbbl.sum() / d.initial_mmbbl.sum()),
                "median_af_1996": float(d.af_1996.median()), "median_af_latest": float(d.af_latest.median()),
                "median_af_latest_ci90": list(boot_ci(d.af_latest.values))}

    ww = {}
    for sec, g in w_all.groupby("sector"):
        ww[sec] = {"n": int(len(g)), "weighted_af": float(g.last_mmbbl.sum() / g.initial_mmbbl.sum()), "median_af": float(g.af_1996.median()),
                   "mean_initial": float(g.initial_mmbbl.mean()), "mean_last": float(g.last_mmbbl.mean()),
                   "share_unchanged": float((g.af_1996.sub(1).abs() < 0.02).mean()), "share_down": float((g.af_1996 <= 0.8).mean()),
                   "share_up": float((g.af_1996 >= 1.25).mean()), "p10": float(g.af_1996.quantile(.1)), "p90": float(g.af_1996.quantile(.9)),
                   "values": [float(v) for v in g.af_1996]}
    piper = w[w.name == "Piper"].iloc[0]

    out = {
        "meta": {"generated": dt.date.today().isoformat(), "pprs_last_period": last_period, "pprs_fields": int(len(info)),
                 "brown_book_pages": int(len(bb)), "brown_book_offshore_with_oil": int((bb.offshore & bb.oil_mt.notna()).sum()),
                 "brown_book_offshore_with_gas": int((bb.offshore & bb.gas_bcm.notna()).sum()),
                 "brown_book_edition_dates": bb.licence_interest_date.value_counts().to_dict(),
                 "watkins_uk": int(len(w)), "sm3_to_bbl": SM3_TO_BBL},
        "watkins": {**ww, "check_piper": {"initial": float(piper.initial_mmbbl), "last": float(piper.last_mmbbl)},
                    "claim": "Appreciation factor from start-up to 1996: 1.22 (UK, 96 fields) and 1.47 (Norway, 30 fields), weighted by initial reserves."},
        "matching": {"n_names": int(len(u)), "n_matched": int(u.nsta_names.notna().sum()), "n_unmatched": int(u.nsta_names.isna().sum()),
                     "unmatched": unmatched, "manual_aliases": ALIASES, "dropped_incomplete_pprs_coverage": dropped_cover,
                     "check_cum_production_1996": {"n": int(chk.notna().sum()), "median_ratio_pprs_over_watkins": float(chk.median()),
                                                   "p10": float(chk.quantile(.1)), "p90": float(chk.quantile(.9)),
                                                   "note": "PPRS cumulative oil to end 1996 divided by Watkins' (initial minus remaining reserves) for matched fields above 5 mmbbl."}},
        "indicator": {
            "uk_vs_brown_book_2001": {**dist(oil_bb.ratio_bb2001, True), "names": oil_bb.field.tolist(),
                                      "ceased": dist(oil_bb[oil_bb.ceased == True].ratio_bb2001),
                                      "not_ceased": dist(oil_bb[oil_bb.ceased != True].ratio_bb2001),
                                      "sum_estimate_mt": float(oil_bb.bb_oil_mt.sum()), "sum_produced_mt": float(oil_bb.cum_oil_mt.sum())},
            "uk_vs_watkins_1996": {**dist(oil_w.ratio_w1996, True), "names": oil_w.field.tolist(),
                                   "ceased": dist(oil_w[oil_w.ceased == True].ratio_w1996),
                                   "sum_estimate_mmbbl": float(oil_w.w_1996_mmbbl.sum()), "sum_produced_mmbbl": float(oil_w.cum_oil_mmbbl.sum())},
            "uk_1996_to_2001": {**dist(both.af_1996_to_2001), "weighted": float(both.bb_mmbbl.sum() / both.w_1996_mmbbl.sum()),
                                "note": "Brown Book tonnes converted to barrels with each field's own PPRS oil density; a few per cent of noise."},
            "norway_same_indicator": {**dist(no.ratio_2004, True), "names": no.name.tolist(),
                                      "shut": dist(no[no.shut].ratio_2004), "true_af": dist(no.true_af),
                                      "sum_estimate": float(no.oil_2004.sum()), "sum_produced": float(no.cum_oil_2025.sum()),
                                      "agreement_note": "For Norway the real revision is known, so the indicator can be compared with it.",
                                      "share_indicator_above_1": float((no.ratio_2004 > 1).mean()), "share_true_af_above_1": float((no.true_af > 1.0).mean())},
        },
        "norway_chain": {"rows": ch.to_dict("records"), "all": agg(ok), "chalk": agg(chalk), "sandstone": agg(sand),
                         "excluded": ch[~ch.index.isin(ok.index)][["watkins_name", "note"]].to_dict("records"),
                         "note": "Oil only. Watkins in million barrels; Sodir million Sm3 x 6.2898."},
        "fields": u.replace({np.nan: None}).to_dict("records"),
    }
    write_json(WEB_DATA / "uk.json", out)
    ind = out["indicator"]
    print("names", len(u), "matched", out["matching"]["n_matched"], "unmatched", out["matching"]["n_unmatched"])
    print("check cum1996", out["matching"]["check_cum_production_1996"])
    for k in ("uk_vs_brown_book_2001", "uk_vs_watkins_1996", "uk_1996_to_2001", "norway_same_indicator"):
        print(k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in ind[k].items() if a not in ("values", "names", "ceased", "not_ceased", "shut", "true_af", "note", "agreement_note")})
        for sub in ("ceased", "not_ceased", "shut", "true_af"):
            if sub in ind[k]:
                print("    ", sub, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in ind[k][sub].items()})
    print("watkins", {s: {a: round(b, 3) for a, b in v.items() if a != "values"} for s, v in ww.items()})
    for k in ("all", "chalk", "sandstone"):
        print("chain", k, {a: (round(b, 2) if isinstance(b, float) else b) for a, b in out["norway_chain"][k].items()})
    print(ch[["watkins_name", "sodir_name", "initial_mmbbl", "y1996_mmbbl", "y2004_mmbbl", "latest_mmbbl", "af_latest", "note"]].round(1).to_string())


if __name__ == "__main__":
    main()
