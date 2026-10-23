"""Step 5: OLS regression of first-gen 6-year completion on school traits.

Model A (main):  completion ~ Pell share + admission rate + log enrollment + part-time share
                             + first-gen share + private + HBCU + distance-only
Model B:         Model A + log core spending per FTE   (how much does money explain?)
Model C:         Model A + SAT average, on the subset that reports SAT (selectivity sensitivity)

Spending is deliberately left OUT of Model A so that the Step 7 spending comparison asks
"what do over-performers spend on?" rather than "...after adjusting for spending?".
Standard errors are HC3 heteroskedasticity-robust. Diagnostics: residuals vs fitted, Q-Q,
histogram, scale-location, leverage vs residuals (Cook's distance), VIF, Breusch-Pagan, Jarque-Bera.

Outputs: data/clean/analysis_scored.parquet, reports/05_regression.md, reports/figures/05_*.png,
         reports/results.json (key numbers for memo/README/dashboard).
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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
REP = ROOT / "reports"
FIG = REP / "figures"
RESULTS = REP / "results.json"

OUTCOME = "firstgen_comp_orig_yr6_rt"
TRAITS_A = ["pctpell", "adm_rate", "log_ugds", "pptug_ef", "first_gen", "private", "hbcu_flag", "distance_only"]
LABELS = {
    "Intercept": "Intercept", "pctpell": "Pell share (0-1)", "adm_rate": "Admission rate (0-1)", "log_ugds": "log(undergrad enrollment)",
    "pptug_ef": "Part-time share (0-1)", "first_gen": "First-gen share (0-1)", "private": "Private nonprofit (vs public)",
    "hbcu_flag": "HBCU", "distance_only": "Distance-education only", "log_core_per_fte": "log(core spending per FTE)", "sat_avg": "SAT average (points)",
}


def fit(df: pd.DataFrame, traits: list[str]):
    formula = f"{OUTCOME} ~ " + " + ".join(traits)
    return smf.ols(formula, data=df).fit(cov_type="HC3")


def coef_table(res) -> pd.DataFrame:
    ci = res.conf_int()
    t = pd.DataFrame({"term": [LABELS.get(i, i) for i in res.params.index], "coef": res.params.values, "robust_se": res.bse.values,
                      "p_value": res.pvalues.values, "ci_low": ci[0].values, "ci_high": ci[1].values})
    return t


def vif_table(df: pd.DataFrame, traits: list[str]) -> pd.DataFrame:
    X = sm.add_constant(df[traits])
    return pd.DataFrame({"term": [LABELS[t] for t in traits],
                         "VIF": [variance_inflation_factor(X.values, i) for i in range(1, X.shape[1])]})


def diagnostics_plot(res, df, path: Path) -> None:
    fitted, resid = res.fittedvalues, res.resid
    infl = res.get_influence()
    lev, cooks = infl.hat_matrix_diag, infl.cooks_distance[0]
    std_resid = infl.resid_studentized_internal
    fig, ax = plt.subplots(2, 3, figsize=(16, 9.5))
    ax[0, 0].scatter(fitted, resid, s=8, alpha=.5); ax[0, 0].axhline(0, color="k", lw=1)
    ax[0, 0].set(title="Residuals vs fitted", xlabel="Predicted completion rate", ylabel="Residual (actual - predicted)")
    sm.qqplot(resid, line="45", fit=True, ax=ax[0, 1], markersize=3); ax[0, 1].set_title("Normal Q-Q of residuals")
    ax[0, 2].hist(resid, bins=40, edgecolor="white"); ax[0, 2].set(title="Histogram of residuals", xlabel="Residual")
    ax[1, 0].scatter(fitted, np.sqrt(np.abs(std_resid)), s=8, alpha=.5)
    ax[1, 0].set(title="Scale-location", xlabel="Predicted completion rate", ylabel="sqrt(|standardized residual|)")
    ax[1, 1].scatter(lev, std_resid, s=8, alpha=.5); ax[1, 1].axhline(0, color="k", lw=1)
    ax[1, 1].set(title="Leverage vs standardized residuals", xlabel="Leverage", ylabel="Standardized residual")
    top = np.argsort(cooks)[-5:]
    for i in top:
        ax[1, 1].annotate(df["instnm"].iloc[i][:28], (lev[i], std_resid[i]), fontsize=7)
    ax[1, 2].stem(np.arange(len(cooks)), cooks, markerfmt=" ", basefmt=" ")
    ax[1, 2].axhline(4 / len(cooks), color="r", ls="--", lw=1, label="4/n rule of thumb"); ax[1, 2].legend()
    ax[1, 2].set(title="Cook's distance by observation", xlabel="School index", ylabel="Cook's D")
    fig.suptitle("Model A diagnostics: first-gen 6-year completion on school traits", fontsize=14)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def main() -> None:
    df = pd.read_parquet(CLEAN / "analysis.parquet")
    FIG.mkdir(exist_ok=True)

    A = fit(df, TRAITS_A)
    B = fit(df, TRAITS_A + ["log_core_per_fte"])
    dfC = df[df["sat_avg"].notna()].copy()
    C_ = fit(dfC, TRAITS_A + ["sat_avg"])
    C_base = fit(dfC, TRAITS_A)

    df["predicted"] = A.fittedvalues
    df["residual"] = A.resid
    df["residual_pct_pts"] = df["residual"] * 100
    df["predicted_B"] = B.fittedvalues
    df["residual_B"] = B.resid
    df.to_parquet(CLEAN / "analysis_scored.parquet", index=False)
    df.to_csv(CLEAN / "analysis_scored.csv", index=False)

    tabA, tabB, tabC = coef_table(A), coef_table(B), coef_table(C_)
    vif = vif_table(df, TRAITS_A)
    bp_lm, bp_p, _, _ = het_breuschpagan(A.resid, A.model.exog)
    jb, jb_p, skew, kurt = jarque_bera(A.resid)
    infl = A.get_influence()
    cooks = infl.cooks_distance[0]
    n_cooks = int((cooks > 4 / len(df)).sum())
    top_cooks = df.assign(cooks=cooks).nlargest(8, "cooks")[["instnm", "stabbr", "ugds", OUTCOME, "predicted", "cooks"]]
    diagnostics_plot(A, df, FIG / "05_diagnostics_model_a.png")

    # actual vs predicted scatter
    fig, ax = plt.subplots(figsize=(7, 6.5))
    ax.scatter(df["predicted"], df[OUTCOME], s=9, alpha=.45)
    lim = [0, 1]; ax.plot(lim, lim, "k--", lw=1, label="actual = predicted")
    ax.set(xlabel="Predicted first-gen 6-year completion (Model A)", ylabel="Actual", title=f"Actual vs predicted, n = {len(df):,}, R² = {A.rsquared:.3f}")
    ax.legend(); fig.tight_layout(); fig.savefig(FIG / "05_actual_vs_predicted.png", dpi=130); plt.close(fig)

    def fmt(t: pd.DataFrame) -> str:
        t = t.copy()
        for c in ["coef", "robust_se", "ci_low", "ci_high"]: t[c] = t[c].map(lambda v: f"{v:.4f}")
        t["p_value"] = t["p_value"].map(lambda v: "<0.001" if v < 0.001 else f"{v:.3f}")
        return t.to_markdown(index=False)

    pct = lambda v: v * 100  # noqa: E731
    lines = [
        "# Regression (Step 5)\n", "Generated by `src/05_regress.py`. Outcome: share of first-generation federal-aid students completing at the same institution within 6 years (0-1 scale). Standard errors are HC3 robust.\n",
        f"\n## Model A (main): school traits, no spending — n = {int(A.nobs):,}, R² = {A.rsquared:.3f}, adj. R² = {A.rsquared_adj:.3f}, residual SD = {np.sqrt(A.mse_resid):.3f}\n",
        fmt(tabA),
        "\n\nReading the coefficients: a coefficient of -0.30 on Pell share means that moving from a school where 20% of students get Pell to one where 60% do (a 0.4 change) predicts a completion rate 0.30 × 0.4 = 12 percentage points lower, holding the other traits fixed. "
        f"Here the Pell coefficient is {A.params['pctpell']:.3f}, so that 40-point difference in Pell share predicts {abs(A.params['pctpell'])*0.4*100:.1f} points {'lower' if A.params['pctpell']<0 else 'higher'} completion.\n",
        f"\n## Model B: Model A + log core spending per FTE — n = {int(B.nobs):,}, R² = {B.rsquared:.3f} (Model A: {A.rsquared:.3f})\n", fmt(tabB),
        f"\n\nA 10% increase in core spending per student is associated with a {B.params['log_core_per_fte']*np.log(1.1)*100:+.2f} percentage-point change in first-gen completion, holding Model A traits fixed. "
        f"Adding spending raises R² by {B.rsquared - A.rsquared:.3f}.\n",
        f"\n## Model C: Model A + SAT average, SAT-reporting schools only — n = {int(C_.nobs):,}, R² = {C_.rsquared:.3f} (Model A on same schools: {C_base.rsquared:.3f})\n", fmt(tabC),
        "\n\n## Multicollinearity (VIF, Model A)\n", vif.round(2).to_markdown(index=False),
        "\n\nVIF (variance inflation factor) above 5 would signal predictors that move together so closely the model cannot separate them.\n",
        "\n## Diagnostics (Model A)\n",
        f"- Breusch-Pagan test for heteroskedasticity: LM = {bp_lm:.1f}, p = {bp_p:.2e}. {'Residual spread varies with the predictors, which is why robust (HC3) standard errors are used.' if bp_p < 0.05 else 'No evidence of heteroskedasticity.'}",
        f"- Jarque-Bera normality of residuals: JB = {jb:.1f}, p = {jb_p:.2e}, skew = {skew:.2f}, kurtosis = {kurt:.2f}. With n = {len(df):,}, coefficient inference does not rely on normal residuals (central limit theorem); this matters only for prediction intervals.",
        f"- Influence: {n_cooks} schools exceed the 4/n Cook's distance rule of thumb ({4/len(df):.4f}). Step 8 re-fits without the largest 5% of schools as a robustness check.",
        "\nMost influential schools:\n", top_cooks.round(4).to_markdown(index=False),
        "\n\n![diagnostics](figures/05_diagnostics_model_a.png)\n", "![actual vs predicted](figures/05_actual_vs_predicted.png)\n",
    ]
    (REP / "05_regression.md").write_text("\n".join(lines))

    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    results["step5"] = {
        "n": int(A.nobs), "r2_A": round(A.rsquared, 4), "adj_r2_A": round(A.rsquared_adj, 4), "resid_sd_A": round(float(np.sqrt(A.mse_resid)), 4),
        "coef_A": {k: round(float(v), 5) for k, v in A.params.items()}, "p_A": {k: round(float(v), 5) for k, v in A.pvalues.items()},
        "se_A": {k: round(float(v), 5) for k, v in A.bse.items()},
        "r2_B": round(B.rsquared, 4), "coef_B_log_core": round(float(B.params["log_core_per_fte"]), 5), "p_B_log_core": round(float(B.pvalues["log_core_per_fte"]), 5),
        "pp_per_10pct_spending": round(float(B.params["log_core_per_fte"] * np.log(1.1) * 100), 3),
        "n_C": int(C_.nobs), "r2_C": round(C_.rsquared, 4), "r2_C_base": round(C_base.rsquared, 4), "coef_C_sat_per_100": round(float(C_.params["sat_avg"] * 100), 5),
        "bp_p": float(bp_p), "jb_p": float(jb_p), "n_cooks_4n": n_cooks, "max_vif": round(float(vif["VIF"].max()), 2),
        "outcome_mean": round(float(df[OUTCOME].mean()), 4), "outcome_sd": round(float(df[OUTCOME].std()), 4),
    }
    RESULTS.write_text(json.dumps(results, indent=2))
    print(A.summary().tables[1]); print(f"\nR2 A={A.rsquared:.3f}  B={B.rsquared:.3f}  C={C_.rsquared:.3f} (base {C_base.rsquared:.3f}, n={int(C_.nobs)})  BP p={bp_p:.2e}  maxVIF={vif['VIF'].max():.2f}")


if __name__ == "__main__":
    main()
