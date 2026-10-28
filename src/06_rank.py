"""Step 6: rank main-sample schools by the empirical-Bayes-shrunken residual of the ranking model (A-int, chosen in Step 5).

Why shrink: a residual on a 60-student cohort is far noisier than one on a 3,000-student cohort, yet
a raw ranking treats them alike, so small schools crowd both tails. Empirical Bayes pulls each residual
toward zero in proportion to its noise:
    sigma_i^2 = p_i (1 - p_i) / n_i        binomial sampling variance of the school's rate (p_i = predicted rate, n_i = first-gen cohort)
    tau^2     = max(var(residual) - mean(sigma_i^2), 0)   between-school variance of the TRUE residual (method of moments)
    shrink_i  = tau^2 / (tau^2 + sigma_i^2)
    residual_eb = residual * shrink_i
A school with a large cohort keeps ~all of its residual; a tiny cohort keeps a fraction.
Primary ranking = residual_eb. The raw ranking is kept as rank_raw and the change is reported.
Also compares against (a) the no-Carnegie spec and (b) the archived pre-review ranking.
Output: data/clean/ranked_schools.csv, reports/06_rankings.md, results.json["step6"].
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
REP = ROOT / "reports"
LARGE_COHORT = 500   # the memo's peer table and the dashboard's large-school list: first-gen cohorts of at least this size
OUT_COLS = ["rank", "rank_raw", "unitid", "instnm", "stabbr", "control_label", "carnegie_group", "ugds", "pctpell", "adm_rate", "first_gen", "firstgen_yr6_n",
            "firstgen_comp_orig_yr6_rt", "predicted", "residual", "shrink_factor", "residual_eb", "residual_pct_pts", "residual_eb_pct_pts", "residual_percentile", "residual_decile",
            "not1stgen_comp_orig_yr6_rt", "fg_gap", "exp_core_per_fte", "exp_instruction_per_fte", "exp_academic_support_per_fte", "exp_student_services_per_fte",
            "exp_institutional_support_per_fte", "oi_matched", "oi_tier_name", "oi_mr_kq5_pq1", "oi_par_q1"]
SHOW = ["rank", "rank_raw", "instnm", "stabbr", "control_label", "carnegie_group", "ugds", "firstgen_yr6_n", "pctpell", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts", "shrink_factor", "residual_eb_pct_pts"]
REN = {"instnm": "school", "control_label": "control", "carnegie_group": "Carnegie", "ugds": "undergrads", "firstgen_yr6_n": "FG cohort", "pctpell": "Pell share", "firstgen_comp_orig_yr6_rt": "actual",
       "residual_pct_pts": "raw resid (pts)", "shrink_factor": "shrink", "residual_eb_pct_pts": "EB resid (pts)"}


def shrink(resid: pd.Series, p: pd.Series, n: pd.Series):
    p = p.clip(0.05, 0.95)
    sigma2 = p * (1 - p) / n
    tau2 = max(float(resid.var() - sigma2.mean()), 1e-6)
    factor = tau2 / (tau2 + sigma2)
    return resid * factor, factor, tau2, sigma2


def main():
    full = pd.read_parquet(CLEAN / "analysis_scored.parquet")
    df = full[full.in_main == 1].copy()
    df["residual_eb"], df["shrink_factor"], tau2, sigma2 = shrink(df["residual"], df["predicted"], df["firstgen_yr6_n"])
    df["residual_eb_pct_pts"] = df["residual_eb"] * 100
    df["rank_raw"] = df["residual"].rank(ascending=False, method="first").astype(int)
    df = df.sort_values("residual_eb", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    df["residual_percentile"] = (1 - (df["rank"] - 1) / len(df)) * 100
    df["residual_decile"] = pd.qcut(df["residual_eb"], 10, labels=range(1, 11)).astype(int)
    df["group"] = np.select([df.residual_decile == 10, df.residual_decile == 1], ["top 10%", "bottom 10%"], "middle")
    n_top = int((df.group == "top 10%").sum())
    raw_top = set(df.nsmallest(n_top, "rank_raw").unitid); eb_top = set(df[df.group == "top 10%"].unitid)
    left_top = df[df.unitid.isin(raw_top - eb_top)]; entered_top = df[df.unitid.isin(eb_top - raw_top)]
    raw_bot = set(df.nlargest(n_top, "rank_raw").unitid); eb_bot = set(df[df.group == "bottom 10%"].unitid)
    left_bot = df[df.unitid.isin(raw_bot - eb_bot)]
    sf = full[full.in_main == 0].copy()
    for c in ["rank", "rank_raw", "residual_percentile", "residual_decile", "residual_eb", "shrink_factor", "residual_eb_pct_pts"]: sf[c] = np.nan
    sf["group"] = "excluded (not ranked)"
    scored = pd.concat([df, sf]); scored.to_parquet(CLEAN / "analysis_scored.parquet", index=False); scored.to_csv(CLEAN / "analysis_scored.csv", index=False)
    df[OUT_COLS + ["group"]].to_csv(CLEAN / "ranked_schools.csv", index=False)

    fmt = lambda d: d[SHOW].rename(columns=REN).round(3).to_markdown(index=False)  # noqa: E731
    top25, bot25, high_pell = df.head(25), df.tail(25), df[df.pctpell >= 0.5].head(15)
    top_large = df[df.firstgen_yr6_n >= LARGE_COHORT].head(6)          # the memo's peer table and the dashboard's large schools list
    top_dec, bot_dec = df[df.group == "top 10%"], df[df.group == "bottom 10%"]
    shrink_by_size = df.assign(bucket=pd.cut(df.firstgen_yr6_n, [0, 100, 250, 500, 1000, 1e9], labels=["<100", "100-249", "250-499", "500-999", "1000+"])).groupby("bucket", observed=True).agg(schools=("unitid", "size"), mean_shrink=("shrink_factor", "mean"), in_raw_top=("unitid", lambda u: u.isin(raw_top).sum()), in_eb_top=("unitid", lambda u: u.isin(eb_top).sum())).round(3)
    rho_raw_eb = stats.spearmanr(df["residual"], df["residual_eb"]).statistic

    old = full.sort_values("residual_A0", ascending=False).reset_index(drop=True); old["rank_A0"] = old.index + 1
    rho_a0 = stats.spearmanr(df.merge(old[["unitid", "rank_A0"]], on="unitid")[["rank", "rank_A0"]].values[:, 0], df.merge(old[["unitid", "rank_A0"]], on="unitid")["rank_A0"]).statistic
    n_sf_in_old_top20 = int(old.head(20)["special_focus"].sum())
    v2 = pd.read_csv(REP / "archive/v2_ranked_schools_carnegie_shrunk.csv")[["unitid", "rank", "residual_eb", "instnm"]].rename(columns={"rank": "rank_v2", "residual_eb": "residual_eb_v2", "instnm": "instnm_v2"})
    v2m = df.merge(v2, on="unitid"); rho_v2 = stats.spearmanr(v2m["residual_eb"], v2m["residual_eb_v2"]).statistic
    v2_top20 = v2.nsmallest(20, "rank_v2"); v2_top20_overlap = len(set(df.head(20).unitid) & set(v2_top20.unitid))
    v2_left = v2_top20[~v2_top20.unitid.isin(df.head(20).unitid)].merge(full[["unitid", "excluded_reason", "ug25abv", "pct_distance"]], on="unitid", how="left").merge(df[["unitid", "rank"]], on="unitid", how="left")
    v2_topdec_overlap = len(eb_top & set(v2.nsmallest(n_top, "rank_v2").unitid)) / n_top
    # California State University system (incl. SDSU) for the reviewer's request
    is_csu = (full.stabbr == "CA") & (full.instnm.str.startswith("California State University") | full.instnm.str.startswith("California State Polytechnic") | full.instnm.str.startswith("California Polytechnic State")
                                      | full.instnm.isin(["San Diego State University", "San Jose State University", "San Francisco State University", "Sonoma State University", "Cal Poly Humboldt", "Humboldt State University"]))
    csu = pd.concat([df[df.unitid.isin(full[is_csu].unitid)], sf[sf.unitid.isin(full[is_csu].unitid)]]).sort_values("residual_eb", ascending=False, na_position="last")
    csu_tab = csu[["instnm", "ugds", "firstgen_yr6_n", "pctpell", "firstgen_comp_orig_yr6_rt", "predicted", "residual_pct_pts", "shrink_factor", "residual_eb_pct_pts", "rank", "residual_decile", "group"]].round(3).rename(columns={
        "instnm": "campus", "ugds": "undergrads 2017", "firstgen_yr6_n": "FG cohort", "pctpell": "Pell 2017-18", "firstgen_comp_orig_yr6_rt": "actual", "residual_pct_pts": "raw resid (pts)", "shrink_factor": "shrink", "residual_eb_pct_pts": "shrunken resid (pts)", "residual_decile": "decile"})
    v4 = pd.read_csv(REP / "archive/v4_ranked_schools_pre_opeid_rule.csv")[["unitid", "rank", "residual_eb", "instnm"]].rename(columns={"rank": "rank_v4", "residual_eb": "residual_eb_v4", "instnm": "instnm_v4"})
    v4m = df.merge(v4, on="unitid"); rho_v4 = stats.spearmanr(v4m["residual_eb"], v4m["residual_eb_v4"]).statistic
    v4_top20 = v4.nsmallest(20, "rank_v4"); v4_top20_overlap = len(set(df.head(20).unitid) & set(v4_top20.unitid))
    v4_left = v4_top20[~v4_top20.unitid.isin(df.head(20).unitid)].merge(full[["unitid", "excluded_reason"]], on="unitid", how="left").merge(df[["unitid", "rank"]], on="unitid", how="left")
    v4_topdec_overlap = len(eb_top & set(v4.nsmallest(n_top, "rank_v4").unitid)) / n_top
    v1 = pd.read_csv(REP / "archive/v1_ranked_schools_mistimed.csv")[["unitid", "rank", "residual"]].rename(columns={"rank": "rank_v1", "residual": "residual_v1"})
    v1m = df.merge(v1, on="unitid"); rho_v1 = stats.spearmanr(v1m["residual_eb"], v1m["residual_v1"]).statistic
    v1_top20_overlap = len(set(df.head(20).unitid) & set(v1.nsmallest(20, "rank_v1").unitid))
    v1_topdec_overlap = len(eb_top & set(v1.nsmallest(n_top, "rank_v1").unitid)) / n_top

    lines = ["# Ranked schools by shrunken residual (Step 6)\n", "Generated by `src/06_rank.py`. Primary ranking = empirical-Bayes-shrunken residual of Model A (entry-year traits + Carnegie group). Special-focus schools excluded.\n",
             f"\n## Shrinkage\n\n- Between-school variance of the true residual τ² = {tau2:.5f} (SD {np.sqrt(tau2)*100:.1f} pts); median sampling variance σ² = {sigma2.median():.5f} (SD {np.sqrt(sigma2.median())*100:.1f} pts).",
             f"- Shrink factor: median {df.shrink_factor.median():.3f}, min {df.shrink_factor.min():.3f} (cohort {int(df.loc[df.shrink_factor.idxmin(), 'firstgen_yr6_n'])}), max {df.shrink_factor.max():.3f}.",
             f"- Spearman between raw and shrunken residuals: {rho_raw_eb:.3f}.\n", "\nShrinkage and top-decile membership by cohort size:\n", shrink_by_size.to_markdown(),
             f"\n\n## Who changed in the top decile ({n_top} schools)\n\n- {len(left_top)} schools left the raw top decile after shrinkage; **{int((left_top.firstgen_yr6_n < 100).sum())} of them had first-gen cohorts under 100** (median cohort {int(left_top.firstgen_yr6_n.median()) if len(left_top) else 0}).",
             f"- {len(entered_top)} schools entered (median cohort {int(entered_top.firstgen_yr6_n.median()) if len(entered_top) else 0}).",
             f"- Bottom decile: {len(left_bot)} schools left, {int((left_bot.firstgen_yr6_n < 100).sum())} with cohorts under 100.\n",
             "\nSchools that left the top decile:\n", left_top.sort_values("rank_raw")[SHOW].rename(columns=REN).round(3).to_markdown(index=False),
             f"\n\n{len(df):,} schools ranked. Top decile cut (shrunken): ≥ {top_dec.residual_eb.min()*100:+.1f} pts; bottom decile: ≤ {bot_dec.residual_eb.max()*100:+.1f} pts.\n",
             "\n## Top 25 over-performers (shrunken)\n", fmt(top25), "\n\n## Bottom 25 under-performers (shrunken)\n", fmt(bot25),
             "\n\n## Top 15 among high-Pell schools (Pell share ≥ 50% in 2017-18)\n", fmt(high_pell),
             f"\n\n## California State University campuses (SDSU and all CSU campuses in the file)\n\nResiduals in percentage points; rank and decile are among the {len(df):,} main-sample schools (10 = best decile). Campuses in an excluded group are shown but not ranked.\n", csu_tab.round(3).to_markdown(index=False),
             f"\n\n## How the top 20 changed when shared-OPEID campuses were set aside (v4 → current)\n\n- Spearman between v4 and current shrunken residuals on the {len(v4m):,} common schools: {rho_v4:.3f}; {v4_top20_overlap} of the v4 top 20 remain in the current top 20; top-decile overlap {v4_topdec_overlap:.0%}.\n",
             "\nv4 top-20 schools no longer in the top 20 (blank rank = now set aside):\n", v4_left[["rank_v4", "instnm_v4", "excluded_reason", "rank"]].to_markdown(index=False),
             f"\n\n## How the top 20 changed when age-25+ and exclusively-online shares were added (v2 → v3)\n\n- Spearman between v2 and current shrunken residuals on common schools: {rho_v2:.3f}; {v2_top20_overlap} of the v2 top 20 remain in the current top 20; top-decile overlap {v2_topdec_overlap:.0%}.\n",
             "\nv2 top-20 schools no longer in the top 20 (blank rank = now in an excluded group):\n", v2_left[["rank_v2", "instnm_v2", "excluded_reason", "ug25abv", "pct_distance", "rank"]].round(3).to_markdown(index=False),
             f"\n\n## Comparisons with earlier specifications\n\n- vs the no-Carnegie spec on all {len(old):,} schools (raw residual): Spearman {rho_a0:.3f}; {n_sf_in_old_top20} of its top 20 were special-focus schools.",
             f"- vs the archived pre-review ranking (Aug-2024 Scorecard file, 2024 traits, no Carnegie, special focus included, raw residual): Spearman {rho_v1:.3f} on {len(v1m):,} common schools, {v1_top20_overlap} of 20 top-20 schools in common, top-decile overlap {v1_topdec_overlap:.0%}.\n",
             "\n## Residual by Carnegie group and control (should average ~0 within each)\n", df.groupby(["carnegie_group", "control_label"])["residual_eb"].agg(["count", "mean", "std"]).round(4).to_markdown(), "\n\nFull list: `data/clean/ranked_schools.csv`.\n"]
    (REP / "06_rankings.md").write_text("\n".join(lines))
    results = json.loads((REP / "results.json").read_text())
    rec = lambda r: {"school": r.instnm, "state": r.stabbr, "carnegie": r.carnegie_group, "ugds": int(r.ugds), "cohort": int(r.firstgen_yr6_n), "pell": round(r.pctpell, 2), "actual": round(r.firstgen_comp_orig_yr6_rt, 3), "predicted": round(r.predicted, 3), "resid_pp": round(r.residual_pct_pts, 1), "resid_eb_pp": round(r.residual_eb_pct_pts, 1), "rank_raw": int(r.rank_raw)}  # noqa: E731
    results["step6"] = {"n_ranked": len(df), "top_decile_n": n_top, "top_decile_cut_pp": round(float(top_dec.residual_eb.min() * 100), 2), "bottom_decile_cut_pp": round(float(bot_dec.residual_eb.max() * 100), 2),
                        "tau2": round(tau2, 6), "tau_pp": round(float(np.sqrt(tau2) * 100), 2), "shrink_median": round(float(df.shrink_factor.median()), 4), "shrink_min": round(float(df.shrink_factor.min()), 4),
                        "spearman_raw_vs_eb": round(float(rho_raw_eb), 4), "top_decile_left": len(left_top), "top_decile_left_under100": int((left_top.firstgen_yr6_n < 100).sum()), "top_decile_entered": len(entered_top),
                        "bottom_decile_left": len(left_bot), "bottom_decile_left_under100": int((left_bot.firstgen_yr6_n < 100).sum()),
                        "top5": [rec(r) for r in df.head(5).itertuples()], "top5_high_pell": [rec(r) for r in high_pell.head(5).itertuples()], "top_large": [rec(r) for r in top_large.itertuples()], "bottom3": [rec(r) for r in df.tail(3).itertuples()],
                        "spearman_old_vs_new": round(float(rho_a0), 4), "spearman_vs_v2": round(float(rho_v2), 4), "top20_overlap_vs_v2": v2_top20_overlap, "top_decile_overlap_vs_v2": round(float(v2_topdec_overlap), 4),
                        "v2_top20_left": v2_left[["rank_v2", "instnm_v2", "excluded_reason", "rank"]].astype(object).where(v2_left[["rank_v2", "instnm_v2", "excluded_reason", "rank"]].notna(), None).to_dict("records"),
                        "csu": csu_tab.astype(object).where(csu_tab.notna(), None).round(3).to_dict("records"), "special_focus_in_old_top20": n_sf_in_old_top20, "spearman_vs_v1_mistimed": round(float(rho_v1), 4), "top20_overlap_vs_v1": v1_top20_overlap,
                        "top_decile_overlap_vs_v1": round(float(v1_topdec_overlap), 4), "n_common_v1": len(v1m), "large_cohort_min": LARGE_COHORT, "n_large_cohort": int((df.firstgen_yr6_n >= LARGE_COHORT).sum()),
                        "spearman_vs_v4": round(float(rho_v4), 4), "top20_overlap_vs_v4": v4_top20_overlap, "top_decile_overlap_vs_v4": round(float(v4_topdec_overlap), 4), "n_common_v4": len(v4m),
                        "v4_top20_left": v4_left[["rank_v4", "instnm_v4", "excluded_reason", "rank"]].astype(object).where(v4_left[["rank_v4", "instnm_v4", "excluded_reason", "rank"]].notna(), None).to_dict("records"),
                        "top_decile_mean_pell": round(float(top_dec.pctpell.mean()), 3), "bottom_decile_mean_pell": round(float(bot_dec.pctpell.mean()), 3),
                        "top_decile_private_share": round(float(top_dec.private.mean()), 3), "bottom_decile_private_share": round(float(bot_dec.private.mean()), 3)}
    (REP / "results.json").write_text(json.dumps(results, indent=2))
    print(fmt(top25.head(12))); print(f"\ntau {np.sqrt(tau2)*100:.1f} pts; shrink median {df.shrink_factor.median():.3f} min {df.shrink_factor.min():.3f}; rho raw/eb {rho_raw_eb:.3f}; top decile left {len(left_top)} (<100: {int((left_top.firstgen_yr6_n < 100).sum())}); vs v1 rho {rho_v1:.3f} top20 overlap {v1_top20_overlap}")
    print(shrink_by_size.to_string()); print(f"\nvs v2: rho {rho_v2:.3f}, top20 overlap {v2_top20_overlap}"); print(v2_left.to_string()); print(csu_tab.round(3).to_string())


if __name__ == "__main__":
    main()
