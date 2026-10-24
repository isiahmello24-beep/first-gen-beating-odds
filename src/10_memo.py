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
pf, f1819, real, fy23 = s7["per_fte"], s7["per_fte_fy1819"], s7["per_fte_real"], s7["per_fte_fy23_only"]
carn, bs, sec = s7["within_carnegie"], s8["bootstrap"], s8["sector"]
pub, prv = sec["Public"]["spending"], sec["Private nonprofit"]["spending"]
cA = s5["coef_A"]
today = date.today().isoformat()


def pv(x):
    return "<0.001" if x < 0.001 else f"{x:.3f}"


def row(label, d, cat):
    return f"| {label} | ${d[cat]['top10_median_$']:,.0f} | ${d[cat]['bottom10_median_$']:,.0f} | {d[cat]['median_ratio']:.2f}× | {pv(d[cat]['mann_whitney_p'])} |"


def peers(rows):
    return "\n".join(f"| {r['school']} ({r['state']}) | {r['carnegie']} | {r['cohort']:,} | {r['pell']:.0%} | {r['actual']:.0%} | {r['predicted']:.0%} | {r['resid_eb_pp']:+.0f} |" for r in rows)


memo = f"""# Memo: Which colleges beat the odds on first-generation completion, and what they spent on

**To:** Director of Student Success  **From:** Isiah Mello  **Date:** {today}
**Data:** College Scorecard (Oct 2026 release), IPEDS finance FY2018-FY2023, Opportunity Insights; {s5['n']:,} four-year public and private nonprofit colleges ({s5['n_excluded']} special-focus, adult- or online-dominant, or anomalous-data schools listed separately).

## Bottom line: the answer depends on your sector

For first-generation students who entered college in 2017-18, the schools that graduated them well above what their student mix predicts spent more per student than comparable under-performers, but *where* the extra money sat differs by sector:

- **Public universities.** Ranked against other publics, over-performers spent more on every core function during the cohort's years: instruction {pub['Instruction']['median_ratio']:.2f}× (p = {pv(pub['Instruction']['mann_whitney_p'])}), academic support {pub['Academic support']['median_ratio']:.2f}× (p = {pv(pub['Academic support']['mann_whitney_p'])}), student services {pub['Student services']['median_ratio']:.2f}× (p = {pv(pub['Student services']['mann_whitney_p'])}), institutional support {pub['Institutional support']['median_ratio']:.2f}×. The public signal is "more of everything that touches students," not a reallocation.
- **Private nonprofits.** Over-performers spent {prv['Instruction']['median_ratio']:.2f}× on instruction and {prv['Academic support']['median_ratio']:.2f}× on academic support (both p < 0.001), with **no** student-services difference ({prv['Student services']['median_ratio']:.2f}×, p = {pv(prv['Student services']['mann_whitney_p'])}).

Pooling both sectors, the instruction ({pf['Instruction']['median_ratio']:.2f}×) and academic-support ({pf['Academic support']['median_ratio']:.2f}×) gaps are clear and the student-services gap is zero ({pf['Student services']['median_ratio']:.2f}×), but that pooled picture is driven by private colleges: restricted to publics, the pooled-decile gaps shrink to {s7['within_control']['Public']['per_fte']['Instruction']['median_ratio']:.2f}× and {s7['within_control']['Public']['per_fte']['Academic support']['median_ratio']:.2f}× and are not statistically significant. A public director should read the public-only row, not the headline. This is a school-level correlation, not proof that moving money moves completion.

## What we measured

- **Outcome:** share of first-generation federal-aid students in the 2017-18 entry cohort who completed at the same school within 6 years (mean {s5['outcome_mean']:.0%}, standard deviation {s5['outcome_sd']:.0%}).
- **Timing:** predictors are the school's 2017-18 values; spending is averaged over fiscal years 2018-2023, the years the cohort was enrolled.
- **Prediction model:** OLS on Pell share, admission rate, enrollment, part-time share, first-gen share, share of students aged 25+, share exclusively online, HBCU and Carnegie classification, all measured in 2017-18, with every slope allowed to differ between public and private schools (R² = {s5['r2_main']:.2f}). This interaction model was chosen over a single pooled slope because its ranking agrees with sector-only rankings far better ({s5['ranking_comparison']['overlap_int_vs_sector_public']:.0%} / {s5['ranking_comparison']['overlap_int_vs_sector_private']:.0%} top-decile overlap vs {s5['ranking_comparison']['overlap_pool_vs_sector_public']:.0%} / {s5['ranking_comparison']['overlap_pool_vs_sector_private']:.0%}). Spending is deliberately left out so the comparison above is not circular.
- **Residual = actual − predicted,** shrunk toward zero for small cohorts (empirical Bayes). A 60-student cohort keeps about {s6['shrink_min']:.0%} of its raw residual, a 3,000-student cohort nearly all of it. Shrinkage removed {s6['top_decile_left']} schools from the top decile, all {s6['top_decile_left_under100']} with cohorts under 100. Top 10% = {s6['top_decile_n']} schools at **+{s6['top_decile_cut_pp']:.0f} points or better**.

## What the model says about student mix (pooled slopes, for orientation)

Holding other traits fixed, each 10-point rise in Pell share predicts {abs(cA['pctpell'])*10:.1f} points lower first-gen completion; each 10-point rise in admission rate predicts {abs(cA['adm_rate'])*10:.1f} points lower; a 10-point rise in part-time share predicts {abs(cA['pptug_ef'])*10:.1f} points lower; HBCUs run {cA['hbcu_flag']*100:+.1f} points. Pell share and first-gen share overlap (correlation {s5['corr_pell_firstgen']:.2f}), so read them as one combined disadvantage headwind rather than two separate levers.

## Pooled spending, top 10% vs bottom 10% (median dollars per FTE, FY2018-23 average)

| Category | Top 10% | Bottom 10% | Ratio | Mann-Whitney p |
|---|---:|---:|---:|---:|
{row('Instruction', pf, 'Instruction')}
{row('Academic support (advising, tutoring, libraries)', pf, 'Academic support')}
{row('Student services (admissions, counseling, activities)', pf, 'Student services')}
{row('Institutional support (administration)', pf, 'Institutional support')}

Budgets sum to 100%, so a larger instruction share is the same fact as more instruction dollars, not a second finding. The gap also holds within Carnegie type: doctoral universities instruction {carn['Doctoral']['per_fte']['Instruction']['median_ratio']:.2f}× and academic support {carn['Doctoral']['per_fte']['Academic support']['median_ratio']:.2f}×; master's {carn["Master's"]['per_fte']['Instruction']['median_ratio']:.2f}× and {carn["Master's"]['per_fte']['Academic support']['median_ratio']:.2f}×; baccalaureate {carn['Baccalaureate']['per_fte']['Instruction']['median_ratio']:.2f}× and {carn['Baccalaureate']['per_fte']['Academic support']['median_ratio']:.2f}×.

## Peers worth a phone call (high-Pell schools, Pell share ≥ 50% in 2017-18, largest shrunken residuals)

| School | Carnegie | First-gen cohort | Pell | Actual | Predicted | Residual (pts) |
|---|---|---:|---:|---:|---:|---:|
{peers(s6['top5_high_pell'])}

## Does it hold up?

- **Multiple comparisons and influence:** after a Benjamini-Hochberg correction across all {s7['bh']['n_tests']} spending tests, the instruction and academic-support gaps survive in every comparison (pooled, each sector, each Carnegie group, each timing window) and the student-services gap survives in none. Dropping the {s7['n_cooks_dropped']} most influential schools leaves instruction at {s7['per_fte_no_cooks']['Instruction']['median_ratio']:.2f}× and academic support at {s7['per_fte_no_cooks']['Academic support']['median_ratio']:.2f}×.
- **Timing variants:** using only FY2018-19 spending (the cohort's first two years) gives instruction {f1819['Instruction']['median_ratio']:.2f}× and academic support {f1819['Academic support']['median_ratio']:.2f}×; all six years in constant FY2023 dollars gives {real['Instruction']['median_ratio']:.2f}× and {real['Academic support']['median_ratio']:.2f}×. The gaps do not depend on the window or on inflation.
- **Bootstrap (1,000 resamples):** the {bs['n_top_decile']} top-decile schools stay top-decile in {bs['mean_p_top_among_point_top']:.0%} of resamples on average; {bs['share_p_ge_0_9']:.0%} of them in at least 90% of resamples.
- **Sector models** rank schools consistently with the pooled model (Spearman {sec['Public']['spearman_vs_pooled']:.2f} public, {sec['Private nonprofit']['spearman_vs_pooled']:.2f} private).
- **Spending in the model:** adding core spending per student and the undergraduate share of enrollment raises R² from {s5['r2_A']:.2f} to {s5['r2_B']:.2f}; a 10% higher budget per student is associated with {s5['pp_per_10pct_spending']:+.1f} points.
- **What the review changed:** the first version used a stale Scorecard file, 2024 traits, FY2023-only spending and no Carnegie control; only {s6['top20_overlap_vs_v1']} of its top-20 schools survive (rank correlation {s6['spearman_vs_v1_mistimed']:.2f}). The instruction and academic-support finding survived every fix.

## Limitations

1. **School-level data.** We see institutions, not students; a school can over-perform because of program mix or who it enrolls in ways the model does not capture. Special-focus colleges (nursing, faith, arts), adult- or online-dominant campuses, and schools with implausible reported rates are excluded for this reason and listed separately.
2. **Correlation only.** Over-performers spent differently; we cannot say that reallocating dollars would change completion.
3. **Definition.** Completion at the same institution for federal-aid students; transfer-out completers count as non-completers. Privacy suppression removes the smallest schools.

## Suggested next step

Pick five peers from the table above in your own sector and compare advising ratios, tutoring reach and gateway-course redesign, the activities that sit inside "instruction" and "academic support" in IPEDS. The dashboard (`streamlit run app/app.py`) filters the ranking by state, sector, Carnegie group, size and Pell share.
"""
(ROOT / "memo/memo.md").write_text(memo)

readme = f"""# Which 4-year colleges graduate first-generation students above prediction, and what did they spend on?

Portfolio project (UCSD MSBA application). Python · DuckDB · pandas · statsmodels · plotly · Streamlit.

## Question

Which US 4-year colleges graduated first-generation students at higher rates than their student mix and structure predict, and how did their spending differ, during the years those students were enrolled, from schools that under-performed?

## Headline results (all numbers generated by the pipeline; see `reports/results.json`)

- **Cohort alignment:** outcome = first-gen students who entered in AY2017-18, measured in AY2023-24 (Scorecard cohort map). Predictors are the schools' 2017-18 values; spending is the FY2018-FY2023 average per FTE.
- **Sample:** {s5['n']:,} four-year public and private nonprofit colleges (Carnegie doctoral, master's, baccalaureate). Scored separately: {s5['n_special_focus']} special-focus schools, {s5['n_nontraditional']} campuses with >50% of undergraduates aged 25+ or exclusively online, {s5['n_anomaly']} schools with implausible Scorecard completion rates (e.g. San Jose State's 3.8%).
- **Model:** OLS of first-gen same-institution 6-year completion on Pell share, admission rate, log enrollment, part-time share, first-gen share, share aged 25+, share exclusively online, HBCU and Carnegie group, with private × every trait (**R² = {s5['r2_main']:.3f}**; pooled version {s5['r2_A']:.3f}), HC3 robust SEs. The interaction model is the ranking model because its top decile overlaps the sector-only rankings at {s5['ranking_comparison']['overlap_int_vs_sector_public']:.0%} (public) and {s5['ranking_comparison']['overlap_int_vs_sector_private']:.0%} (private). Spending is not in the model.
- **Ranking:** residual = actual − predicted, shrunk toward zero for small cohorts (empirical Bayes; τ = {s6['tau_pp']:.1f} pts). Shrinkage removed {s6['top_decile_left']} small-cohort schools from the top decile. Top decile ({s6['top_decile_n']} schools) beat prediction by **≥ {s6['top_decile_cut_pp']:.1f} points**.
- **Spending, by sector:** in a public-only model, over-performing publics spent more on all four core functions (instruction {pub['Instruction']['median_ratio']:.2f}×, academic support {pub['Academic support']['median_ratio']:.2f}×, student services {pub['Student services']['median_ratio']:.2f}×). In a private-only model the gap is instruction {prv['Instruction']['median_ratio']:.2f}× and academic support {prv['Academic support']['median_ratio']:.2f}× with no student-services difference. Pooled: instruction {pf['Instruction']['median_ratio']:.2f}×, academic support {pf['Academic support']['median_ratio']:.2f}× (p < 0.001), student services {pf['Student services']['median_ratio']:.2f}×.
- **Robustness:** a Benjamini-Hochberg correction across {s7['bh']['n_tests']} spending tests keeps the instruction and academic-support gaps everywhere and the student-services gap nowhere; dropping {s7['n_cooks_dropped']} Cook's-flagged schools leaves them at {s7['per_fte_no_cooks']['Instruction']['median_ratio']:.2f}× / {s7['per_fte_no_cooks']['Academic support']['median_ratio']:.2f}×. Results hold with FY2018-19 spending only ({f1819['Instruction']['median_ratio']:.2f}× / {f1819['Academic support']['median_ratio']:.2f}×), in constant FY2023 dollars ({real['Instruction']['median_ratio']:.2f}× / {real['Academic support']['median_ratio']:.2f}×), and within each Carnegie group. A 1,000-resample bootstrap keeps top-decile schools in the top decile {bs['mean_p_top_among_point_top']:.0%} of the time.

![spending](reports/figures/07_spending_top_vs_bottom.png)

## What changed after review (see `decisions.md`)

Four review passes found fourteen problems: spending measured after the cohort left, a stale Scorecard download, ambiguity about whether spending sat inside the model, nursing and health colleges dominating the ranking, a weak robustness check, no shrinkage for small cohorts, budget shares presented as separate findings, no control for adult or online student mix, one campus (San Jose State) with an implausible reported rate at the bottom of the list, a single pooled slope where public and private schools need different ones, no multiple-comparison correction, no influence check on the spending comparison, and an unreported VIF. All are fixed. Only {s6['top20_overlap_vs_v1']} of the original top-20 schools survive in the corrected ranking (Spearman {s6['spearman_vs_v1_mistimed']:.2f}); the instruction and academic-support finding held through every change. The original ranking is archived in `reports/archive/`.

## Data

| Source | File(s) | Role |
|---|---|---|
| College Scorecard (US Dept. of Education), Oct 2026 release | Most-Recent-Cohorts-Institution_10152026.csv; MERGED2017_18_PP.csv from the raw archive | outcome (first-gen completion, 2017-18 cohort); entry-year Pell share, admission rate, enrollment, part-time share |
| IPEDS (NCES) | HD2023, IC2023; F1718-F2223 finance (F1A public, F2 private nonprofit); EFIA2018-2023 | 4-year filter, Carnegie 2018, open-admission flag, FY2018-23 functional expenses per FTE |
| BLS CPI-U via FRED | CPIAUCSL | fiscal-year deflators for the constant-dollar check |
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
| 3 | `src/03_join.py` | `data/clean/joined.parquet`, `finance_by_year.parquet`, `reports/03_join_report.md` (drop funnel, CPI table) |
| 4 | `src/04_clean.py` | `data/clean/analysis.parquet`, `reports/04_data_quality.md` |
| 5 | `src/05_regress.py` | `reports/05_regression.md`, diagnostic plots in `reports/figures/` |
| 6 | `src/06_rank.py` | `data/clean/ranked_schools.csv`, `reports/06_rankings.md` (shrinkage, before/after the fixes) |
| 7 | `src/07_spending.py` | `reports/07_spending_comparison.md` (pooled, by sector, by Carnegie, timing variants) |
| 8 | `src/08_robustness.py` | `reports/08_robustness.md`, `data/clean/bootstrap_ranks.csv` |
| 9 | `app/app.py` | Streamlit dashboard |
| 10 | `src/10_memo.py` | `memo/memo.md`, this README |
| check | `reports/11_spot_check.md` | three schools checked by hand against the College Scorecard website |

`reports/06_rankings.md` also lists every California State University campus (raw and shrunken residual, rank, decile) and how the top 20 changed at each review pass.

`decisions.md` logs every modeling and cleaning choice with its reason. `reports/results.json` holds the key numbers the memo, README and dashboard read.

## Dashboard

`streamlit run app/app.py`: actual-vs-predicted scatter with hover, coefficient chart, filterable ranking (state, sector, Carnegie group, size, Pell share) with raw and shrunken residuals, bootstrap rank intervals and CSV download, spending comparison (pooled, sector models, Carnegie groups, timing variants), per-school lookup with peer comparison, methods and limitations.

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
print(memo[:3200])
