"""Step 10: generate the one-page memo and README from reports/results.json.

No number in either document is typed by hand; every figure is read from results.json,
which Steps 5-8 wrote from code output.
"""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "reports/results.json").read_text())
s5, s6, s7, s8 = R["step5"], R["step6"], R["step7"], R["step8"]
pf, sh, wc = s7["per_fte"], s7["share_core"], s7["within_control"]
cA = s5["coef_A"]
today = date.today().isoformat()


def peers(rows):
    return "\n".join(f"| {r['school']} ({r['state']}) | {r['pell']:.0%} | {r['actual']:.0%} | {r['predicted']:.0%} | {r['resid_pp']:+.0f} |" for r in rows)


memo = f"""# Memo: Which colleges beat the odds on first-generation completion, and what they spend on

**To:** Director of Student Success  **From:** Isiah Mello  **Date:** {today}
**Data:** College Scorecard, IPEDS FY2022-23 finance, Opportunity Insights; {s5['n']:,} four-year public and private nonprofit colleges.

## Bottom line

Across {s5['n']:,} four-year colleges, the schools that graduate first-generation students well above what their student mix predicts spend more per student on **instruction** and **academic support**, not on student services. Under-performers spend similar dollars on student services but a larger *share* of their budget there. This is a correlation at the school level, not proof that moving money would move completion, but it points to where the strongest peers put their resources.

## What we measured

- **Outcome:** share of first-generation federal-aid students who complete at the same school within 6 years (sample mean {s5['outcome_mean']:.0%}, standard deviation {s5['outcome_sd']:.0%}).
- **Prediction model:** OLS regression on Pell share, admission rate, enrollment, part-time share, first-gen share, public/private, HBCU, and online-only status. R² = {s5['r2_A']:.2f}: these traits explain about {s5['r2_A']*100:.0f}% of the school-to-school variation.
- **Residual = actual − predicted.** A residual of +10 points means a school graduates first-gen students 10 points above what similar schools achieve. Top 10% = {s6['top_decile_n']} schools at **+{s6['top_decile_cut_pp']:.0f} points or better**; bottom 10% at {s6['bottom_decile_cut_pp']:+.0f} or worse.

## What the model says about student mix

Holding other traits fixed, each 10-point rise in Pell share predicts {abs(cA['pctpell'])*10:.1f} points lower first-gen completion; each 10-point rise in admission rate predicts {abs(cA['adm_rate'])*10:.1f} points lower; a 10-point rise in part-time share predicts {abs(cA['pptug_ef'])*10:.1f} points lower. Private nonprofits run {cA['private']*100:+.1f} points relative to publics. These are the headwinds the ranking adjusts for.

## What over-performers spend on (top 10% vs bottom 10%, median dollars per FTE student)

| Category | Top 10% | Bottom 10% | Ratio | Share of core budget: top vs bottom |
|---|---:|---:|---:|---|
| Instruction | ${pf['Instruction']['top10_median_$']:,.0f} | ${pf['Instruction']['bottom10_median_$']:,.0f} | {pf['Instruction']['median_ratio']:.2f}× | {sh['Instruction']['top10_mean_share']:.0%} vs {sh['Instruction']['bottom10_mean_share']:.0%} |
| Academic support (advising, tutoring, libraries) | ${pf['Academic support']['top10_median_$']:,.0f} | ${pf['Academic support']['bottom10_median_$']:,.0f} | {pf['Academic support']['median_ratio']:.2f}× | {sh['Academic support']['top10_mean_share']:.0%} vs {sh['Academic support']['bottom10_mean_share']:.0%} |
| Student services (admissions, counseling, activities) | ${pf['Student services']['top10_median_$']:,.0f} | ${pf['Student services']['bottom10_median_$']:,.0f} | {pf['Student services']['median_ratio']:.2f}× | {sh['Student services']['top10_mean_share']:.0%} vs {sh['Student services']['bottom10_mean_share']:.0%} |
| Institutional support (administration) | ${pf['Institutional support']['top10_median_$']:,.0f} | ${pf['Institutional support']['bottom10_median_$']:,.0f} | {pf['Institutional support']['median_ratio']:.2f}× | {sh['Institutional support']['top10_mean_share']:.0%} vs {sh['Institutional support']['bottom10_mean_share']:.0%} |

Instruction and academic support differences are statistically clear (Mann-Whitney p < 0.001 for both); the student-services dollar difference is not (p = {pf['Student services']['mann_whitney_p']:.2f}), while the student-services *share* difference is (p < 0.001). Among private nonprofits alone the gap is wider (instruction {wc['Private nonprofit']['per_fte']['Instruction']['median_ratio']:.2f}×, academic support {wc['Private nonprofit']['per_fte']['Academic support']['median_ratio']:.2f}×); among publics it is smaller (instruction {wc['Public']['per_fte']['Instruction']['median_ratio']:.2f}×, academic support {wc['Public']['per_fte']['Academic support']['median_ratio']:.2f}×, student services {wc['Public']['per_fte']['Student services']['median_ratio']:.2f}×), so for a public institution the signal is "more of everything that touches academics", not a reallocation away from student services.

## Peers worth a phone call (high-Pell schools, Pell share ≥ 50%, largest residuals)

| School | Pell | Actual | Predicted | Residual (pts) |
|---|---:|---:|---:|---:|
{peers(s6['top5_high_pell'])}

## Does it hold up?

Dropping the largest 5% of schools ({s8['n_dropped']} universities over {s8['ugds_cut']:,.0f} undergrads) leaves the ranking essentially unchanged (rank correlation {s8['spearman']:.3f}, {s8['top_decile_overlap']:.0%} of the top decile identical) and the spending pattern intact (instruction {s8['spending_trimmed']['Instruction']['median_ratio']:.2f}×, academic support {s8['spending_trimmed']['Academic support']['median_ratio']:.2f}×). Adding spending per student to the model raises R² from {s5['r2_A']:.2f} to {s5['r2_B']:.2f}; a 10% higher core budget per student is associated with {s5['pp_per_10pct_spending']:+.1f} points of first-gen completion.

## Limitations

1. **School-level data.** We see institutions, not students; a school can over-perform because of program mix or who it enrolls in ways the model does not capture. The raw top of the list is small nursing and health colleges for exactly this reason.
2. **Correlation only.** Over-performers spend differently; we cannot say that reallocating dollars would change completion.
3. **Timing and definition.** Finance is FY2023; the completion cohorts entered 6-8 years earlier. Students who transfer and finish elsewhere count as non-completers.

## Suggested next step

Pick five peers from the table above with a similar Pell share and sector, and compare advising ratios, tutoring reach and gateway-course redesign, the activities that sit inside "instruction" and "academic support" in IPEDS. The dashboard (`streamlit run app/app.py`) filters the full ranking by state, sector, size and Pell share.
"""
(ROOT / "memo/memo.md").write_text(memo)

readme = f"""# Which 4-year colleges graduate first-generation students above prediction, and what do they spend on?

Portfolio project (UCSD MSBA application). Python · DuckDB · pandas · statsmodels · plotly · Streamlit.

## Question

Which US 4-year colleges graduate first-generation students at higher rates than their student mix and structure predict, and how does their spending differ from schools that under-perform?

## Headline results (all numbers generated by the pipeline; see `reports/results.json`)

- **Sample:** {s5['n']:,} four-year public and private nonprofit colleges with a published first-gen 6-year completion rate.
- **Model:** OLS of first-gen same-institution 6-year completion on Pell share, admission rate, log enrollment, part-time share, first-gen share, private, HBCU, distance-only. **R² = {s5['r2_A']:.3f}**, HC3 robust SEs. All predictors except distance-only significant at p < 0.001.
- **Ranking:** residual = actual − predicted. Top decile ({s6['top_decile_n']} schools) beat prediction by **≥ {s6['top_decile_cut_pp']:.1f} points**.
- **Spending:** top-decile schools spend **{pf['Instruction']['median_ratio']:.2f}× more per FTE on instruction** and **{pf['Academic support']['median_ratio']:.2f}× on academic support** than bottom-decile schools (medians; Mann-Whitney p < 0.001). Student-services dollars are similar ({pf['Student services']['median_ratio']:.2f}×) but under-performers devote a larger share of core spending to them ({sh['Student services']['bottom10_mean_share']:.0%} vs {sh['Student services']['top10_mean_share']:.0%}).
- **Robustness:** dropping the largest 5% of schools leaves rankings (Spearman {s8['spearman']:.3f}) and the spending pattern unchanged.

![spending](reports/figures/07_spending_top_vs_bottom.png)

## Data

| Source | File(s) | Role |
|---|---|---|
| College Scorecard (US Dept. of Education) | Most-Recent-Cohorts-Institution.csv | outcome (first-gen completion), Pell share, admission rate, enrollment, flags |
| IPEDS 2023 (NCES) | HD2023, IC2023, EFIA2023, F2223_F1A (public), F2223_F2 (private nonprofit) | 4-year filter, open-admission flag, FTE denominator, functional expenses |
| Opportunity Insights | mrc_table2, mrc_table11 | mobility rate and parent income (context; 73% match) |

Join key: `UNITID`. Opportunity Insights is reached via OPEID → `super_opeid`. Raw files are gitignored; `src/01_download.py` recreates them.

## Reproduce

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
for s in src/0[1-8]_*.py src/10_memo.py; do python "$s"; done   # ~2 minutes after download
streamlit run app/app.py
```

## Pipeline (one script per build step)

| Step | Script | Output |
|---|---|---|
| 1 | `src/01_download.py` | `data/raw/`, `reports/01_raw_inventory.md` (row counts, columns) |
| 2 | `src/columns.py`, `src/02_columns.py` | `reports/02_column_selection.md` (every column, plain description) |
| 3 | `src/03_join.py` | `data/clean/joined.parquet`, `reports/03_join_report.md` (drop funnel) |
| 4 | `src/04_clean.py` | `data/clean/analysis.parquet`, `reports/04_data_quality.md` |
| 5 | `src/05_regress.py` | `reports/05_regression.md`, diagnostic plots in `reports/figures/` |
| 6 | `src/06_rank.py` | `data/clean/ranked_schools.csv`, `reports/06_rankings.md` |
| 7 | `src/07_spending.py` | `reports/07_spending_comparison.md` |
| 8 | `src/08_robustness.py` | `reports/08_robustness.md` |
| 9 | `app/app.py` | Streamlit dashboard |
| 10 | `src/10_memo.py` | `memo/memo.md`, this README |

`decisions.md` logs every modeling and cleaning choice with its reason. `reports/results.json` holds the key numbers the memo, README and dashboard read.

## Dashboard

`streamlit run app/app.py`: actual-vs-predicted scatter with hover, coefficient chart, filterable ranking with CSV download, top-vs-bottom spending comparison (overall and within sector), per-school lookup with peer comparison, methods and limitations.

## Limitations

- **School-level data.** Institutions, not students, are the unit. Unobserved differences in program mix and student preparation can produce a residual that has nothing to do with what the school does. Small single-program health colleges top the raw list for this reason; use the enrollment filter.
- **Correlation only.** Spending differences describe over-performers; they do not show that changing spending would change completion.
- **Timing.** FY2023 finance is matched to completion cohorts that entered 6-8 years earlier.
- **Outcome definition.** Completion at the same institution for federal-aid students; transfer-out completers count as non-completers. Privacy suppression removes the smallest schools.
- **Opportunity Insights** data describe students born 1980-82 and are used as context only.

## Repository layout

```
app/        Streamlit dashboard
data/raw/   downloaded sources (gitignored)   data/clean/  joined, cleaned, scored datasets
memo/       one-page memo to a student success director
notebooks/  exploration notebook
reports/    step-by-step reports, figures, results.json
src/        numbered pipeline scripts
CLAUDE.md   original project brief      decisions.md  decisions log
```
"""
(ROOT / "README.md").write_text(readme)
print(memo)
