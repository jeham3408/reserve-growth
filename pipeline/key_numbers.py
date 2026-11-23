#!/usr/bin/env python3
"""Print every number used in the talk, the README and the reply draft, straight from web/data/*.json."""
import json

from common import WEB_DATA

NO = json.loads((WEB_DATA / "norway.json").read_text())
UK = json.loads((WEB_DATA / "uk.json").read_text())
HD = json.loads((WEB_DATA / "hard.json").read_text())
UE = json.loads((WEB_DATA / "uk_editions.json").read_text())


def pc(v):
    return f"{(v - 1) * 100:+.0f} %"


def main():
    o, S, T, D, W = HD["overall"], HD["size"], HD["timing"], HD["drilling"], HD["watkins"]
    print("NORWAY, from the estimate before start-up")
    for k in ("y1", "y3", "y5", "latest"):
        x = o[k]
        print(f"  {k}: n={x['n']} median {pc(x['median'])} CI [{pc(x['ci90'][0])}, {pc(x['ci90'][1])}] down {x['n_down']} up {x['n_up']} large {x['share_large']:.0%} p10 {pc(x['p10'])} p90 {pc(x['p90'])}" + (f" weighted {pc(x['volume_weighted'])}" if "volume_weighted" in x else ""))
    print(f"  start-up year: {o['start_year_step']['n_changed_20pct']} fields moved > 20 %: {o['start_year_step']['names_down_20pct']}")
    for k in ("1", "3", "5"):
        a = S["at"][k]
        print(f"  size y{k}: small n={a['small']['n']} typical ±{a['small']['typical_change']:.0%} median {pc(a['small']['median'])} down {a['small']['share_down']:.0%} up {a['small']['share_up']:.0%} p10..p90 {pc(a['small']['p10'])}..{pc(a['small']['p90'])} | large n={a['large']['n']} typical ±{a['large']['typical_change']:.0%} median {pc(a['large']['median'])} down {a['large']['share_down']:.0%} up {a['large']['share_up']:.0%} p10..p90 {pc(a['large']['p10'])}..{pc(a['large']['p90'])} | p_mag {a['p_magnitude']:.3f} p_dir {a['p_direction']:.3f}")
    print(f"  size ratio 3y ×{S['ratio_typical_3y']['ratio']:.2f} CI {S['ratio_typical_3y']['ci90']}; rho {S['rho_size_vs_magnitude_3y']['rho']:+.2f} p {S['rho_size_vs_magnitude_3y']['p']:.3f}")
    print(f"  tie-backs among small: {sum(1 for p in S['points'] if p['size'] < S['threshold_msm3'] and p['tieback'])} of {S['n_small']}; among large: {sum(1 for p in S['points'] if p['size'] >= S['threshold_msm3'] and p['tieback'])} of {S['n_large']}")
    for st in S["steps"]:
        print(f"    step {st['label']}: small ±{st['small_typical']:.0%} large ±{st['large_typical']:.0%} p {st['p']:.3f}")
    print(f"  Watkins: n={W['n']} (UK {W['n_uk']}, Norway {W['n_norway']}) coef {W['magnitude_coef_log_size']:+.3f} p {W['magnitude_p']:.4f}; UK alone p {W['by_sector']['UK']['p']:.4f}; Norway alone p {W['by_sector']['Norway']['p']:.3f}; direction p {W['direction_p']:.2f}")
    print(f"  timing: down n={T['n_down']} up n={T['n_up']}; after year 1 down {T['share_of_final_change_after_year1']['down']:.0%} up {T['share_of_final_change_after_year1']['up']:.0%}; after year 3 down {T['share_of_final_change_after_year3']['down']:.0%} up {T['share_of_final_change_after_year3']['up']:.0%}; half by y1 {T['half_reached_by_year1']}; half by y3 {T['half_reached_by_year3']}; p {T['p_year1']:.5f}; largest step year {T['year_of_largest_step_median']}")
    n = D["new_fields"]
    print(f"  drilling new fields: with later wells n={n['with_later_wells']['n']} {pc(n['with_later_wells']['median_later_change'])} (up25 {n['with_later_wells']['share_up_25']:.0%}) | without n={n['no_later_wells']['n']} {pc(n['no_later_wells']['median_later_change'])} (up25 {n['no_later_wells']['share_up_25']:.0%}) | p {n['p']:.3f} regression p {n['regression_p']:.3f}")
    ol = D["old_fields"]
    print(f"  drilling old fields: producing n={ol['n_producing']} rho {ol['rho_producing']['rho']:+.2f} p {ol['rho_producing']['p']:.4f}; terciles {[(t['label'], t['n'], pc(t['median_growth'])) for t in ol['terciles_producing']]}; with size p {ol['checks']['regression_with_size']['log_rel']['p']:.2f}")
    for m in HD["models"]:
        print(f"  model: {m['label']}: AUC {m['cv_auc']:.2f} null95 {m['null_auc_p95']:.2f} p {m['permutation_p']:.3f}")
    mid = NO["midlife"]
    print(f"  older fields: n={mid['n']} sum {mid['sum_2004']:.0f} -> {mid['sum_last']:.0f} ({pc(mid['weighted'])}); producing {mid['n_still_producing']}, below 2004: {mid['share_below_1_still_producing']:.0%}")
    h5 = NO["headline"]["af5"]
    print(f"  first pass (base end of start-up year) y5: n={h5['n']} median {pc(h5['median'])} down {h5['n_down']} up {h5['n_up']}")
    print(f"  fields {NO['meta']['n_fields']} rows {NO['meta']['n_rows']}")
    ex = {p["name"]: p for p in S["points"]}
    for nm in ("OSELVAR", "VEGA", "GAUPE", "EDVARD GRIEG", "JOHAN SVERDRUP", "BRYNHILD", "MARIA"):
        if nm in ex:
            print(f"    {nm}: pre {ex[nm]['size']:.1f} MSm3 afp1 {pc(ex[nm]['afp1'])} afp3 {pc(ex[nm]['afp3'])} afp5 {pc(ex[nm]['afp5']) if ex[nm]['afp5'] else 'n/a'}")
    print("UK")
    O, R = UE["outcome"], UE["revisions"]
    print(f"  editions: oil estimates by year {UE['meta']['oil_estimates_by_year']}; oil fields {UE['meta']['n_oil_fields']}; >=2 est {UE['meta']['n_with_two_or_more']}; update2002 check {UE['meta']['update2002_check']}")
    a = O["all"]
    print(f"  outcome: n={O['n']} (Watkins {O['n_watkins']}, editions {O['n_editions']}) median {pc(a['median'])} CI [{pc(a['ci90'][0])}, {pc(a['ci90'][1])}] up25 {a['share_up']:.0%} down20 {a['share_down']:.0%} typical ±{a['typical_change']:.0%}; small n={O['small']['n']} ±{O['small']['typical_change']:.0%} large n={O['large']['n']} ±{O['large']['typical_change']:.0%} p {O['p_magnitude']:.2f}; dropped {O['dropped_incomplete_production']}")
    g = R["groups"]
    print(f"  revisions 1997-2000: young n={g['young']['n']} ±{g['young']['typical_change']:.0%} mature n={g['mature']['n']} ±{g['mature']['typical_change']:.0%} p {R['p_young_vs_mature_magnitude']:.3f}; small n={g['all_small']['n']} ±{g['all_small']['typical_change']:.0%} large n={g['all_large']['n']} ±{g['all_large']['typical_change']:.0%} p {R['p_small_vs_large_magnitude_all']:.2f}")
    for st in R["steps"]:
        print(f"    {st['from']}->{st['to']}: n={st['n']} changed>10% {st['share_changed_10pct']:.0%} typical ±{st['typical_change']:.0%}")
    i = UK["indicator"]["uk_vs_brown_book_2001"]
    print(f"  indicator: n={i['n']} above 1: {i['share_above_1']:.0%}; Watkins factors UK {UK['watkins']['UK']['weighted_af']:.2f} Norway {UK['watkins']['Norway']['weighted_af']:.2f}; chain ×{UK['norway_chain']['all']['af_latest']:.2f} (n={UK['norway_chain']['all']['n']})")


if __name__ == "__main__":
    main()
