"""Step 8: robustness. (a) Bootstrap the residual ranking, 1,000 resamples. (b) Separate public and private models.

(a) Each resample draws n schools with replacement, refits Model A, predicts for EVERY school in the
    original sample, and re-ranks the residuals. For each school we record how often it lands in the top
    decile and the 2.5th-97.5th percentile of its rank. Rank stability of the point-estimate top decile is
    the headline: if membership flips often, the ranking is noise.
(b) Public-only and private-only Model A fits: do coefficients differ by sector, and do sector-specific
    residual deciles tell the same spending story as the pooled model?
Also kept: the drop-largest-5% check from the brief, reported in one line.
Outputs: data/clean/bootstrap_ranks.csv, reports/08_robustness.md, results.json["step8"].
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from patsy import dmatrices
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
REP = ROOT / "reports"
OUTCOME = "firstgen_comp_orig_yr6_rt"
TRAITS = ["pctpell", "adm_rate", "log_ugds", "pptug_ef", "first_gen", "private", "hbcu_flag", "distance_only"]
CARNEGIE = "C(carnegie_group, Treatment(reference=\"Master's\"))"
FORMULA = f"{OUTCOME} ~ " + " + ".join(TRAITS) + f" + {CARNEGIE}"
FORMULA_SECTOR = f"{OUTCOME} ~ " + " + ".join(t for t in TRAITS if t != "private") + f" + {CARNEGIE}"
CORE = {"exp_instruction": "Instruction", "exp_academic_support": "Academic support", "exp_student_services": "Student services", "exp_institutional_support": "Institutional support", "exp_core": "Core (4 categories)"}
B = 1000
SEED = 20261023


def spending_table(t, b):
    rows = []
    for k, lbl in CORE.items():
        a, c = t[f"{k}_per_fte"], b[f"{k}_per_fte"]
        rows.append({"category": lbl, "top10_median_$": a.median(), "bottom10_median_$": c.median(), "median_ratio": a.median() / c.median(),
                     "welch_p_log": stats.ttest_ind(np.log1p(a), np.log1p(c), equal_var=False).pvalue, "mann_whitney_p": stats.mannwhitneyu(a, c, alternative="two-sided").pvalue})
    return pd.DataFrame(rows)


def fm(d):
    d = d.copy()
    for c in d.columns:
        if c.endswith("_$"): d[c] = d[c].map(lambda v: f"${v:,.0f}")
        elif c.endswith("_p") or c.endswith("_p_log"): d[c] = d[c].map(lambda v: "<0.001" if v < 0.001 else f"{v:.3f}")
        elif c == "median_ratio": d[c] = d[c].map(lambda v: f"{v:.2f}×")
    return d.to_markdown(index=False)


def main():
    df = pd.read_parquet(CLEAN / "analysis_scored.parquet"); df = df[df.special_focus == 0].reset_index(drop=True)
    n = len(df); n_top = int(round(n * 0.10))
    point_top = set(df.nlargest(n_top, "residual")["unitid"])

    # ---------------------------------------------------------------- (a) bootstrap
    y, X = dmatrices(FORMULA, df, return_type="dataframe"); y = y.values.ravel(); X = X.values
    rng = np.random.default_rng(SEED)
    in_top = np.zeros(n); rank_sum = np.zeros(n); ranks = np.empty((B, n), dtype=np.int32)
    for b in range(B):
        idx = rng.integers(0, n, n)
        beta, *_ = np.linalg.lstsq(X[idx], y[idx], rcond=None)
        resid = y - X @ beta
        r = stats.rankdata(-resid, method="ordinal")       # 1 = best
        ranks[b] = r; in_top += (r <= n_top); rank_sum += r
    boot = pd.DataFrame({"unitid": df.unitid, "instnm": df.instnm, "point_rank": df["rank"].astype(int), "p_top_decile": in_top / B,
                         "boot_rank_mean": rank_sum / B, "boot_rank_p2_5": np.percentile(ranks, 2.5, axis=0), "boot_rank_p97_5": np.percentile(ranks, 97.5, axis=0)})
    boot.to_csv(CLEAN / "bootstrap_ranks.csv", index=False)
    pt = boot[boot.unitid.isin(point_top)]
    stab = {"n_top_decile": n_top, "mean_p_top_among_point_top": float(pt.p_top_decile.mean()), "share_p_ge_0_9": float((pt.p_top_decile >= 0.9).mean()),
            "share_p_ge_0_5": float((pt.p_top_decile >= 0.5).mean()), "expected_overlap": float(pt.p_top_decile.sum() / n_top),
            "n_outside_with_p_ge_0_5": int(((~boot.unitid.isin(point_top)) & (boot.p_top_decile >= 0.5)).sum()),
            "median_rank_ci_width_top_decile": float((pt.boot_rank_p97_5 - pt.boot_rank_p2_5).median()),
            "median_rank_ci_width_all": float((boot.boot_rank_p97_5 - boot.boot_rank_p2_5).median())}
    # expected overlap of the top decile between two independent bootstrap draws (pairwise Jaccard-style overlap on 200 random pairs)
    pairs = rng.integers(0, B, (200, 2)); ov = [len(set(np.where(ranks[i] <= n_top)[0]) & set(np.where(ranks[j] <= n_top)[0])) / n_top for i, j in pairs]
    stab["mean_pairwise_top_decile_overlap"] = float(np.mean(ov))
    top_tab = boot.sort_values("point_rank").head(20)[["point_rank", "instnm", "p_top_decile", "boot_rank_p2_5", "boot_rank_p97_5"]]

    # ---------------------------------------------------------------- (b) sector models
    pooled = smf.ols(FORMULA, data=df).fit(cov_type="HC3")
    sec = {}
    for c in ["Public", "Private nonprofit"]:
        d = df[df.control_label == c].copy()
        m = smf.ols(FORMULA_SECTOR, data=d).fit(cov_type="HC3")
        d["resid_sector"] = m.resid; d["dec_sector"] = pd.qcut(d["resid_sector"], 10, labels=range(1, 11)).astype(int)
        rho = stats.spearmanr(d["residual"], d["resid_sector"]).statistic
        nt = int(round(len(d) * 0.1)); ov_s = len(set(d.nlargest(nt, "residual").unitid) & set(d.nlargest(nt, "resid_sector").unitid)) / nt
        sp = spending_table(d[d.dec_sector == 10], d[d.dec_sector == 1])
        sec[c] = {"model": m, "n": len(d), "r2": m.rsquared, "spearman_vs_pooled": rho, "top_decile_overlap_vs_pooled": ov_s, "spending": sp, "n_dec": int((d.dec_sector == 10).sum())}
    coef = pd.DataFrame({"term": [t for t in TRAITS if t != "private"],
                         "pooled": [pooled.params[t] for t in TRAITS if t != "private"],
                         "public": [sec["Public"]["model"].params[t] for t in TRAITS if t != "private"], "public_p": [sec["Public"]["model"].pvalues[t] for t in TRAITS if t != "private"],
                         "private": [sec["Private nonprofit"]["model"].params[t] for t in TRAITS if t != "private"], "private_p": [sec["Private nonprofit"]["model"].pvalues[t] for t in TRAITS if t != "private"]})

    # ---------------------------------------------------------------- (c) drop largest 5% (from the brief)
    cut = df.ugds.quantile(0.95); trimmed = df[df.ugds <= cut].copy(); tm = smf.ols(FORMULA, data=trimmed).fit(cov_type="HC3")
    rho_trim = stats.spearmanr(trimmed["residual"], tm.resid).statistic

    lines = ["# Robustness (Step 8)\n", "Generated by `src/08_robustness.py`.\n",
             f"\n## (a) Bootstrap of residual ranks: {B:,} resamples of {n:,} schools (seed {SEED})\n",
             "Each resample refits Model A and re-ranks every school. `p_top_decile` = share of resamples in which the school lands in the top 10%.\n",
             f"- Point-estimate top decile: {n_top} schools. Their mean probability of being top-decile across resamples: **{stab['mean_p_top_among_point_top']:.1%}**.",
             f"- {stab['share_p_ge_0_9']:.0%} of them are top-decile in ≥ 90% of resamples; {stab['share_p_ge_0_5']:.0%} in ≥ 50%.",
             f"- {stab['n_outside_with_p_ge_0_5']} schools outside the point-estimate top decile are top-decile in ≥ 50% of resamples (borderline cases).",
             f"- Mean overlap of the top decile between two random resamples: {stab['mean_pairwise_top_decile_overlap']:.1%}.",
             f"- Median width of the 95% rank interval: {stab['median_rank_ci_width_top_decile']:.0f} rank positions for top-decile schools, {stab['median_rank_ci_width_all']:.0f} for all schools (out of {n:,}).",
             "\nReading this: the residual is dominated by the school's own actual-minus-predicted gap, and the coefficients are estimated from 1,251 schools, so resampling the schools moves the coefficients only a little. "
             "The bootstrap therefore measures sensitivity of the ranking to *which schools define the prediction line*, not sampling noise in each school's completion rate (Scorecard publishes a point value, not a standard error). Small-cohort schools are still noisier than this interval shows.\n",
             "\nTop 20 with bootstrap rank intervals:\n", top_tab.round(3).to_markdown(index=False),
             f"\n\n## (b) Separate public and private models\n",
             f"| | Pooled | Public | Private nonprofit |\n|---|---:|---:|---:|\n| n | {int(pooled.nobs):,} | {sec['Public']['n']:,} | {sec['Private nonprofit']['n']:,} |\n| R² | {pooled.rsquared:.3f} | {sec['Public']['r2']:.3f} | {sec['Private nonprofit']['r2']:.3f} |\n"
             f"| Spearman, sector residual vs pooled residual | | {sec['Public']['spearman_vs_pooled']:.3f} | {sec['Private nonprofit']['spearman_vs_pooled']:.3f} |\n"
             f"| Top-decile overlap with pooled model (within sector) | | {sec['Public']['top_decile_overlap_vs_pooled']:.0%} | {sec['Private nonprofit']['top_decile_overlap_vs_pooled']:.0%} |\n",
             "\nCoefficients (HC3 p-values for the sector fits):\n", coef.round(4).to_markdown(index=False)]
    for c, s in sec.items():
        lines += [f"\n\n### Spending, top vs bottom decile of the {c}-only model (n = {s['n_dec']} per decile)\n", fm(s["spending"])]
    lines += [f"\n\n## (c) Drop the largest 5% of schools (undergrads > {cut:,.0f}, {n - len(trimmed)} schools)\n",
              f"Spearman between full-model and trimmed-model residuals on the remaining {len(trimmed):,} schools: {rho_trim:.3f}. Dropping 5% of a 1,251-school sample is a weak test; it is reported because the brief asked for it, and the bootstrap above is the stronger check.\n"]
    (REP / "08_robustness.md").write_text("\n".join(lines))
    results = json.loads((REP / "results.json").read_text())
    rec = lambda d: {r["category"]: {k: round(float(v), 4) for k, v in r.items() if k != "category"} for r in d.to_dict("records")}  # noqa: E731
    results["step8"] = {"bootstrap": {"B": B, "seed": SEED, **{k: round(v, 4) if isinstance(v, float) else v for k, v in stab.items()}},
                        "sector": {c: {"n": s["n"], "r2": round(s["r2"], 4), "spearman_vs_pooled": round(float(s["spearman_vs_pooled"]), 4), "top_decile_overlap_vs_pooled": round(float(s["top_decile_overlap_vs_pooled"]), 4),
                                       "n_dec": s["n_dec"], "spending": rec(s["spending"]), "coef": {t: round(float(s["model"].params[t]), 5) for t in TRAITS if t != "private"}} for c, s in sec.items()},
                        "drop5": {"ugds_cut": float(cut), "n_dropped": int(n - len(trimmed)), "spearman": round(float(rho_trim), 4)}}
    (REP / "results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(stab, indent=1)); print(coef.round(4).to_string())
    for c, s in sec.items(): print(f"\n-- {c} R2 {s['r2']:.3f} rho {s['spearman_vs_pooled']:.3f} overlap {s['top_decile_overlap_vs_pooled']:.0%}"); print(fm(s["spending"]))
    print(f"\ndrop5: cut {cut:.0f}, rho {rho_trim:.3f}")


if __name__ == "__main__":
    main()
