"""Step 7: compare the top 10% and bottom 10% of schools (by residual) on spending categories.

For each IPEDS functional expense category we compare dollars per FTE and the share of
"core" spending (instruction + academic support + student services + institutional support).
Tests: Welch t-test on log dollars per FTE (means), Mann-Whitney U (distributions).
Because private nonprofits spend more and are over-represented in some deciles, the
comparison is also run within control type.
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
CATS = {"exp_instruction": "Instruction", "exp_academic_support": "Academic support", "exp_student_services": "Student services",
        "exp_institutional_support": "Institutional support", "exp_research": "Research", "exp_public_service": "Public service",
        "exp_scholarships": "Scholarships (expensed)", "exp_auxiliary": "Auxiliary enterprises", "exp_core": "Core (4 categories)", "exp_total": "Total expenses"}
CORE = ["exp_instruction", "exp_academic_support", "exp_student_services", "exp_institutional_support"]


def compare(top: pd.DataFrame, bot: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for k, label in CATS.items():
        a, b = top[f"{k}_per_fte"], bot[f"{k}_per_fte"]
        la, lb = np.log1p(a), np.log1p(b)
        t_p = stats.ttest_ind(la, lb, equal_var=False).pvalue
        mw_p = stats.mannwhitneyu(a, b, alternative="two-sided").pvalue
        rows.append({"category": label, "top10_median_$": a.median(), "bottom10_median_$": b.median(), "median_diff_$": a.median() - b.median(),
                     "median_ratio": a.median() / b.median() if b.median() > 0 else np.nan,
                     "top10_mean_$": a.mean(), "bottom10_mean_$": b.mean(), "welch_p_log": t_p, "mann_whitney_p": mw_p})
    return pd.DataFrame(rows)


def shares(top: pd.DataFrame, bot: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for k in CORE:
        a, b = top[f"{k}_share_core"], bot[f"{k}_share_core"]
        rows.append({"category": CATS[k], "top10_mean_share": a.mean(), "bottom10_mean_share": b.mean(), "diff_pct_pts": (a.mean() - b.mean()) * 100,
                     "welch_p": stats.ttest_ind(a, b, equal_var=False).pvalue})
    return pd.DataFrame(rows)


def fmt_money(df: pd.DataFrame) -> str:
    d = df.copy()
    for c in d.columns:
        if c.endswith("_$"): d[c] = d[c].map(lambda v: f"${v:,.0f}")
        elif c.endswith("_p") or c.endswith("_p_log"): d[c] = d[c].map(lambda v: "<0.001" if v < 0.001 else f"{v:.3f}")
        elif c == "median_ratio": d[c] = d[c].map(lambda v: f"{v:.2f}×")
    return d.to_markdown(index=False)


def main() -> None:
    df = pd.read_parquet(CLEAN / "analysis_scored.parquet")
    top, bot = df[df.group == "top 10%"], df[df.group == "bottom 10%"]
    all_cmp, all_sh = compare(top, bot), shares(top, bot)
    by_ctrl = {c: (compare(top[top.control_label == c], bot[bot.control_label == c]), shares(top[top.control_label == c], bot[bot.control_label == c]),
                   int((top.control_label == c).sum()), int((bot.control_label == c).sum())) for c in ["Public", "Private nonprofit"]}
    profile = pd.DataFrame({"top 10%": top[["ugds", "pctpell", "adm_rate", "first_gen", "private", "fte_total", "firstgen_comp_orig_yr6_rt", "predicted"]].median(),
                            "bottom 10%": bot[["ugds", "pctpell", "adm_rate", "first_gen", "private", "fte_total", "firstgen_comp_orig_yr6_rt", "predicted"]].median()}).round(3)

    # ---- figures: medians per FTE for the 4 core categories, overall and within control
    core_lbl = [CATS[k] for k in CORE]
    long = []
    for grp, d in [("top 10%", top), ("bottom 10%", bot)]:
        for k in CORE:
            long.append({"group": grp, "category": CATS[k], "median $ per FTE": d[f"{k}_per_fte"].median(), "mean share of core": d[f"{k}_share_core"].mean()})
    long = pd.DataFrame(long)
    fig = px.bar(long, x="category", y="median $ per FTE", color="group", barmode="group", title="Median spending per FTE: top 10% vs bottom 10% residual schools",
                 color_discrete_map={"top 10%": "#2a9d8f", "bottom 10%": "#e76f51"})
    fig.write_html(FIG / "07_spending_top_vs_bottom.html", include_plotlyjs="cdn")
    f, ax = plt.subplots(1, 2, figsize=(14, 5.5))
    x = np.arange(len(CORE)); w = 0.38
    for i, (grp, color) in enumerate([("top 10%", "#2a9d8f"), ("bottom 10%", "#e76f51")]):
        d = long[long.group == grp]
        ax[0].bar(x + (i - .5) * w, d["median $ per FTE"], w, label=grp, color=color)
        ax[1].bar(x + (i - .5) * w, d["mean share of core"] * 100, w, label=grp, color=color)
    for a_, t, yl in [(ax[0], "Median $ per FTE by category", "$ per FTE"), (ax[1], "Mean share of core spending", "% of core spending")]:
        a_.set_xticks(x); a_.set_xticklabels(core_lbl, rotation=15); a_.set(title=t, ylabel=yl); a_.legend()
    f.suptitle(f"Top 10% (n={len(top)}) vs bottom 10% (n={len(bot)}) schools by first-gen completion residual"); f.tight_layout()
    f.savefig(FIG / "07_spending_top_vs_bottom.png", dpi=130); plt.close(f)

    lines = ["# Spending comparison: top 10% vs bottom 10% (Step 7)\n", "Generated by `src/07_spending.py`. Groups = top and bottom deciles of the Model A residual. Dollars are fiscal-year 2022-23 IPEDS expenses per 12-month FTE student.\n",
             f"\n## Who is in each group (medians)\n", profile.to_markdown(),
             f"\n\nPrivate share: top decile {top['private'].mean():.0%}, bottom decile {bot['private'].mean():.0%}. Control is in the model, so this difference is not mechanical; it means the residual spread differs by sector.\n",
             "\n## Dollars per FTE, all schools\n", fmt_money(all_cmp),
             "\n\n## Share of core spending (instruction + academic support + student services + institutional support)\n", all_sh.round(4).to_markdown(index=False)]
    for c, (cmp_, sh, nt, nb) in by_ctrl.items():
        lines += [f"\n\n## Within {c} schools only (top n={nt}, bottom n={nb})\n", fmt_money(cmp_[cmp_.category.isin(core_lbl + ['Core (4 categories)'])]),
                  "\n\nShares of core:\n", sh.round(4).to_markdown(index=False)]
    lines += ["\n\n![spending](figures/07_spending_top_vs_bottom.png)\n",
              "\nInterpretation guide: `welch_p_log` tests whether mean log-dollars differ (robust to the long right tail); `mann_whitney_p` tests whether one group's values tend to be larger. "
              "A category that differs in dollars but not in share means over-performers spend more on everything; a category that differs in share means they allocate differently.\n"]
    (REP / "07_spending_comparison.md").write_text("\n".join(lines))

    results = json.loads((REP / "results.json").read_text())
    rec = lambda d: {r["category"]: {kk: (None if pd.isna(v) else round(float(v), 4)) for kk, v in r.items() if kk != "category"} for r in d.to_dict("records")}  # noqa: E731
    results["step7"] = {"n_top": len(top), "n_bottom": len(bot), "profile_medians": {k: {kk: float(vv) for kk, vv in v.items()} for k, v in profile.to_dict().items()},
                        "per_fte": rec(all_cmp), "share_core": rec(all_sh),
                        "within_control": {c: {"n_top": nt, "n_bottom": nb, "per_fte": rec(cmp_), "share_core": rec(sh)} for c, (cmp_, sh, nt, nb) in by_ctrl.items()}}
    (REP / "results.json").write_text(json.dumps(results, indent=2))
    print(profile.to_string()); print(); print(fmt_money(all_cmp)); print(); print(all_sh.round(4).to_string())
    for c, (cmp_, sh, nt, nb) in by_ctrl.items():
        print(f"\n-- within {c} (n {nt} vs {nb})"); print(fmt_money(cmp_[cmp_.category.isin(core_lbl)])); print(sh.round(4).to_string())


if __name__ == "__main__":
    main()
