"""Step 4: clean missing and suppressed values; write a data quality report (cohort-aligned version).

Input : data/clean/joined.parquet (1 row per UNITID, 4-year public + private nonprofit)
Output: data/clean/analysis.parquet (+ .csv), reports/04_data_quality.md

Model inputs are the ENTRY-YEAR (2017-18) values: pctpell, adm_rate, ugds, pptug_ef, sat_avg are copied from the
e_* columns (first_gen is the 2015-17 pooled value, the last one Scorecard published); today's values are kept as *_now for context.
Spending per FTE is the FY2018-FY2023 average (from the join); FY2023-only values are *_fy23.

Rules (each one counted in the report):
  1. Outcome FIRSTGEN_COMP_ORIG_YR6_RT must be present and not privacy-suppressed.
  2. First-gen cohort (FIRSTGEN_YR6_N) must be >= MIN_COHORT students so the rate is not noise.
  3. Entry-year ADM_RATE missing + IPEDS OPENADMP = 1 (open admission) -> 1.0; missing otherwise -> drop.
  4. Entry-year Pell share, enrollment, part-time share, first-gen share must be present.
  5. At least MIN_FIN_YEARS of the 6 fiscal years with positive FTE and positive total/instruction spending.
Nothing is imputed except rule 3, and that fill is flagged in `adm_rate_filled`.
Special-focus Carnegie schools are KEPT in the file with special_focus = 1; Step 5 models them separately.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import columns as C

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
REPORT = ROOT / "reports" / "04_data_quality.md"
MIN_COHORT = 50
MIN_FIN_YEARS = 3

CORE = ["exp_instruction", "exp_academic_support", "exp_student_services", "exp_institutional_support"]
ENTRY = {"pctpell": "e_pctpell", "adm_rate": "e_adm_rate", "ugds": "e_ugds", "pptug_ef": "e_pptug_ef", "sat_avg": "e_sat_avg"}
# first_gen is NOT remapped: the Scorecard stopped publishing it after the 2016-17 file, and the most-recent
# file carries that same value (AY2015-16 + AY2016-17 pooled cohorts), one to two years before our cohort.
CARNEGIE_GROUP = {**{k: "Doctoral" for k in (15, 16, 17)}, **{k: "Master's" for k in (18, 19, 20)}, **{k: "Baccalaureate" for k in (21, 22)},
                  **{k: "Baccalaureate/Associate's" for k in (14, 23)}, **{k: "Special focus / tribal" for k in range(24, 34)}}
KEY_COLS = ["ug_share_fte", "firstgen_comp_orig_yr6_rt", "firstgen_yr6_n", "not1stgen_comp_orig_yr6_rt", "first_gen", "e_pctpell", "e_adm_rate", "e_sat_avg", "e_ugds",
            "e_pptug_ef", "pctpell", "adm_rate", "ugds", "inexpfte", "c150_4", "openadmp", "n_fin_years", "fte_total"] + [f"{k}_per_fte" for k in C.SPENDING_CATEGORIES]


def main() -> None:
    df = pd.read_parquet(CLEAN / "joined.parquet")
    n0 = len(df)
    log: list[tuple[str, int, int]] = []

    def apply(rule: str, keep: pd.Series) -> None:
        nonlocal df
        dropped = int((~keep).sum()); df = df[keep].copy(); log.append((rule, dropped, len(df)))
        print(f"{dropped:5d} dropped | {len(df):5d} left | {rule}")

    before = pd.DataFrame({"missing": df[KEY_COLS].isna().sum(), "missing_pct": (df[KEY_COLS].isna().mean() * 100).round(1)}).astype(object)
    before.loc["firstgen_comp_orig_yr6_rt", "of_which_privacy_suppressed"] = int(df["outcome_suppressed"].sum())
    before.loc["firstgen_comp_orig_yr6_rt", "of_which_null"] = int(df["outcome_null"].sum())

    # today's values -> *_now; entry-year values -> canonical model names
    for canon, e in ENTRY.items():
        if canon in df:
            df[f"{canon}_now"] = df[canon]
        df[canon] = df[e]

    apply("1a. Outcome not available (Scorecard NA)", ~df["outcome_null"].fillna(False).astype(bool))
    apply("1b. Outcome privacy-suppressed (cohort too small to publish)", ~df["outcome_suppressed"].fillna(False).astype(bool))
    apply(f"2. First-gen 6-year cohort < {MIN_COHORT} students", df["firstgen_yr6_n"] >= MIN_COHORT)
    fill = df["adm_rate"].isna() & (df["openadmp"] == 1)
    df["adm_rate_filled"] = fill; df.loc[fill, "adm_rate"] = 1.0; n_filled = int(fill.sum())
    apply("3. Entry-year admission rate missing and school is NOT open-admission", df["adm_rate"].notna())
    for col, label in [("pctpell", "Pell share (2017-18)"), ("ugds", "Undergrad enrollment (Fall 2017)"), ("pptug_ef", "Part-time share (Fall 2017)"), ("first_gen", "First-gen share (2015-17 pooled cohorts)")]:
        apply(f"4. {label} missing", df[col].notna())
    apply(f"5. Fewer than {MIN_FIN_YEARS} fiscal years of usable finance + FTE data", df["n_fin_years"] >= MIN_FIN_YEARS)

    # ---------------------------------------------------------------- derived
    for k in C.SPENDING_CATEGORIES:
        for suffix in ["", "_fy23", "_fy1819", "_real"]:
            df[f"{k}_per_fte{suffix}"] = df[f"{k}_per_fte{suffix}"].fillna(0.0)   # blank functional line on a filed form = $0
    for suffix in ["", "_fy23", "_fy1819", "_real"]:
        df[f"exp_core_per_fte{suffix}"] = df[[f"{k}_per_fte{suffix}" for k in CORE]].sum(axis=1)
        for k in CORE:
            df[f"{k}_share_core{suffix}"] = df[f"{k}_per_fte{suffix}"] / df[f"exp_core_per_fte{suffix}"]
    df["log_ugds"] = np.log(df["ugds"])
    df["log_core_per_fte"] = np.log(df["exp_core_per_fte"])
    df["private"] = (df["hd_control"] == 2).astype(int)
    df["hbcu_flag"] = (df["hbcu"] == 1).astype(int)
    df["distance_only"] = (df["distanceonly"] == 1).astype(int)
    df["open_admission"] = (df["openadmp"] == 1).astype(int)
    df["fg_gap"] = df["not1stgen_comp_orig_yr6_rt"] - df["firstgen_comp_orig_yr6_rt"]
    df["control_label"] = df["hd_control"].map({1: "Public", 2: "Private nonprofit"})
    df["carnegie_group"] = df["hd_c18basic"].map(CARNEGIE_GROUP).fillna("Other")
    df["special_focus"] = (df["carnegie_group"] == "Special focus / tribal").astype(int)
    assert (df["carnegie_group"] != "Other").all(), df.loc[df.carnegie_group == "Other", "hd_c18basic"].unique()

    rate_cols = ["firstgen_comp_orig_yr6_rt", "not1stgen_comp_orig_yr6_rt", "pctpell", "adm_rate", "pptug_ef", "first_gen"]
    out_of_range = {c: int(((df[c] < 0) | (df[c] > 1)).sum()) for c in rate_cols}
    assert all(v == 0 for v in out_of_range.values()), out_of_range
    assert df["unitid"].is_unique
    xchk = df[["inexpfte", "exp_instruction_per_fte_fy23"]].dropna()
    corr = xchk.corr().iloc[0, 1]; ratio = (xchk["exp_instruction_per_fte_fy23"] / xchk["inexpfte"]).describe()
    drift = pd.DataFrame({"entry_2017": df[["pctpell", "adm_rate", "ugds"]].median(), "now_2024": df[["pctpell_now", "adm_rate_now", "ugds_now"]].median().values,
                          "corr_entry_now": [df["pctpell"].corr(df["pctpell_now"]), df["adm_rate"].corr(df["adm_rate_now"]), df["ugds"].corr(df["ugds_now"])]}).round(3)
    spend_drift = pd.DataFrame({"window_avg_FY18_23": df[[f"{k}_per_fte" for k in CORE]].median().values, "FY2023_only": df[[f"{k}_per_fte_fy23" for k in CORE]].median().values,
                                "corr": [df[f"{k}_per_fte"].corr(df[f"{k}_per_fte_fy23"]) for k in CORE]}, index=CORE).round(3)
    hi = df.nlargest(6, "exp_core_per_fte")[["instnm", "stabbr", "ugds", "fte_total", "exp_core_per_fte"]]
    lo = df.nsmallest(6, "exp_core_per_fte")[["instnm", "stabbr", "ugds", "fte_total", "exp_core_per_fte"]]
    carn = df.groupby(["carnegie_group", "control_label"]).size().unstack(fill_value=0)

    df.to_parquet(CLEAN / "analysis.parquet", index=False); df.to_csv(CLEAN / "analysis.csv", index=False)
    desc = df[["firstgen_comp_orig_yr6_rt", "not1stgen_comp_orig_yr6_rt", "fg_gap", "firstgen_yr6_n", "first_gen", "pctpell", "adm_rate", "ugds", "pptug_ef", "fte_total",
               "exp_core_per_fte", "exp_instruction_per_fte", "exp_academic_support_per_fte", "exp_student_services_per_fte", "exp_institutional_support_per_fte"]].describe(percentiles=[.05, .25, .5, .75, .95]).T.round(3)
    main_n, sf_n = int((df.special_focus == 0).sum()), int((df.special_focus == 1).sum())
    lines = ["# Data quality report (Step 4)\n", "Generated by `src/04_clean.py`.\n",
             f"\n## Starting point\n\n{n0:,} four-year public and private nonprofit schools from the Step 3 join.\n",
             "\n## Missing values before cleaning (e_* = entry-year 2017-18 values used in the model)\n", before.astype(object).fillna("").to_markdown(),
             "\n\n`PS` (PrivacySuppressed) means the Department of Education withheld the number because the cohort was too small to protect student privacy. "
             "It is not a zero and it is not random: small schools are suppressed more often, so the final sample under-represents very small colleges.\n",
             "\n## Cleaning rules applied in order\n", "| Rule | Dropped | Remaining |", "|---|---:|---:|", *[f"| {r} | {d:,} | {n:,} |" for r, d, n in log],
             f"\n- Rule 3 filled `adm_rate` = 1.0 for **{n_filled}** open-admission schools (flag `adm_rate_filled`). Open admission means every applicant is accepted, so 100% is the true value, not an imputation.",
             "- Blank functional expense lines on a filed finance form were set to $0.",
             f"\n## Final file: {len(df):,} schools = {main_n:,} in the main sample + {sf_n:,} special-focus / tribal (Carnegie 2018 codes 24-33), modeled separately\n",
             carn.to_markdown(),
             "\n\n## Timing: entry-year vs today's predictor values (medians and correlations)\n", drift.to_markdown(),
             "\n\nPell share and enrollment are stable school traits (high correlation), but the 2024 values describe students who entered seven years after the cohort, so the model uses the 2017-18 values.\n",
             "\n## Timing: window-average vs FY2023-only spending per FTE (medians)\n", spend_drift.to_markdown(),
             "\n\n## Summary statistics (final file)\n", desc.to_markdown(),
             "\n\n## Cross-check: IPEDS-derived FY2023 instruction per FTE vs Scorecard INEXPFTE (FY2024 in this release)\n",
             f"- Pearson correlation: {corr:.3f} on {len(xchk):,} schools; ratio ours/Scorecard median {ratio['50%']:.2f} (IQR {ratio['25%']:.2f}-{ratio['75%']:.2f}). Adjacent fiscal years, so a ratio near 1 and a high correlation confirm the finance join and FTE denominator.\n",
             "\n## Outliers kept (the model uses log spending)\n", "Highest core spending per FTE:\n", hi.round(0).to_markdown(index=False), "\n\nLowest:\n", lo.round(0).to_markdown(index=False),
             f"\n\n## Range checks\n\nAll rate columns within [0, 1]: {out_of_range}. UNITID unique: True.\n"]
    REPORT.write_text("\n".join(lines))
    print(f"\nfinal {len(df):,} (main {main_n:,}, special focus {sf_n:,}); INEXPFTE corr {corr:.3f}; wrote {REPORT.relative_to(ROOT)}")
    print(drift.to_string()); print(spend_drift.to_string()); print(carn.to_string())


if __name__ == "__main__":
    main()
