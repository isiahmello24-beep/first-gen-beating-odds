"""Step 7: compare the top 10% and bottom 10% of schools (by Model A residual) on spending categories.

Spending = IPEDS functional expenses per 12-month FTE, averaged over FY2018-FY2023 (the cohort's years).
Tests: Welch t-test on log dollars per FTE, Mann-Whitney U. Deciles are of the shrunken residual (Step 6).
Variants: FY2018-19 only (first two years), all six years in FY2023 dollars (CPI-U), FY2023 only (the
mistimed version). Repeated within control type and within each Carnegie group.
Budget shares are reported as composition only: they sum to 100%, so a higher instruction share
is the same fact as a lower share elsewhere, not an independent finding.
Outputs: reports/07_spending_comparison.md, reports/figures/07_*.png/html, results.json["step7"].
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
import plotly.express as px
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
REP = ROOT / "reports"
FIG = REP / "figures"
CATS = {"exp_instruction": "Instruction", "exp_academic_support": "Academic support", "exp_student_services": "Student services", "exp_institutional_support": "Institutional support",
        "exp_research": "Research", "exp_public_service": "Public service", "exp_scholarships": "Scholarships (expensed)", "exp_auxiliary": "Auxiliary enterprises",
        "exp_core": "Core (4 categories)", "exp_total": "Total expenses"}
CORE = ["exp_instruction", "exp_academic_support", "exp_student_services", "exp_institutional_support"]


def compare(top, bot, suffix=""):
    rows = []
    for k, label in CATS.items():
        a, b = top[f"{k}_per_fte{suffix}"], bot[f"{k}_per_fte{suffix}"]
        rows.append({"category": label, "top10_median_$": a.median(), "bottom10_median_$": b.median(), "median_diff_$": a.median() - b.median(),
                     "median_ratio": a.median() / b.median() if b.median() > 0 else np.nan, "top10_mean_$": a.mean(), "bottom10_mean_$": b.mean(),
                     "welch_p_log": stats.ttest_ind(np.log1p(a), np.log1p(b), equal_var=False).pvalue, "mann_whitney_p": stats.mannwhitneyu(a, b, alternative="two-sided").pvalue})
    return pd.DataFrame(rows)


def shares(top, bot, suffix=""):
    return pd.DataFrame([{"category": CATS[k], "top10_mean_share": top[f"{k}_share_core{suffix}"].mean(), "bottom10_mean_share": bot[f"{k}_share_core{suffix}"].mean()} for k in CORE])


def fmt_money(d):
    d = d.copy()
    for c in d.columns:
        if c.endswith("_$"): d[c] = d[c].map(lambda v: f"${v:,.0f}")
        elif c.endswith("_p") or c.endswith("_p_log"): d[c] = d[c].map(lambda v: "<0.001" if v < 0.001 else f"{v:.3f}")
        elif c == "median_ratio": d[c] = d[c].map(lambda v: "n/a" if pd.isna(v) else f"{v:.2f}×")
    return d.to_markdown(index=False)


def main():
    df = pd.read_parquet(CLEAN / "analysis_scored.parquet"); df = df[df.in_main == 1]
    top, bot = df[df.group == "top 10%"], df[df.group == "bottom 10%"]
    all_cmp, all_sh = compare(top, bot), shares(top, bot)
    fy23_cmp = compare(top, bot, "_fy23")
    variants = {"FY2018-23 nominal average (main)": compare(top, bot), "FY2018-19 only": compare(top, bot, "_fy1819"),
                "FY2018-23 in FY2023 dollars": compare(top, bot, "_real"), "FY2023 only (mistimed)": fy23_cmp}
    var_tab = pd.DataFrame({v: {r["category"]: f"{r['median_ratio']:.2f}× (p {('<0.001' if r['mann_whitney_p'] < 0.001 else f'{r[chr(109)+chr(97)+chr(110)+chr(110)+chr(95)+chr(119)+chr(104)+chr(105)+chr(116)+chr(110)+chr(101)+chr(121)+chr(95)+chr(112)]:.2f}')})" for r in d.to_dict("records") if r["category"] in list(CATS.values())[:4] + ["Core (4 categories)"]} for v, d in variants.items()})
    by_carn = {g: (compare(top[top.carnegie_group == g], bot[bot.carnegie_group == g]), int((top.carnegie_group == g).sum()), int((bot.carnegie_group == g).sum())) for g in ["Doctoral", "Master's", "Baccalaureate"]}
    by_ctrl = {c: (compare(top[top.control_label == c], bot[bot.control_label == c]), shares(top[top.control_label == c], bot[bot.control_label == c]),
                   int((top.control_label == c).sum()), int((bot.control_label == c).sum())) for c in ["Public", "Private nonprofit"]}
    prof_cols = ["ugds", "pctpell", "adm_rate", "first_gen", "private", "fte_total", "firstgen_comp_orig_yr6_rt", "predicted"]
    profile = pd.DataFrame({"top 10%": top[prof_cols].median(), "bottom 10%": bot[prof_cols].median()}).round(3)
    carn_mix = pd.crosstab(df.group, df.carnegie_group, normalize="index").loc[["top 10%", "bottom 10%"]].round(3)

    core_lbl = [CATS[k] for k in CORE]
    long = pd.DataFrame([{"group": g, "category": CATS[k], "median $ per FTE": d[f"{k}_per_fte"].median()} for g, d in [("top 10%", top), ("bottom 10%", bot)] for k in CORE])
    px.bar(long, x="category", y="median $ per FTE", color="group", barmode="group", title="Median spending per FTE (FY2018-23 avg): top 10% vs bottom 10% residual schools",
           color_discrete_map={"top 10%": "#2a9d8f", "bottom 10%": "#e76f51"}).write_html(FIG / "07_spending_top_vs_bottom.html", include_plotlyjs="cdn")
    f, ax = plt.subplots(figsize=(9, 5.5)); x = np.arange(len(CORE)); w = 0.38
    for i, (grp, color) in enumerate([("top 10%", "#2a9d8f"), ("bottom 10%", "#e76f51")]):
        ax.bar(x + (i - .5) * w, long[long.group == grp]["median $ per FTE"], w, label=grp, color=color)
    ax.set_xticks(x); ax.set_xticklabels(core_lbl); ax.set(title=f"Median $ per FTE by category, FY2018-23 average\ntop 10% (n={len(top)}) vs bottom 10% (n={len(bot)}) by first-gen completion residual", ylabel="$ per FTE"); ax.legend()
    f.tight_layout(); f.savefig(FIG / "07_spending_top_vs_bottom.png", dpi=130); plt.close(f)

    lines = ["# Spending comparison: top 10% vs bottom 10% (Step 7)\n", "Generated by `src/07_spending.py`. Groups = top and bottom deciles of the Model A residual (main sample, special focus excluded). "
             "Dollars are IPEDS expenses per 12-month FTE averaged over fiscal years 2018-2023, the years the AY2017-18 cohort was enrolled.\n",
             "\n## Who is in each group (medians)\n", profile.to_markdown(), "\n\nCarnegie mix:\n", carn_mix.to_markdown(),
             f"\n\nPrivate share: top decile {top.private.mean():.0%}, bottom decile {bot.private.mean():.0%}. Control is in the model, so the residual averages zero within each sector; this difference means the residual spread is wider among privates.\n",
             "\n## Dollars per FTE (FY2018-23 average), all schools\n", fmt_money(all_cmp),
             "\n\n## Timing variants: median ratio top/bottom (Mann-Whitney p)\n", var_tab.to_markdown(),
             "\n\nFY2018-19 covers the cohort's first two years, when most attrition happens. Constant dollars use BLS CPI-U fiscal-year averages (see Step 3 report); because every school faces the same price years, deflating changes levels, not the cross-school comparison.\n",
             "\n## FY2023-only spending in full (the mistimed version)\n", fmt_money(fy23_cmp[fy23_cmp.category.isin(core_lbl + ["Core (4 categories)"])]),
             "\n\n## Composition of core spending (shares sum to 100%, so these are one fact, not four)\n", all_sh.round(3).to_markdown(index=False)]
    for c, (cmp_, sh, nt, nb) in by_ctrl.items():
        lines += [f"\n\n## Within {c} schools only (top n={nt}, bottom n={nb})\n", fmt_money(cmp_[cmp_.category.isin(core_lbl + ["Core (4 categories)"])]), "\n\nComposition:\n", sh.round(3).to_markdown(index=False)]
    for g, (cmp_, nt, nb) in by_carn.items():
        lines += [f"\n\n## Within Carnegie {g} schools only (top n={nt}, bottom n={nb})\n", fmt_money(cmp_[cmp_.category.isin(core_lbl + ["Core (4 categories)"])])]
    lines += ["\n\n![spending](figures/07_spending_top_vs_bottom.png)\n",
              "\nInterpretation guide: `welch_p_log` tests whether mean log-dollars differ (robust to the long right tail); `mann_whitney_p` tests whether one group's values tend to be larger. "
              "Dollar differences are the finding. Shares describe how the same dollars are split and cannot be read as separate evidence.\n"]
    (REP / "07_spending_comparison.md").write_text("\n".join(lines))
    results = json.loads((REP / "results.json").read_text())
    rec = lambda d: {r["category"]: {kk: (None if pd.isna(v) else round(float(v), 4)) for kk, v in r.items() if kk != "category"} for r in d.to_dict("records")}  # noqa: E731
    results["step7"] = {"n_top": len(top), "n_bottom": len(bot), "profile_medians": {k: {kk: float(vv) for kk, vv in v.items()} for k, v in profile.to_dict().items()},
                        "per_fte": rec(all_cmp), "per_fte_fy23_only": rec(fy23_cmp), "per_fte_fy1819": rec(variants["FY2018-19 only"]), "per_fte_real": rec(variants["FY2018-23 in FY2023 dollars"]), "share_core": rec(all_sh),
                        "within_carnegie": {g: {"n_top": nt, "n_bottom": nb, "per_fte": rec(cmp_)} for g, (cmp_, nt, nb) in by_carn.items()},
                        "within_control": {c: {"n_top": nt, "n_bottom": nb, "per_fte": rec(cmp_), "share_core": rec(sh)} for c, (cmp_, sh, nt, nb) in by_ctrl.items()}}
    (REP / "results.json").write_text(json.dumps(results, indent=2))
    print(fmt_money(all_cmp[all_cmp.category.isin(core_lbl + ["Core (4 categories)"])])); print("\nvariants:"); print(var_tab.to_string())
    for g, (cmp_, nt, nb) in by_carn.items(): print(f"\n-- Carnegie {g} ({nt} vs {nb})"); print(fmt_money(cmp_[cmp_.category.isin(core_lbl)]))
    for c, (cmp_, sh, nt, nb) in by_ctrl.items():
        print(f"\n-- within {c} ({nt} vs {nb})"); print(fmt_money(cmp_[cmp_.category.isin(core_lbl)]))


if __name__ == "__main__":
    main()
