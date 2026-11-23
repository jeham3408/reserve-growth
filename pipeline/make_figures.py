#!/usr/bin/env python3
"""Static 16:9 figures for the slides, drawn from the same JSON files the web page uses (web/data/*.json)."""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import FIGURES, WEB_DATA

UP, DOWN, FLAT, INK, INK2, BAND, GRID = "#2a78d6", "#e34948", "#a3a29b", "#0b0b0b", "#52514e", "#dcdbd4", "#ebeae5"
plt.rcParams.update({"font.size": 15, "font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#7b7a74", "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "savefig.dpi": 160})
NO = json.loads((WEB_DATA / "norway.json").read_text())
UK = json.loads((WEB_DATA / "uk.json").read_text())
HD = json.loads((WEB_DATA / "hard.json").read_text())
UE = json.loads((WEB_DATA / "uk_editions.json").read_text())
BBL = NO["meta"]["sm3_to_bbl"]


def col(af):
    return UP if af >= 1.25 else DOWN if af <= 0.8 else FLAT


def pc(v):
    return "±0" if abs(v - 1) < 0.005 else (f"−{round((1 - v) * 100)} %" if v < 1 else f"+{round((v - 1) * 100)} %")


def ratio_axis(ax, ticks, axis="y"):
    (ax.set_yscale if axis == "y" else ax.set_xscale)("log")
    (ax.set_yticks if axis == "y" else ax.set_xticks)(ticks)
    (ax.set_yticklabels if axis == "y" else ax.set_xticklabels)([pc(t) for t in ticks])
    ax.minorticks_off()


def save(fig, name):
    FIGURES.mkdir(exist_ok=True)
    fig.savefig(FIGURES / name, bbox_inches="tight")
    plt.close(fig)
    print("wrote figures/" + name)


def fig_new_fields():
    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    fs = [f for f in NO["fields"] if f.get("pre") and f["t0"] > 2004]
    series = []
    for f in fs:
        pts = [(-1, 1.0)] + [(y - f["t0"], v / f["pre"]) for y, v in zip(f["y"], f["oe"]) if y >= f["t0"]]
        if len(pts) > 1:
            series.append((f, pts))
    ks = range(-1, 21)
    cur = []
    for k in ks:
        v = [p[1] for _, pts in series for p in pts if p[0] == k]
        if len(v) >= 8:
            cur.append((k, np.quantile(v, .1), np.median(v), np.quantile(v, .9)))
    ax.fill_between([c[0] for c in cur], [c[1] for c in cur], [c[3] for c in cur], color=BAND, alpha=.8, lw=0, label="middle 80 % of fields")
    for f, pts in series:
        ax.plot(*zip(*[(x, max(y, .1)) for x, y in pts]), color=col(pts[-1][1]), lw=1.3, alpha=.6)
    ax.plot([c[0] for c in cur], [c[2] for c in cur], color=INK, lw=3, label="median field")
    ends = sorted(series, key=lambda s: s[1][-1][1])
    for f, pts in ends[:3] + ends[-4:]:
        ax.annotate(f["name"].title(), (pts[-1][0], max(pts[-1][1], .11)), xytext=(6, 0), textcoords="offset points", va="center", fontsize=11, color=INK)
    ratio_axis(ax, [0.125, 0.25, 0.5, 1, 2, 4])
    ax.set_ylim(0.1, 4.6); ax.set_xlim(-1, 23)
    ax.axhline(1, color="#7b7a74", lw=1); ax.axvline(0, color="#7b7a74", lw=1, ls=":")
    ax.grid(axis="y", color=GRID); ax.set_axisbelow(True)
    ax.set_xlabel("Years after production start (each line starts at the estimate one year before)")
    o = HD["overall"]["y3"]
    ax.set_title(f"{len(series)} Norwegian fields started since 2005: estimate compared with the last estimate before start-up\n"
                 f"After 3 years: median {pc(o['median'])}; {o['n_down']} of {o['n']} fields down 20 % or more, {o['n_up']} up 25 % or more",
                 loc="left", fontsize=15, color=INK)
    ax.plot([], [], color=UP, lw=2, label="now up 25 % or more"); ax.plot([], [], color=DOWN, lw=2, label="now down 20 % or more")
    ax.legend(frameon=False, loc="lower right", fontsize=12, ncol=1)
    fig.text(0.01, -0.01, "Source: Sodir FactPages, field_reserves (fldRecoverableOE), resource accounts 2004–2025. NLOD.", fontsize=10, color=INK2)
    save(fig, "fig1_new_fields_from_pre_start_estimate.png")


def fig_midlife():
    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    old = [f for f in NO["fields"] if f["pre2004"]]
    years = list(range(2004, 2026)); mat = {y: [] for y in years}
    for f in old:
        b = f["oe"][f["y"].index(2004)]
        pts = [(y, v / b) for y, v in zip(f["y"], f["oe"])]
        for y, v in pts:
            mat[y].append(v)
        ax.plot(*zip(*pts), color=col(pts[-1][1]), lw=1.2, alpha=.55)
    ax.fill_between(years, [np.quantile(mat[y], .1) for y in years], [np.quantile(mat[y], .9) for y in years], color=BAND, alpha=.7, lw=0, zorder=0)
    ax.plot(years, [np.median(mat[y]) for y in years], color=INK, lw=3)
    ratio_axis(ax, [0.5, 1, 2, 4]); ax.set_ylim(0.45, 6); ax.set_xlim(2004, 2025.5)
    ax.axhline(1, color="#7b7a74", lw=1); ax.grid(axis="y", color=GRID); ax.set_axisbelow(True)
    m = NO["midlife"]
    ax.set_title(f"{m['n']} fields already producing before 2004: estimate compared with the 2004 estimate\n"
                 f"Sum {m['sum_2004']:,.0f} → {m['sum_last']:,.0f} million Sm³ o.e. ({pc(m['weighted'])}); only {m['share_below_1_still_producing']:.0%} of those still producing are below 2004",
                 loc="left", fontsize=15, color=INK)
    ax.set_xlabel("Resource account year (these fields enter mid-life: revisions before 2004 are not included)")
    save(fig, "fig2_older_fields_from_2004.png")


def fig_size():
    S = HD["size"]; a = S["at"]["3"]
    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    pts = [p for p in S["points"] if p["afp3"] is not None]
    ax.axhspan(0.8, 1.25, color=BAND, alpha=.45, zorder=0)
    ax.scatter([p["size"] * BBL for p in pts], [max(p["afp3"], .1) for p in pts], s=90, c=[col(p["afp3"]) for p in pts], edgecolor="#fcfcfb", lw=1, zorder=3)
    for p in sorted(pts, key=lambda p: p["afp3"])[:4] + sorted(pts, key=lambda p: -p["afp3"])[:2] + sorted(pts, key=lambda p: -p["size"])[:2]:
        right = p["size"] * BBL > 700
        ax.annotate(p["name"].title(), (p["size"] * BBL, max(p["afp3"], .1)), xytext=(-8 if right else 8, 8 if right else 0), textcoords="offset points",
                    ha="right" if right else "left", va="center", fontsize=11, color=INK)
    ax.set_xscale("log"); ax.set_xticks([1, 10, 100, 1000]); ax.set_xticklabels(["1", "10", "100", "1 000"])
    ratio_axis(ax, [0.125, 0.25, 0.5, 1, 2, 4]); ax.set_ylim(0.1, 4.6); ax.set_xlim(0.7, 4000)
    ax.axhline(1, color="#7b7a74", lw=1); ax.axvline(100, color="#7b7a74", lw=1.2, ls="--")
    ax.grid(color=GRID); ax.set_axisbelow(True)
    ax.text(0.8, 0.108, f"under 100 million barrels ({a['small']['n']} fields)\ntypically ±{a['small']['typical_change']:.0%}, {a['small']['share_down']:.0%} down 20 % or more", ha="left", va="bottom", fontsize=13, color=INK)
    ax.text(3600, 0.108, f"larger fields ({a['large']['n']})\ntypically ±{a['large']['typical_change']:.0%}, {a['large']['share_down']:.0%} down 20 % or more", ha="right", va="bottom", fontsize=13, color=INK)
    ax.set_xlabel("Estimate before start-up, million barrels of oil equivalents (log scale)")
    ax.set_ylabel("Change three years after start-up")
    w = HD["watkins"]
    ax.set_title(f"Small fields are revised about twice as much as larger fields (×{S['ratio_typical_3y']['ratio']:.1f}, p = {a['p_magnitude']:.2f})\n"
                 f"Same pattern in {w['n']} older UK and Norwegian fields (Watkins 2000, p = {w['magnitude_p']:.3f})", loc="left", fontsize=15, color=INK)
    save(fig, "fig3_small_fields_revised_more.png")


def fig_timing():
    T = HD["timing"]
    fig, ax = plt.subplots(figsize=(12.8, 6.6))
    for key, colr, lab in (("down", DOWN, f"ended 20 % or more down ({T['n_down']} fields)"), ("up", UP, f"ended 25 % or more up ({T['n_up']} fields)")):
        pts = [{"k": -1, "median": 0, "p25": 0, "p75": 0}] + T["path"][key]
        ks = [p["k"] for p in pts]
        ax.fill_between(ks, [np.clip(p["p25"], -.3, 1.3) for p in pts], [np.clip(p["p75"], -.3, 1.3) for p in pts], color=colr, alpha=.14, lw=0)
        ax.plot(ks, [p["median"] for p in pts], color=colr, lw=3.2, marker="o", ms=7, label=lab)
    ax.set_ylim(-0.3, 1.3); ax.set_yticks([0, .5, 1]); ax.set_yticklabels(["0 %", "50 %", "100 %"]); ax.set_xlim(-1, T["min_years_followed"])
    ax.set_xticks(range(-1, T["min_years_followed"] + 1)); ax.set_xticklabels(["before", "start"] + [str(k) for k in range(1, T["min_years_followed"] + 1)])
    ax.axhline(0, color="#7b7a74", lw=1); ax.grid(axis="y", color=GRID); ax.set_axisbelow(True)
    ax.set_xlabel("Years after production start"); ax.set_ylabel("Share of the eventual change\nalready in the estimate")
    ax.legend(frameon=False, loc="lower right", fontsize=13)
    ax.set_title(f"Downgrades come fast, upgrades come slowly\nAfter one year: {T['share_of_final_change_after_year1']['down']:.0%} of the eventual loss is in the books, "
                 f"{max(0, T['share_of_final_change_after_year1']['up']):.0%} of the eventual gain", loc="left", fontsize=15, color=INK)
    save(fig, "fig4_downgrades_fast_upgrades_slow.png")


def fig_drilling():
    D = HD["drilling"]["old_fields"]
    fig, ax = plt.subplots(figsize=(12.8, 6.8))
    pts = D["points"]
    t = lambda v: np.log1p(v)
    for p in pts:
        ax.scatter(t(p["rel"]), p["af"], s=95, c=col(p["af"]) if p["producing"] else "#fcfcfb", edgecolor="#fcfcfb" if p["producing"] else FLAT, lw=1 if p["producing"] else 1.8, zorder=3)
    for p in sorted(pts, key=lambda p: -p["af"])[:4]:
        ax.annotate(p["name"].title(), (t(p["rel"]), p["af"]), xytext=(-8, 0), textcoords="offset points", ha="right", va="center", fontsize=11, color=INK)
    ticks = [0, .5, 1, 2, 4, 8]
    ax.set_xticks([t(v) for v in ticks]); ax.set_xticklabels(["none", "0.5", "1", "2", "4", "8"])
    ratio_axis(ax, [1, 1.5, 2, 3, 4]); ax.set_ylim(0.7, max(4.4, max(p["af"] for p in pts) * 1.1))
    ax.axhline(1, color="#7b7a74", lw=1); ax.grid(color=GRID); ax.set_axisbelow(True)
    ax.set_xlabel("New wells 2005–2025 per well drilled before 2005 (open circles: no longer producing)"); ax.set_ylabel("Change in the estimate 2004–2025")
    tc = D["terciles_producing"]
    ax.set_title(f"Upgrades follow continued drilling: older fields that kept drilling grew the most (rank correlation {D['rho_producing']['rho']:+.2f}, {D['n_producing']} producing fields)\n"
                 f"Least drilling {pc(tc[0]['median_growth'])} · middle {pc(tc[1]['median_growth'])} · most drilling {pc(tc[2]['median_growth'])}", loc="left", fontsize=15, color=INK)
    save(fig, "fig5_growth_follows_drilling.png")


def fig_uk_outcome():
    O = UE["outcome"]; pts = O["points"]
    fig, ax = plt.subplots(figsize=(12.8, 6.8))
    ax.axhspan(0.8, 1.25, color=BAND, alpha=.45, zorder=0)
    ax.scatter([max(.7, p["size_mmbbl"]) for p in pts], [p["ratio"] for p in pts], s=95, c=[col(p["ratio"]) for p in pts], edgecolor="#fcfcfb", lw=1, zorder=3)
    for p in sorted(pts, key=lambda p: -p["ratio"])[:3] + sorted(pts, key=lambda p: p["ratio"])[:2] + sorted(pts, key=lambda p: -p["size_mmbbl"])[:2]:
        right = p["size_mmbbl"] > 500
        ax.annotate(p["name"], (max(.7, p["size_mmbbl"]), p["ratio"]), xytext=(-8 if right else 8, 0), textcoords="offset points", ha="right" if right else "left", va="center", fontsize=11, color=INK)
    ax.set_xscale("log"); ax.set_xticks([1, 10, 100, 1000]); ax.set_xticklabels(["1", "10", "100", "1 000"]); ax.set_xlim(0.7, 3000)
    ratio_axis(ax, [0.5, 1, 2, 4]); ax.set_ylim(0.35, 5)
    ax.axhline(1, color="#7b7a74", lw=1); ax.axvline(100, color="#7b7a74", lw=1.2, ls="--"); ax.grid(color=GRID); ax.set_axisbelow(True)
    ax.set_xlabel("Estimate at start-up, million barrels of oil (log scale)"); ax.set_ylabel("Total production ÷ estimate at start-up")
    a = O["all"]
    ax.set_title(f"UK: the estimate at start-up against what the field finally produced ({O['n']} fields that have ceased)\n"
                 f"Median {pc(a['median'])}; {a['share_up']:.0%} ended 25 % or more above the estimate, {a['share_down']:.0%} 20 % or more below; typical miss {a['typical_change']:.0%}",
                 loc="left", fontsize=15, color=INK)
    fig.text(0.01, -0.02, "Sources: Watkins (2000) start-up estimates; DTI Brown Book web editions 1998–2001 (Internet Archive); NSTA production 1975–2026.", fontsize=10, color=INK2)
    save(fig, "fig6_uk_startup_estimate_vs_outcome.png")


def fig_uk_annual():
    R = UE["revisions"]
    fig, ax = plt.subplots(figsize=(12.8, 6.4))
    n = 0
    for f in UE["fields"]:
        if len(f["y"]) >= 2:
            n += 1
            v = [m / f["mt"][0] for m in f["mt"]]
            ax.plot(f["y"], np.clip(v, .35, 3), color=col(v[-1]), lw=1.4, alpha=.6)
    ratio_axis(ax, [0.5, 1, 2]); ax.set_ylim(0.35, 3); ax.set_xticks([1997, 1998, 1999, 2000]); ax.set_xlim(1996.9, 2000.1)
    ax.axhline(1, color="#7b7a74", lw=1); ax.grid(axis="y", color=GRID); ax.set_axisbelow(True)
    g = R["groups"]
    ax.set_title(f"UK estimates per field are open for four year-ends: {n} offshore oil fields in the Brown Book web editions 1998–2001\n"
                 f"Young fields moved ±{g['young']['typical_change']:.0%}, mature fields ±{g['mature']['typical_change']:.0%} over 1997–2000 (p = {R['p_young_vs_mature_magnitude']:.2f})",
                 loc="left", fontsize=15, color=INK)
    ax.set_xlabel("Operator's estimate of recoverable oil originally present, relative to the first listed estimate (end of year)")
    save(fig, "fig7_uk_estimates_1997_2000.png")


def fig_chain():
    ch = UK["norway_chain"]["all"]
    fig, ax = plt.subplots(figsize=(12.8, 6.2))
    labels = ["at start-up", "1996", "2004", "2025"]; vals = [ch["initial"], ch["y1996"], ch["y2004"], ch["latest"]]; af = [1, ch["af_1996"], ch["af_2004"], ch["af_latest"]]
    bars = ax.bar(labels, [v / 1000 for v in vals], color=UP, width=.58)
    for b, v, a in zip(bars, vals, af):
        ax.text(b.get_x() + b.get_width() / 2, v / 1000 + .25, f"{v / 1000:.1f} bn bbl" + ("" if a == 1 else f"\n×{a:.2f}"), ha="center", va="bottom", fontsize=14, color=INK)
    ax.set_ylim(0, ch["latest"] / 1000 * 1.22); ax.set_yticks([]); ax.spines["left"].set_visible(False)
    ax.set_title(f"The same {ch['n']} Norwegian oil fields, from start-up to today: the estimate has doubled\n"
                 "Start-up and 1996 from Watkins (2000); 2004 and 2025 from Sodir (oil only)", loc="left", fontsize=15, color=INK)
    save(fig, "fig8_norway_long_run.png")


if __name__ == "__main__":
    for old in FIGURES.glob("fig*.png"):
        old.unlink()
    fig_new_fields(); fig_midlife(); fig_size(); fig_timing(); fig_drilling(); fig_uk_outcome(); fig_uk_annual(); fig_chain()
