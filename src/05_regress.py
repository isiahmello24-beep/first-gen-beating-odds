"""Step 5: OLS regression of first-gen 6-year completion on school traits (cohort-aligned, Carnegie-controlled).

Main sample = non-special-focus schools (Carnegie 2018 doctoral, master's, baccalaureate).
Model A (main):  completion ~ Pell share + admission rate + log enrollment + part-time share + first-gen share
                             + private + HBCU + distance-only + Carnegie group (baseline: Master's)
                 All predictors are entry-year (2017-18) values. Spending is NOT in Model A, so Step 7 can ask
                 "what do over-performers spend on?" without conditioning on spending.
Model A-int: Model A plus private × every trait (Carnegie dummies shared). Chosen as the MAIN ranking model if its
          shrunken ranking overlaps both sector-only rankings better than the pooled model does (rule recorded in results.json).
Model A0 (original spec, for comparison): same traits, no Carnegie dummies, all schools incl. special focus.
Model B:  Model A + log core spending per FTE (FY2018-23 average) + undergraduate share of total FTE
          (so a research university's graduate-heavy denominator does not masquerade as low undergraduate spending).   Model C: Model A + SAT, SAT reporters only.
Special-focus schools are scored out-of-sample with Model A and reported separately (never ranked with the main sample).
HC3 robust SEs. Diagnostics: residual plots, VIF, Breusch-Pagan, Jarque-Bera, Cook's distance.
Outputs: data/clean/analysis_scored.parquet, reports/05_regression.md, reports/figures/05_*.png, reports/results.json["step5"].
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import jarque_bera
from scipy import stats
import importlib.util
_spec = importlib.util.spec_from_file_location("rank06", Path(__file__).with_name("06_rank.py")); _m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_m)
shrink = _m.shrink
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
REP = ROOT / "reports"
FIG = REP / "figures"
RESULTS = REP / "results.json"
OUTCOME = "firstgen_comp_orig_yr6_rt"
TRAITS = ["pctpell", "adm_rate", "log_ugds", "pptug_ef", "first_gen", "ug25abv", "pct_distance", "private", "hbcu_flag"]
TRAITS_PREV = ["pctpell", "adm_rate", "log_ugds", "pptug_ef", "first_gen", "private", "hbcu_flag", "distance_only"]   # spec before the age/online controls
CARNEGIE = "C(carnegie_group, Treatment(reference=\"Master's\"))"
LABELS_BASE = {"pctpell": "Pell share", "adm_rate": "admission rate", "log_ugds": "log enrollment", "pptug_ef": "part-time share", "first_gen": "first-gen share", "ug25abv": "share aged 25+", "pct_distance": "share online", "hbcu_flag": "HBCU"}
LABELS = {**{f"private:{t}": f"Private × {v}" for t, v in LABELS_BASE.items()}, "Intercept": "Intercept (Master's, public)", "pctpell": "Pell share (0-1)", "adm_rate": "Admission rate (0-1)", "log_ugds": "log(undergrad enrollment)",
          "pptug_ef": "Part-time share (0-1)", "first_gen": "First-gen share (0-1)", "private": "Private nonprofit (vs public)", "hbcu_flag": "HBCU",
          "distance_only": "Distance-education only", "ug25abv": "Share of undergrads aged 25+ (0-1)", "pct_distance": "Share exclusively online (0-1)", "log_core_per_fte": "log(core spending per FTE, FY18-23 avg)", "ug_share_fte": "Undergraduate share of total FTE (0-1)", "sat_avg": "SAT average (points)",
          f"{CARNEGIE}[T.Doctoral]": "Carnegie: Doctoral (vs Master's)", f"{CARNEGIE}[T.Baccalaureate]": "Carnegie: Baccalaureate (vs Master's)"}
FORMULA_A = f"{OUTCOME} ~ " + " + ".join(TRAITS) + f" + {CARNEGIE}"
FORMULA_INT = FORMULA_A + " + " + " + ".join(f"private:{t}" for t in TRAITS if t != "private")
FORMULA_SECTOR = f"{OUTCOME} ~ " + " + ".join(t for t in TRAITS if t != "private") + f" + {CARNEGIE}"
FORMULA_A0 = f"{OUTCOME} ~ " + " + ".join(TRAITS_PREV)
FORMULA_PREV = FORMULA_A0 + f" + {CARNEGIE}"


def fit(df, formula):
    return smf.ols(formula, data=df).fit(cov_type="HC3")


def coef_table(res):
    ci = res.conf_int()
    return pd.DataFrame({"term": [LABELS.get(i, i) for i in res.params.index], "coef": res.params.values, "robust_se": res.bse.values,
                         "p_value": res.pvalues.values, "ci_low": ci[0].values, "ci_high": ci[1].values})


def fmt(t):
    t = t.copy()
    for c in ["coef", "robust_se", "ci_low", "ci_high"]: t[c] = t[c].map(lambda v: f"{v:.4f}")
    t["p_value"] = t["p_value"].map(lambda v: "<0.001" if v < 0.001 else f"{v:.3f}")
    return t.to_markdown(index=False)


def diagnostics_plot(res, df, path):
    fitted, resid = res.fittedvalues, res.resid
    infl = res.get_influence(); lev, cooks, std_resid = infl.hat_matrix_diag, infl.cooks_distance[0], infl.resid_studentized_internal
    fig, ax = plt.subplots(2, 3, figsize=(16, 9.5))
    ax[0, 0].scatter(fitted, resid, s=8, alpha=.5); ax[0, 0].axhline(0, color="k", lw=1); ax[0, 0].set(title="Residuals vs fitted", xlabel="Predicted completion rate", ylabel="Residual")
    sm.qqplot(resid, line="45", fit=True, ax=ax[0, 1], markersize=3); ax[0, 1].set_title("Normal Q-Q of residuals")
    ax[0, 2].hist(resid, bins=40, edgecolor="white"); ax[0, 2].set(title="Histogram of residuals", xlabel="Residual")
    ax[1, 0].scatter(fitted, np.sqrt(np.abs(std_resid)), s=8, alpha=.5); ax[1, 0].set(title="Scale-location", xlabel="Predicted", ylabel="sqrt(|std residual|)")
    ax[1, 1].scatter(lev, std_resid, s=8, alpha=.5); ax[1, 1].axhline(0, color="k", lw=1); ax[1, 1].set(title="Leverage vs standardized residuals", xlabel="Leverage", ylabel="Std residual")
    for i in np.argsort(cooks)[-5:]: ax[1, 1].annotate(df["instnm"].iloc[i][:28], (lev[i], std_resid[i]), fontsize=7)
    ax[1, 2].stem(np.arange(len(cooks)), cooks, markerfmt=" ", basefmt=" "); ax[1, 2].axhline(4 / len(cooks), color="r", ls="--", lw=1, label="4/n"); ax[1, 2].legend()
    ax[1, 2].set(title="Cook's distance", xlabel="School index", ylabel="Cook's D")
    fig.suptitle("Model A diagnostics: first-gen 6-year completion on entry-year school traits + Carnegie group", fontsize=13); fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def main():
    FIG.mkdir(exist_ok=True)
    full = pd.read_parquet(CLEAN / "analysis.parquet")
    df = full[full.in_main == 1].copy()
    sf = full[full.in_main == 0].copy()          # special focus + adult/online-dominant, scored out of sample

    A = fit(df, FORMULA_A); A0 = fit(full, FORMULA_A0); A_noc = fit(df, f"{OUTCOME} ~ " + " + ".join(TRAITS)); A_prev = fit(df, FORMULA_PREV if df["distance_only"].nunique() > 1 else FORMULA_PREV.replace(" + distance_only", ""))
    AI = fit(df, FORMULA_INT)
    pub_m = fit(df[df.private == 0], FORMULA_SECTOR); prv_m = fit(df[df.private == 1], FORMULA_SECTOR)
    # ---- ranking comparison: pooled (A) vs interaction (AI) vs sector-only, all shrunken
    cmp = df[["unitid", "private", "firstgen_yr6_n"]].copy()
    cmp["r_pool"] = shrink(A.resid, A.fittedvalues, df.firstgen_yr6_n)[0]
    cmp["r_int"] = shrink(AI.resid, AI.fittedvalues, df.firstgen_yr6_n)[0]
    cmp["r_sec"] = np.nan
    for m, flag in [(pub_m, 0), (prv_m, 1)]:
        sub = df[df.private == flag]; cmp.loc[sub.index, "r_sec"] = shrink(m.resid, m.fittedvalues, sub.firstgen_yr6_n)[0].values
    def overlap(a, b, d):
        k = int(round(len(d) * 0.1)); return len(set(d.nlargest(k, a).unitid) & set(d.nlargest(k, b).unitid)) / k
    rc = {"spearman_int_vs_pool": stats.spearmanr(cmp.r_int, cmp.r_pool).statistic, "top_decile_overlap_int_vs_pool": overlap("r_int", "r_pool", cmp)}
    for flag, name in [(0, "public"), (1, "private")]:
        d = cmp[cmp.private == flag]
        rc[f"spearman_int_vs_sector_{name}"] = stats.spearmanr(d.r_int, d.r_sec).statistic; rc[f"spearman_pool_vs_sector_{name}"] = stats.spearmanr(d.r_pool, d.r_sec).statistic
        rc[f"overlap_int_vs_sector_{name}"] = overlap("r_int", "r_sec", d); rc[f"overlap_pool_vs_sector_{name}"] = overlap("r_pool", "r_sec", d)
    use_int = rc["overlap_int_vs_sector_public"] > rc["overlap_pool_vs_sector_public"] and rc["overlap_int_vs_sector_private"] > rc["overlap_pool_vs_sector_private"]
    MAIN = AI if use_int else A; MAIN_FORMULA = FORMULA_INT if use_int else FORMULA_A; main_name = "A-int (interaction)" if use_int else "A (pooled)"
    B = fit(df, MAIN_FORMULA + " + log_core_per_fte + ug_share_fte")
    B_noug = fit(df, MAIN_FORMULA + " + log_core_per_fte")
    dfC = df[df.sat_avg.notna()]; C_ = fit(dfC, MAIN_FORMULA + " + sat_avg"); C_base = fit(dfC, MAIN_FORMULA)

    df["predicted"], df["residual"] = MAIN.fittedvalues, MAIN.resid
    df["predicted_pooled"], df["residual_pooled"] = A.fittedvalues, A.resid
    df["predicted_int"], df["residual_int"] = AI.fittedvalues, AI.resid
    cooks_main = MAIN.get_influence().cooks_distance[0]
    df["cooks_d"] = cooks_main; df["cooks_flag"] = (cooks_main > 4 / len(df)).astype(int)
    df["predicted_B"], df["residual_B"] = B.fittedvalues, B.resid
    # special-focus schools have no Carnegie dummy in Model A: score them at the Master's baseline (documented in the report)
    sf_in = sf.assign(carnegie_group=np.where(sf.carnegie_group == "Special focus / tribal", "Master's", sf.carnegie_group))
    sf["predicted"] = MAIN.predict(sf_in); sf["residual"] = sf[OUTCOME] - sf["predicted"]; sf["predicted_B"] = np.nan; sf["residual_B"] = np.nan
    sf["predicted_pooled"] = A.predict(sf_in); sf["residual_pooled"] = sf[OUTCOME] - sf["predicted_pooled"]; sf["predicted_int"] = AI.predict(sf_in); sf["residual_int"] = sf[OUTCOME] - sf["predicted_int"]
    sf["cooks_d"] = np.nan; sf["cooks_flag"] = 0
    scored = pd.concat([df, sf]); scored["residual_pct_pts"] = scored["residual"] * 100
    scored["predicted_A0"] = A0.fittedvalues.reindex(scored.index); scored["residual_A0"] = A0.resid.reindex(scored.index)
    scored.to_parquet(CLEAN / "analysis_scored.parquet", index=False); scored.to_csv(CLEAN / "analysis_scored.csv", index=False)

    X = sm.add_constant(pd.get_dummies(df[TRAITS + ["carnegie_group"]], columns=["carnegie_group"], drop_first=False).drop(columns=["carnegie_group_Master's"]).astype(float))
    vif = pd.DataFrame({"term": X.columns[1:], "VIF": [variance_inflation_factor(X.values, i) for i in range(1, X.shape[1])]})
    vif["flag"] = np.where(vif.VIF > 5, "> 5", "")
    corr_pf = df[["pctpell", "first_gen", "adm_rate", "ug25abv"]].corr().round(3)
    Xi = AI.model.exog; vif_int = pd.DataFrame({"term": [LABELS.get(n, n) for n in AI.model.exog_names[1:]], "VIF": [variance_inflation_factor(Xi, i) for i in range(1, Xi.shape[1])]})
    bp_lm, bp_p, _, _ = het_breuschpagan(MAIN.resid, MAIN.model.exog); jb, jb_p, skew, kurt = jarque_bera(MAIN.resid)
    cooks = cooks_main; n_cooks = int((cooks > 4 / len(df)).sum())
    top_cooks = df.assign(cooks=cooks).nlargest(8, "cooks")[["instnm", "stabbr", "ugds", OUTCOME, "predicted", "cooks"]]
    diagnostics_plot(MAIN, df, FIG / "05_diagnostics_model_a.png")
    fig, ax = plt.subplots(figsize=(7, 6.5)); ax.scatter(df["predicted"], df[OUTCOME], s=9, alpha=.45, label=f"main sample ({main_name})")
    ax.scatter(sf["predicted"], sf[OUTCOME], s=14, alpha=.8, color="#e76f51", label="excluded groups (out of sample)")
    ax.plot([0, 1], [0, 1], "k--", lw=1); ax.set(xlabel="Predicted first-gen 6-year completion (Model A)", ylabel="Actual", title=f"Actual vs predicted, n = {len(df):,}, R² = {MAIN.rsquared:.3f}"); ax.legend()
    fig.tight_layout(); fig.savefig(FIG / "05_actual_vs_predicted.png", dpi=130); plt.close(fig)

    sf_tab = sf.sort_values(["excluded_reason", "residual"], ascending=[True, False])[["excluded_reason", "instnm", "stabbr", "hd_c18basic", "ugds", "ug25abv", "pct_distance", "pctpell", OUTCOME, "predicted", "residual"]].round(3)
    lines = ["# Regression (Step 5)\n", "Generated by `src/05_regress.py`. Outcome: share of first-generation federal-aid students in the AY2017-18 entry cohort who completed at the same institution within 6 years (0-1). "
             "Predictors are the school's 2017-18 values. Standard errors are HC3 robust. Main sample excludes Carnegie special-focus / tribal schools and campuses with more than 50% of undergraduates aged 25+ or exclusively online in Fall 2017.\n",
             f"\n## Model A (main): entry-year traits + Carnegie group, no spending — n = {int(A.nobs):,}, R² = {A.rsquared:.3f}, adj. R² = {A.rsquared_adj:.3f}, residual SD = {np.sqrt(A.mse_resid):.3f}\n", fmt(coef_table(A)),
             f"\n\nReading the coefficients: the Pell coefficient is {A.params['pctpell']:.3f}, so a school with a 40-point higher Pell share (0.20 vs 0.60) is predicted {abs(A.params['pctpell'])*0.4*100:.1f} points {'lower' if A.params['pctpell']<0 else 'higher'} on first-gen completion, holding the other traits fixed.\n",
             f"\n## Model A-int: Model A + private × each trait (Carnegie dummies shared) — n = {int(AI.nobs):,}, R² = {AI.rsquared:.3f}\n", fmt(coef_table(AI)),
             f"\n\n### Which model ranks schools? Shrunken-residual rankings compared (top-decile overlap computed within sector)\n\n| Comparison | Spearman | Top-decile overlap |\n|---|---:|---:|\n"
             f"| Interaction vs pooled (all schools) | {rc['spearman_int_vs_pool']:.3f} | {rc['top_decile_overlap_int_vs_pool']:.0%} |\n"
             f"| Pooled vs public-only model (publics) | {rc['spearman_pool_vs_sector_public']:.3f} | {rc['overlap_pool_vs_sector_public']:.0%} |\n"
             f"| Interaction vs public-only model (publics) | {rc['spearman_int_vs_sector_public']:.3f} | {rc['overlap_int_vs_sector_public']:.0%} |\n"
             f"| Pooled vs private-only model (privates) | {rc['spearman_pool_vs_sector_private']:.3f} | {rc['overlap_pool_vs_sector_private']:.0%} |\n"
             f"| Interaction vs private-only model (privates) | {rc['spearman_int_vs_sector_private']:.3f} | {rc['overlap_int_vs_sector_private']:.0%} |\n",
             f"\nRule: the interaction model becomes the main ranking model if its overlap with BOTH sector-only rankings beats the pooled model's. Result: **{'interaction model adopted' if use_int else 'pooled model kept'}** → main model = {main_name}. "
             "The interaction model differs from two separate sector fits only in sharing the Carnegie dummies and the residual variance, so it should sit close to the sector rankings; the point of the test is whether it gets there without splitting the sample.\n",
             f"\n## Specification comparisons on the same {len(df):,} schools\n\n- Model A without Carnegie dummies: R² = {A_noc.rsquared:.3f}.\n- Previous spec (distance-only flag instead of the age-25+ and exclusively-online shares): R² = {A_prev.rsquared:.3f}.\n- Original spec (no Carnegie, distance-only flag) on all {len(full):,} schools including excluded groups: R² = {A0.rsquared:.3f}.\n",
             f"\n## Model B: Model A + log core spending per FTE (FY2018-23 average) + undergraduate share of FTE — n = {int(B.nobs):,}, R² = {B.rsquared:.3f} (Model A: {A.rsquared:.3f})\n", fmt(coef_table(B)),
             f"\n\nA 10% higher core budget per student is associated with {B.params['log_core_per_fte']*np.log(1.1)*100:+.2f} percentage points of first-gen completion, holding Model A traits and the undergraduate share fixed "
             f"(without the undergraduate-share control: {B_noug.params['log_core_per_fte']*np.log(1.1)*100:+.2f} points, R² {B_noug.rsquared:.3f}). Adding spending raises R² by {B.rsquared - A.rsquared:.3f}. "
             f"The undergraduate-share coefficient is {B.params['ug_share_fte']:+.3f} (p = {B.pvalues['ug_share_fte']:.3f}): per-FTE spending at graduate-heavy universities partly serves graduate students, and this term absorbs that.\n",
             f"\n## Model C: Model A + SAT average, SAT-reporting schools only — n = {int(C_.nobs):,}, R² = {C_.rsquared:.3f} (Model A on same schools: {C_base.rsquared:.3f})\n", fmt(coef_table(C_)),
             "\n\n## Multicollinearity (VIF, Model A)\n", vif.round(2).to_markdown(index=False),
             "\n\n## Diagnostics (Model A)\n",
             f"- Breusch-Pagan: LM = {bp_lm:.1f}, p = {bp_p:.2e}. {'Residual spread varies with the predictors; HC3 robust SEs are used.' if bp_p < 0.05 else 'No evidence of heteroskedasticity.'}",
             f"- Jarque-Bera: JB = {jb:.1f}, p = {jb_p:.2e}, skew = {skew:.2f}, kurtosis = {kurt:.2f}. With n = {len(df):,} inference on coefficients does not rely on normal residuals.",
             f"- Influence: {n_cooks} schools exceed the 4/n Cook's distance rule of thumb. Step 8 bootstraps the ranking to show how much any single school matters.",
             "\nMost influential schools:\n", top_cooks.round(4).to_markdown(index=False),
             f"\n\n## Excluded schools ({len(sf)}), scored out-of-sample with Model A and NOT ranked with the main sample\n",
             f"Two groups. (1) Carnegie special-focus / tribal (codes 24-33: faith, medical, health professions, engineering, technology, business, arts, law, other, tribal), scored at the Master's Carnegie baseline: {int((sf.excluded_reason == 'special focus / tribal').sum())} schools. "
             f"(2) Campuses where more than 50% of Fall 2017 undergraduates were aged 25+ or exclusively online: {int((sf.excluded_reason == 'adult (25+) or online share > 50%').sum())} schools. "
             f"(3) Schools whose Scorecard completion rates are implausible against their IPEDS graduation rate (both first-gen and non-first-gen below 25% of C150_4): {int((sf.excluded_reason == 'outcome implausible vs IPEDS grad rate').sum())} schools. "
             "Both serve populations and run programs the main model does not describe, so their residuals are shown for transparency only.\n", sf_tab.to_markdown(index=False),
             "\n\n![diagnostics](figures/05_diagnostics_model_a.png)\n", "![actual vs predicted](figures/05_actual_vs_predicted.png)\n"]
    (REP / "05_regression.md").write_text("\n".join(lines))
    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    results["step5"] = {"main_model": main_name, "main_formula": MAIN_FORMULA, "use_interaction": bool(use_int), "ranking_comparison": {k: round(float(v), 4) for k, v in rc.items()},
                        "r2_int": round(AI.rsquared, 4), "r2_main": round(MAIN.rsquared, 4), "coef_main": {k: round(float(v), 5) for k, v in MAIN.params.items()}, "p_main": {k: round(float(v), 5) for k, v in MAIN.pvalues.items()},
                        "vif": {r.term: round(float(r.VIF), 2) for r in vif.itertuples()}, "vif_over5": [r.term for r in vif.itertuples() if r.VIF > 5], "corr_pell_firstgen": round(float(corr_pf.loc["pctpell", "first_gen"]), 3),
                        "n": int(A.nobs), "n_special_focus": int((sf.excluded_reason == "special focus / tribal").sum()), "n_nontraditional": int((sf.excluded_reason == "adult (25+) or online share > 50%").sum()), "n_anomaly": int((sf.excluded_reason == "outcome implausible vs IPEDS grad rate").sum()), "n_excluded": len(sf), "r2_A_prev_spec": round(A_prev.rsquared, 4), "r2_A": round(A.rsquared, 4), "adj_r2_A": round(A.rsquared_adj, 4), "resid_sd_A": round(float(np.sqrt(A.mse_resid)), 4),
                        "r2_A_no_carnegie": round(A_noc.rsquared, 4), "r2_A0_original_spec_all_schools": round(A0.rsquared, 4), "n_A0": int(A0.nobs),
                        "coef_A": {k: round(float(v), 5) for k, v in A.params.items()}, "p_A": {k: round(float(v), 5) for k, v in A.pvalues.items()}, "se_A": {k: round(float(v), 5) for k, v in A.bse.items()},
                        "r2_B": round(B.rsquared, 4), "coef_B_log_core": round(float(B.params["log_core_per_fte"]), 5), "p_B_log_core": round(float(B.pvalues["log_core_per_fte"]), 5),
                        "pp_per_10pct_spending": round(float(B.params["log_core_per_fte"] * np.log(1.1) * 100), 3),
                        "pp_per_10pct_spending_no_ugshare": round(float(B_noug.params["log_core_per_fte"] * np.log(1.1) * 100), 3), "r2_B_no_ugshare": round(B_noug.rsquared, 4),
                        "coef_B_ug_share": round(float(B.params["ug_share_fte"]), 5), "p_B_ug_share": round(float(B.pvalues["ug_share_fte"]), 5),
                        "n_C": int(C_.nobs), "r2_C": round(C_.rsquared, 4), "r2_C_base": round(C_base.rsquared, 4), "coef_C_sat_per_100": round(float(C_.params["sat_avg"] * 100), 5),
                        "bp_p": float(bp_p), "jb_p": float(jb_p), "n_cooks_4n": n_cooks, "max_vif": round(float(vif["VIF"].max()), 2),
                        "outcome_mean": round(float(df[OUTCOME].mean()), 4), "outcome_sd": round(float(df[OUTCOME].std()), 4),
                        "cohort": "NSLDS AY2017-18 entry cohort measured AY2023-24; predictors 2017-18; spending FY2018-FY2023 average"}
    RESULTS.write_text(json.dumps(results, indent=2))
    print(fmt(coef_table(A))); print(f"\nmain={main_name} | " + " ".join(f"{k}={v:.3f}" for k, v in rc.items())); print(vif.round(2).to_string()); print(f"\nR2 A={A.rsquared:.3f} int={AI.rsquared:.3f} (no Carnegie {A_noc.rsquared:.3f}; prev spec {A_prev.rsquared:.3f}; original spec all schools {A0.rsquared:.3f}; n excluded {len(sf)})  B={B.rsquared:.3f}  C={C_.rsquared:.3f}/{C_base.rsquared:.3f} n={int(C_.nobs)}  BP p={bp_p:.1e} maxVIF={vif['VIF'].max():.2f} cooks>4/n={n_cooks}")


if __name__ == "__main__":
    main()
