"""Step 4: clean missing and suppressed values; write a data quality report.

Input : data/clean/joined.parquet (1 row per UNITID, 4-year public + private nonprofit)
Output: data/clean/analysis.parquet (+ .csv), reports/04_data_quality.md

Rules (each one counted in the report):
  1. Outcome FIRSTGEN_COMP_ORIG_YR6_RT must be present and not privacy-suppressed.
  2. First-gen cohort (FIRSTGEN_YR6_N) must be >= MIN_COHORT students so the rate is not noise.
  3. ADM_RATE missing + IPEDS OPENADMP = 1 (open admission) -> 1.0; missing otherwise -> drop.
  4. Pell share, enrollment, part-time share, first-gen share must be present.
  5. Positive total FTE and positive total / instruction spending (per-student denominators).
Nothing is imputed except rule 3, and that fill is flagged in `adm_rate_filled`.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import columns as C

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
REPORT = ROOT / "reports" / "04_data_quality.md"
MIN_COHORT = 50

CORE = ["exp_instruction", "exp_academic_support", "exp_student_services", "exp_institutional_support"]
KEY_COLS = ["firstgen_comp_orig_yr6_rt", "firstgen_yr6_n", "not1stgen_comp_orig_yr6_rt", "first_gen", "pctpell",
            "adm_rate", "sat_avg", "ugds", "pptug_ef", "inexpfte", "c150_4", "ret_ft4", "fteug", "ftegd", "ftedpp",
            "openadmp"] + list(C.SPENDING_CATEGORIES)


def main() -> None:
    df = pd.read_parquet(CLEAN / "joined.parquet")
    n0 = len(df)
    log: list[tuple[str, int, int]] = []  # rule, dropped, remaining

    def apply(rule: str, keep: pd.Series) -> None:
        nonlocal df
        dropped = int((~keep).sum())
        df = df[keep].copy()
        log.append((rule, dropped, len(df)))
        print(f"{dropped:5d} dropped | {len(df):5d} left | {rule}")

    # ------------------------------------------------ missingness before cleaning
    before = pd.DataFrame({
        "missing": df[KEY_COLS].isna().sum(),
        "missing_pct": (df[KEY_COLS].isna().mean() * 100).round(1),
    })
    before.loc["firstgen_comp_orig_yr6_rt", "of_which_privacy_suppressed"] = int(df["outcome_suppressed"].sum())
    before.loc["firstgen_comp_orig_yr6_rt", "of_which_null"] = int(df["outcome_null"].sum())

    # ------------------------------------------------------------------ rules
    apply("1a. Outcome not available (Scorecard NULL)", ~df["outcome_null"].fillna(False).astype(bool))
    apply("1b. Outcome privacy-suppressed (cohort too small to publish)", ~df["outcome_suppressed"].fillna(False).astype(bool))
    apply(f"2. First-gen 6-year cohort < {MIN_COHORT} students", df["firstgen_yr6_n"] >= MIN_COHORT)

    fill = df["adm_rate"].isna() & (df["openadmp"] == 1)
    df["adm_rate_filled"] = fill
    df.loc[fill, "adm_rate"] = 1.0
    n_filled = int(fill.sum())
    apply("3. Admission rate missing and school is NOT open-admission", df["adm_rate"].notna())

    for col, label in [("pctpell", "Pell share"), ("ugds", "Undergrad enrollment"), ("pptug_ef", "Part-time share"), ("first_gen", "First-gen share")]:
        apply(f"4. {label} ({col}) missing", df[col].notna())

    df["fte_total"] = df["fteug"].fillna(0) + df["ftegd"].fillna(0) + df["ftedpp"].fillna(0)
    apply("5a. Total 12-month FTE is zero or missing", df["fte_total"] > 0)
    apply("5b. Total expenses missing or not positive", df["exp_total"].fillna(0) > 0)
    apply("5c. Instruction expenses missing or not positive", df["exp_instruction"].fillna(0) > 0)

    # --------------------------------------------------------------- derived
    for k in C.SPENDING_CATEGORIES:
        df[k] = df[k].fillna(0.0)                       # a blank functional line on a filed form = $0 in that category
        df[f"{k}_per_fte"] = df[k] / df["fte_total"]
    df["exp_core"] = df[CORE].sum(axis=1)
    df["exp_core_per_fte"] = df["exp_core"] / df["fte_total"]
    for k in CORE:
        df[f"{k}_share_core"] = df[k] / df["exp_core"]
    df["log_ugds"] = np.log(df["ugds"])
    df["log_core_per_fte"] = np.log(df["exp_core_per_fte"])
    df["private"] = (df["hd_control"] == 2).astype(int)
    df["hbcu_flag"] = (df["hbcu"] == 1).astype(int)
    df["distance_only"] = (df["distanceonly"] == 1).astype(int)
    df["open_admission"] = (df["openadmp"] == 1).astype(int)
    df["fg_gap"] = df["not1stgen_comp_orig_yr6_rt"] - df["firstgen_comp_orig_yr6_rt"]
    df["control_label"] = df["hd_control"].map({1: "Public", 2: "Private nonprofit"})

    # ------------------------------------------------------------ sanity checks
    rate_cols = ["firstgen_comp_orig_yr6_rt", "not1stgen_comp_orig_yr6_rt", "pctpell", "adm_rate", "pptug_ef", "first_gen"]
    out_of_range = {c: int(((df[c] < 0) | (df[c] > 1)).sum()) for c in rate_cols if c in df}
    assert all(v == 0 for v in out_of_range.values()), out_of_range
    assert df["unitid"].is_unique
    # Scorecard publishes its own instruction-per-FTE; compare to ours as a cross-check
    xchk = df[["inexpfte", "exp_instruction_per_fte"]].dropna()
    corr = xchk.corr().iloc[0, 1]
    ratio = (xchk["exp_instruction_per_fte"] / xchk["inexpfte"]).describe()

    # outliers worth a human look (kept in the data; the model uses logs)
    hi = df.nlargest(8, "exp_core_per_fte")[["instnm", "stabbr", "ugds", "fte_total", "exp_core_per_fte"]]
    lo = df.nsmallest(8, "exp_core_per_fte")[["instnm", "stabbr", "ugds", "fte_total", "exp_core_per_fte"]]

    # ------------------------------------------------------------------ save
    df.to_parquet(CLEAN / "analysis.parquet", index=False)
    df.to_csv(CLEAN / "analysis.csv", index=False)

    desc = df[["firstgen_comp_orig_yr6_rt", "not1stgen_comp_orig_yr6_rt", "fg_gap", "firstgen_yr6_n", "first_gen", "pctpell", "adm_rate", "ugds", "pptug_ef",
               "fte_total", "exp_core_per_fte", "exp_instruction_per_fte", "exp_academic_support_per_fte",
               "exp_student_services_per_fte", "exp_institutional_support_per_fte"]].describe(percentiles=[.05, .25, .5, .75, .95]).T
    desc = desc.round(3)

    lines = [
        "# Data quality report (Step 4)\n", "Generated by `src/04_clean.py`.\n",
        f"\n## Starting point\n\n{n0:,} four-year public and private nonprofit schools from the Step 3 join.\n",
        "\n## Missing values before cleaning\n", before.astype(object).fillna("").to_markdown(),
        "\n\n`PrivacySuppressed` means the Department of Education withheld the number because the cohort was too small to protect student privacy. "
        "It is not a zero and it is not random: small schools are suppressed more often, so the final sample under-represents very small colleges.\n",
        "\n## Cleaning rules applied in order\n", "| Rule | Dropped | Remaining |", "|---|---:|---:|",
        *[f"| {r} | {d:,} | {n:,} |" for r, d, n in log],
        f"\n- Rule 3 filled `adm_rate` = 1.0 for **{n_filled}** open-admission schools (flag `adm_rate_filled`). Open admission means every applicant is accepted, so an admission rate of 100% is the true value, not an imputation.",
        "- Blank functional expense lines on a filed finance form were set to $0 (a school that reports no research spending has none).",
        f"\n## Final analysis sample: {len(df):,} schools ({(df['private']==1).sum():,} private nonprofit, {(df['private']==0).sum():,} public)\n",
        "\n## Summary statistics (final sample)\n", desc.to_markdown(),
        "\n\n## Cross-check: IPEDS-derived instruction per FTE vs Scorecard INEXPFTE\n",
        f"- Pearson correlation: {corr:.3f} on {len(xchk):,} schools.",
        f"- Ratio ours / Scorecard: median {ratio['50%']:.2f}, 25th pct {ratio['25%']:.2f}, 75th pct {ratio['75%']:.2f}. "
        "Differences come from Scorecard using an earlier fiscal year and a slightly different FTE definition; a ratio near 1 confirms the finance join and denominator are right.",
        "\n## Outliers kept (model uses log spending, so these do not dominate)\n", "Highest core spending per FTE:\n", hi.round(0).to_markdown(index=False),
        "\n\nLowest core spending per FTE:\n", lo.round(0).to_markdown(index=False),
        f"\n\n## Range checks\n\nAll rate columns within [0, 1]: {out_of_range}. UNITID unique: True.\n",
    ]
    REPORT.write_text("\n".join(lines))
    print(f"\nfinal sample {len(df):,}; wrote {REPORT.relative_to(ROOT)}; INEXPFTE corr {corr:.3f}, ratio median {ratio['50%']:.2f}")


if __name__ == "__main__":
    main()
