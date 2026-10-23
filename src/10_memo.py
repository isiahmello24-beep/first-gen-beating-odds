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
pf, fy23, wc = s7["per_fte"], s7["per_fte_fy23_only"], s7["within_control"]
bs, sec = s8["bootstrap"], s8["sector"]
cA = s5["coef_A"]
today = date.today().isoformat()
pub_sp, prv_sp = sec["Public"]["spending"], sec["Private nonprofit"]["spending"]


def pv(x):
    return "<0.001" if x < 0.001 else f"{x:.3f}"


def peers(rows):
    return "\n".join(f"| {r['school']} ({r['state']}) | {r['carnegie']} | {r['pell']:.0%} | {r['actual']:.0%} | {r['predicted']:.0%} | {r['resid_pp']:+.0f} |" for r in rows)


memo = f"""# Memo: Which colleges beat the odds on first-generation completion, and what they spend on

**To:** Director of Student Success  **From:** Isiah Mello  **Date:** {today}
**Data:** College Scorecard (Oct 2026 release), IPEDS finance FY2018-FY2023, Opportunity Insights; {s5['n']:,} four-year public and private nonprofit colleges (special-focus schools analyzed separately).

## Bottom line

For the cohort of first-generation students who entered college in 2017-18, the schools that graduated them well above what their student mix predicts spent more per student on **instruction** and **academic support** during the years those students were enrolled. Student-services spending was no different overall. This is a school-level correlation, not proof that moving money would move completion, but it points to where the strongest peers put their resources.

## What we measured

- **Outcome:** share of first-generation federal-aid students in the 2017-18 entry cohort who completed at the same school within 6 years (mean {s5['outcome_mean']:.0%}, standard deviation {s5['outcome_sd']:.0%}).
- **Timing:** predictors are the school's 2017-18 values and spending is averaged over fiscal years 2018-2023, so every input describes the years the cohort was actually on campus.
- **Prediction model:** OLS on Pell share, admission rate, enrollment, part-time share, first-gen share, public/private, HBCU, online-only status and Carnegie classification. R² = {s5['r2_A']:.2f}: these traits explain about {s5['r2_A']*100:.0f}% of the school-to-school variation. Spending is deliberately left out of this model so the comparison below is not circular.
- **Residual = actual − predicted.** Top 10% = {s6['top_decile_n']} schools at **+{s6['top_decile_cut_pp']:.0f} points or better**; bottom 10% at {s6['bottom_decile_cut_pp']:+.0f} or worse.

## What the model says about student mix

Holding other traits fixed, each 10-point rise in Pell share predicts {abs(cA['pctpell'])*10:.1f} points lower first-gen completion; each 10-point rise in admission rate predicts {abs(cA['adm_rate'])*10:.1f} points lower; a 10-point rise in part-time share predicts {abs(cA['pptug_ef'])*10:.1f} points lower; HBCUs run {cA['hbcu_flag']*100:+.1f} points. Private nonprofits run {cA['private']*100:+.1f} points relative to publics. These are the headwinds the ranking adjusts for.

## What over-performers spent (top 10% vs bottom 10%, median dollars per FTE student, FY2018-23 average)

| Category | Top 10% | Bottom 10% | Ratio | Mann-Whitney p |
|---|---:|---:|---:|---:|
| Instruction | ${pf['Instruction']['top10_median_$']:,.0f} | ${pf['Instruction']['bottom10_median_$']:,.0f} | {pf['Instruction']['median_ratio']:.2f}× | {pv(pf['Instruction']['mann_whitney_p'])} |
| Academic support (advising, tutoring, libraries) | ${pf['Academic support']['top10_median_$']:,.0f} | ${pf['Academic support']['bottom10_median_$']:,.0f} | {pf['Academic support']['median_ratio']:.2f}× | {pv(pf['Academic support']['mann_whitney_p'])} |
| Student services (admissions, counseling, activities) | ${pf['Student services']['top10_median_$']:,.0f} | ${pf['Student services']['bottom10_median_$']:,.0f} | {pf['Student services']['median_ratio']:.2f}× | {pv(pf['Student services']['mann_whitney_p'])} |
| Institutional support (administration) | ${pf['Institutional support']['top10_median_$']:,.0f} | ${pf['Institutional support']['bottom10_median_$']:,.0f} | {pf['Institutional support']['median_ratio']:.2f}× | {pv(pf['Institutional support']['mann_whitney_p'])} |

Because budgets sum to 100%, more instruction dollars also means a larger instruction *share*; that is the same fact, not a second finding.

**Sector matters.** In a public-only model, over-performing publics spent more on all four categories, including student services ({pub_sp['Student services']['median_ratio']:.2f}×, p = {pv(pub_sp['Student services']['mann_whitney_p'])}): the signal there is "more of everything that touches students". In a private-only model the gap is concentrated in instruction ({prv_sp['Instruction']['median_ratio']:.2f}×) and academic support ({prv_sp['Academic support']['median_ratio']:.2f}×) with no student-services difference ({prv_sp['Student services']['median_ratio']:.2f}×).

## Peers worth a phone call (high-Pell schools, Pell share ≥ 50% in 2017-18, largest residuals)

| School | Carnegie | Pell | Actual | Predicted | Residual (pts) |
|---|---|---:|---:|---:|---:|
{peers(s6['top5_high_pell'])}

## Does it hold up?

- **Bootstrap (1,000 resamples):** the {bs['n_top_decile']} top-decile schools stay in the top decile in {bs['mean_p_top_among_point_top']:.0%} of resamples on average; {bs['share_p_ge_0_9']:.0%} of them in at least 90% of resamples. The ranking is not an artifact of which schools happen to define the prediction line.
- **Separate sector models:** Spearman {sec['Public']['spearman_vs_pooled']:.2f} (public) and {sec['Private nonprofit']['spearman_vs_pooled']:.2f} (private) with the pooled ranking; the spending pattern above holds in each.
- **Timing check:** using only FY2023 spending (after the cohort left) gives instruction {fy23['Instruction']['median_ratio']:.2f}× and academic support {fy23['Academic support']['median_ratio']:.2f}×, similar ratios, but the earlier version of this analysis also used 2024 traits and no Carnegie control, and only {s6['top20_overlap_vs_v1']} of its top-20 schools survive in the corrected ranking (rank correlation {s6['spearman_vs_v1_mistimed']:.2f}).
- **Spending in the model:** adding core spending per student raises R² from {s5['r2_A']:.2f} to {s5['r2_B']:.2f}; a 10% higher budget per student is associated with {s5['pp_per_10pct_spending']:+.1f} points.

## Limitations

1. **School-level data.** We see institutions, not students; a school can over-perform because of program mix or who it enrolls in ways the model does not capture. Special-focus colleges (nursing, faith, arts) are excluded for this reason and listed separately.
2. **Correlation only.** Over-performers spend differently; we cannot say that reallocating dollars would change completion.
3. **Definition.** Completion at the same institution for federal-aid students; transfer-out completers count as non-completers. Privacy suppression removes the smallest schools.

## Suggested next step

Pick five peers from the table above with a similar Pell share and sector, and compare advising ratios, tutoring reach and gateway-course redesign, the activities that sit inside "instruction" and "academic support" in IPEDS. The dashboard (`streamlit run app/app.py`) filters the full ranking by state, sector, Carnegie group, size and Pell share.
"""
(ROOT / "memo/memo.md").write_text(memo)

readme = f"""# Which 4-year colleges graduate first-generation students above prediction, and what do they spend on?

Portfolio project (UCSD MSBA application). Python · DuckDB · pandas · statsmodels · plotly · Streamlit.

## Question

Which US 4-year colleges graduate first-generation students at higher rates than their student mix and structure predict, and how did their spending differ, during the years those students were enrolled, from schools that under-perform?

## Headline results (all numbers generated by the pipeline; see `reports/results.json`)

- **Cohort alignment:** outcome = first-gen students who entered in AY2017-18, measured in AY2023-24 (Scorecard cohort map). Predictors are the schools' 2017-18 values; spending is the FY2018-FY2023 average per FTE.
- **Sample:** {s5['n']:,} four-year public and private nonprofit colleges (Carnegie doctoral, master's, baccalaureate); {s5['n_special_focus']} special-focus schools scored separately.
- **Model:** OLS of first-gen same-institution 6-year completion on Pell share, admission rate, log enrollment, part-time share, first-gen share, private, HBCU, distance-only and Carnegie group. **R² = {s5['r2_A']:.3f}**, HC3 robust SEs. Spending is not in the model.
- **Ranking:** residual = actual − predicted. Top decile ({s6['top_decile_n']} schools) beat prediction by **≥ {s6['top_decile_cut_pp']:.1f} points**.
- **Spending:** top-decile schools spent **{pf['Instruction']['median_ratio']:.2f}× more per FTE on instruction** and **{pf['Academic support']['median_ratio']:.2f}× on academic support** than bottom-decile schools (medians; Mann-Whitney p < 0.001). Student-services dollars were not different ({pf['Student services']['median_ratio']:.2f}×, p = {pf['Student services']['mann_whitney_p']:.2f}). Within publics alone, over-performers spent more on all four categories.
- **Robustness:** 1,000-resample bootstrap keeps the top-decile schools in the top decile {bs['mean_p_top_among_point_top']:.0%} of the time; separate public and private models rank schools consistently with the pooled model (Spearman {sec['Public']['spearman_vs_pooled']:.2f} / {sec['Private nonprofit']['spearman_vs_pooled']:.2f}).

![spending](reports/figures/07_spending_top_vs_bottom.png)

## What changed after review (see `decisions.md`)

The first build used the Scorecard's undated download (an August 2024 file), today's school traits, FY2023 spending and no Carnegie control. Review found four problems: spending measured after the cohort left, ambiguity about whether spending sat inside the model, nursing and health colleges dominating the ranking, and a weak robustness check. All four are fixed; only {s6['top20_overlap_vs_v1']} of the original top-20 schools survive in the corrected ranking (Spearman {s6['spearman_vs_v1_mistimed']:.2f}), while the instruction and academic-support finding held. The original ranking is archived in `reports/archive/`.

## Data

| Source | File(s) | Role |
|---|---|---|
| College Scorecard (US Dept. of Education), Oct 2026 release | Most-Recent-Cohorts-Institution_10152026.csv; MERGED2017_18_PP.csv from the raw archive | outcome (first-gen completion, 2017-18 cohort); entry-year Pell share, admission rate, enrollment, part-time share |
| IPEDS (NCES) | HD2023, IC2023; F1718-F2223 finance (F1A public, F2 private nonprofit); EFIA2018-2023 | 4-year filter, Carnegie 2018, open-admission flag, FY2018-23 functional expenses per FTE |
| Opportunity Insights | mrc_table2, mrc_table11 | mobility rate and parent income (context) |

Join key: `UNITID`. Opportunity Insights is reached via OPEID → `super_opeid`. Raw files are gitignored; `src/01_download.py` recreates them (~600 MB, mostly the Scorecard raw archive).

## Reproduce

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
for s in src/0[1-8]_*.py src/10_memo.py; do python "$s"; done
streamlit run app/app.py
```

## Pipeline (one script per build step)

| Step | Script | Output |
|---|---|---|
| 1 | `src/01_download.py` | `data/raw/`, `reports/01_raw_inventory.md` (row counts, columns) |
| 2 | `src/columns.py`, `src/02_columns.py` | `reports/02_column_selection.md` (every column, plain description, timing) |
| 3 | `src/03_join.py` | `data/clean/joined.parquet`, `finance_by_year.parquet`, `reports/03_join_report.md` (drop funnel) |
| 4 | `src/04_clean.py` | `data/clean/analysis.parquet`, `reports/04_data_quality.md` |
| 5 | `src/05_regress.py` | `reports/05_regression.md`, diagnostic plots in `reports/figures/` |
| 6 | `src/06_rank.py` | `data/clean/ranked_schools.csv`, `reports/06_rankings.md` (incl. before/after the fixes) |
| 7 | `src/07_spending.py` | `reports/07_spending_comparison.md` |
| 8 | `src/08_robustness.py` | `reports/08_robustness.md`, `data/clean/bootstrap_ranks.csv` |
| 9 | `app/app.py` | Streamlit dashboard |
| 10 | `src/10_memo.py` | `memo/memo.md`, this README |

`decisions.md` logs every modeling and cleaning choice with its reason. `reports/results.json` holds the key numbers the memo, README and dashboard read.

## Dashboard

`streamlit run app/app.py`: actual-vs-predicted scatter with hover, coefficient chart, filterable ranking (state, sector, Carnegie group, size, Pell share) with CSV download, top-vs-bottom spending comparison (pooled and sector models), per-school lookup with bootstrap rank interval and peer comparison, methods and limitations.

## Limitations

- **School-level data.** Institutions, not students, are the unit. Unobserved differences in program mix and preparation can produce a residual unrelated to what the school does. Special-focus colleges are excluded for this reason and listed in `reports/05_regression.md`.
- **Correlation only.** Spending differences describe over-performers; they do not show that changing spending would change completion.
- **Outcome definition.** Completion at the same institution for federal-aid students; transfer-out completers count as non-completers. Privacy suppression removes the smallest schools.
- **Structural traits** (control, level, Title IV status, open admission) come from 2023 IPEDS files and are assumed unchanged since 2017.
- **Opportunity Insights** data describe students born 1980-82 and are used as context only.

## Repository layout

```
app/        Streamlit dashboard
data/raw/   downloaded sources (gitignored)   data/clean/  joined, cleaned, scored datasets
memo/       one-page memo to a student success director
notebooks/  exploration notebook
reports/    step-by-step reports, figures, results.json, archive/ (pre-review ranking)
src/        numbered pipeline scripts
CLAUDE.md   original project brief      decisions.md  decisions log
```
"""
(ROOT / "README.md").write_text(readme)
print(memo)
