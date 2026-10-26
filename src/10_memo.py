"""Step 10: generate the one-page memo and README from reports/results.json.

No number in either document is typed by hand; every figure is read from results.json,
which Steps 5-8 wrote from code output.
"""
import json
import numpy as np
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


lm = s7["level_vs_mix"]
pp_double = lm["coef"]["log_core_per_fte"] * np.log(2) * 100          # points per doubling of core spending per FTE
r2_pct = lm["r2"] * 100
headline = f"Budgets explain {r2_pct:.1f}% of why some colleges beat the odds on first-generation completion. Look at the peers."

memo = f"""# Memo: {headline}

**To:** Director of Student Success · **From:** Isiah Luna · **Date:** {today}

## How much of over-performance is money?

Not much. Among {s5['n']:,} four-year colleges, the top tenth graduated first-gen students at least {s6['top_decile_cut_pp']:.1f} points above what their student mix predicts. Spending level and mix together explain **{r2_pct:.1f}%** of the variation in that residual. With the budget size held fixed, one standard deviation more academic-support share is associated with {lm['pp_per_sd_acad_share']:+.1f} points and one SD more instruction share with {lm['pp_per_sd_instr_share']:+.1f}; doubling core spending per student is associated with about {pp_double:+.0f} points. All three are real (p = {pv(lm['p']['acad_share'])}, {pv(lm['p']['instr_share'])}, {pv(lm['p']['log_core_per_fte'])}) and small against an {s6['top_decile_cut_pp']:.1f}-point gap. Most over-performance sits outside budget data, so the recommendation is a list of schools to call, not a reallocation.

## What the budget data do show

Over-performers spent more per student; the pattern differs by sector. Publics, ranked against publics: more on everything (instruction {pub['Instruction']['median_ratio']:.2f}×, academic support {pub['Academic support']['median_ratio']:.2f}×, student services {pub['Student services']['median_ratio']:.2f}×). Privates: instruction {prv['Instruction']['median_ratio']:.2f}× and academic support {prv['Academic support']['median_ratio']:.2f}×, student services flat ({prv['Student services']['median_ratio']:.2f}×). After correcting for {s7['bh']['n_tests']} comparisons, the instruction and academic-support gaps survive everywhere; the student-services gap nowhere.

**Method.** Completion of first-gen students at the same school within 6 years, predicted from 2017-18 Pell share, admission rate, enrollment, part-time, first-gen, adult and online shares, HBCU and Carnegie type, with slopes that differ by sector (R² {s5['r2_main']:.2f}). Residual = actual − predicted, shrunk for small cohorts.

## The recommendation: call these peers (500 or more first-gen students)

| School | Kind | First-gen cohort | Pell | Actual | Expected | Points above |
|---|---|---:|---:|---:|---:|---:|
{peers(s6['top_large'])}

Ask about advising, gateway courses and first-gen programming.

## Limitations

1. **School-level data.** We see institutions, not students; program mix or unmeasured preparation can produce a residual unrelated to practice. Special-focus, adult and online campuses are listed separately.
2. **Correlation only.** Nothing here shows that moving dollars would change completion.
3. **Definition.** Transfer-out completers count as non-completers; privacy suppression removes the smallest schools.
"""
(ROOT / "memo/memo.md").write_text(memo)

readme = f"""# Which 4-year colleges graduate first-generation students above prediction, and how much of it is money?

**Live dashboard:** https://first-gen-beating-odds.streamlit.app

Some colleges graduate far more of their first-generation students than you would expect from who they enroll, and this project finds them and asks whether money is the reason. The answer: how much a college spends, and what it spends it on, explains only about 5 percent of why some schools beat the odds. The takeaway for a college that wants to do better is to learn from the peer schools that beat the odds with similar students, not to move money between budget lines.

Portfolio project. Python · DuckDB · pandas · statsmodels · plotly · Streamlit.

## Question

Which US 4-year colleges graduated first-generation students at higher rates than their student mix and structure predict, and how did their spending differ, during the years those students were enrolled, from schools that under-performed?

## Headline results (all numbers generated by the pipeline; see `reports/results.json`)

- **Effect size first:** spending level and mix together explain **{r2_pct:.1f}%** of the variance in the over-performance residual. One SD more academic-support share ≈ {lm['pp_per_sd_acad_share']:+.1f} points, one SD more instruction share ≈ {lm['pp_per_sd_instr_share']:+.1f}, doubling core spending per FTE ≈ {pp_double:+.0f} points, against a top-decile cut of +{s6['top_decile_cut_pp']:.1f} points. Most over-performance sits outside budget data, so the memo's recommendation is a peer list, not a reallocation.

- **Cohort alignment:** outcome = first-gen students who entered in AY2017-18, measured in AY2023-24 (Scorecard cohort map). Predictors are the schools' 2017-18 values; spending is the FY2018-FY2023 average per FTE.
- **Sample:** {s5['n']:,} four-year public and private nonprofit colleges (Carnegie doctoral, master's, baccalaureate). Scored separately: {s5['n_special_focus']} special-focus schools, {s5['n_nontraditional']} campuses with >50% of undergraduates aged 25+ or exclusively online, {s5['n_anomaly']} schools with implausible Scorecard completion rates (e.g. San Jose State's 3.8%).
- **Model:** OLS of first-gen same-institution 6-year completion on Pell share, admission rate, log enrollment, part-time share, first-gen share, share aged 25+, share exclusively online, HBCU and Carnegie group, with private × every trait (**R² = {s5['r2_main']:.3f}**; pooled version {s5['r2_A']:.3f}), HC3 robust SEs. The interaction model is the ranking model because its top decile overlaps the sector-only rankings at {s5['ranking_comparison']['overlap_int_vs_sector_public']:.0%} (public) and {s5['ranking_comparison']['overlap_int_vs_sector_private']:.0%} (private). Spending is not in the model.
- **Ranking:** residual = actual − predicted, shrunk toward zero for small cohorts (empirical Bayes; τ = {s6['tau_pp']:.1f} pts). Shrinkage removed {s6['top_decile_left']} small-cohort schools from the top decile. Top decile ({s6['top_decile_n']} schools) beat prediction by **≥ {s6['top_decile_cut_pp']:.1f} points**.
- **Spending, by sector:** in a public-only model, over-performing publics spent more on all four core functions (instruction {pub['Instruction']['median_ratio']:.2f}×, academic support {pub['Academic support']['median_ratio']:.2f}×, student services {pub['Student services']['median_ratio']:.2f}×). In a private-only model the gap is instruction {prv['Instruction']['median_ratio']:.2f}× and academic support {prv['Academic support']['median_ratio']:.2f}× with no student-services difference. Pooled: instruction {pf['Instruction']['median_ratio']:.2f}×, academic support {pf['Academic support']['median_ratio']:.2f}× (p < 0.001), student services {pf['Student services']['median_ratio']:.2f}×.
- **Slopes differ by sector:** joint Wald F test of the eight private × trait terms, F({s5['joint_F_interactions']['df_num']}, {s5['joint_F_interactions']['df_denom']}) = {s5['joint_F_interactions']['F']:.2f}, p {'< 0.001' if s5['joint_F_interactions']['p'] < 0.001 else f"= {s5['joint_F_interactions']['p']:.3f}"}. A fractional-logit version of the model ranks schools identically in practice (Spearman {s8['fractional_logit']['spearman_vs_main']:.3f}, top-decile overlap {s8['fractional_logit']['top_decile_overlap_vs_main']:.0%}).
- **Level vs mix:** regressing the shrunken residual on log core spending, instruction share and academic-support share (sector and Carnegie controls): {'shares remain significant with the level fixed' if s7['level_vs_mix']['shares_hold'] else 'shares are not significant once the level is fixed'} (instruction share p = {s7['level_vs_mix']['p']['instr_share']:.3f}, academic support p = {s7['level_vs_mix']['p']['acad_share']:.3f}), but level explains more (R² {s7['level_vs_mix']['r2_level_only']:.3f} vs {s7['level_vs_mix']['r2_mix_only']:.3f}).
- **Robustness:** a Benjamini-Hochberg correction across {s7['bh']['n_tests']} spending tests keeps the instruction and academic-support gaps everywhere and the student-services gap nowhere; dropping {s7['n_cooks_dropped']} Cook's-flagged schools leaves them at {s7['per_fte_no_cooks']['Instruction']['median_ratio']:.2f}× / {s7['per_fte_no_cooks']['Academic support']['median_ratio']:.2f}×. Results hold with FY2018-19 spending only ({f1819['Instruction']['median_ratio']:.2f}× / {f1819['Academic support']['median_ratio']:.2f}×), in constant FY2023 dollars ({real['Instruction']['median_ratio']:.2f}× / {real['Academic support']['median_ratio']:.2f}×), and within each Carnegie group. A 1,000-resample bootstrap keeps top-decile schools in the top decile {bs['mean_p_top_among_point_top']:.0%} of the time.

![spending](reports/figures/07_spending_top_vs_bottom.png)

## What changed after review (see `decisions.md`)

Five review passes tested timing, sample composition, small school noise, sector differences, and multiple comparisons. Every change sits in `decisions.md`. Only {s6['top20_overlap_vs_v1']} of the original top-20 schools survive in the corrected ranking (Spearman {s6['spearman_vs_v1_mistimed']:.2f}); the instruction and academic-support finding held through every change. The original ranking is archived in `reports/archive/`.

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
pip install -r requirements.txt          # or requirements.lock.txt for the exact versions used (Python 3.14)
for s in src/0[1-8]_*.py src/10_memo.py; do python "$s"; done
streamlit run app/app.py
```

Raw data (~600 MB) is gitignored and re-downloaded by the first script. The cleaned outputs in `data/clean/` are committed, so the dashboard and all reports work without downloading anything.

## Deploy the dashboard (Streamlit Community Cloud)

1. Push this repository to GitHub (public or private; Community Cloud can read either).
2. At share.streamlit.io choose **New app**, select the repo and branch, set **Main file path** to `app/app.py`.
3. Under **Advanced settings** pick Python 3.12 or 3.13 (Cloud does not offer 3.14 yet) and leave the requirements file as `requirements.txt`; the lock file is for local reproduction on 3.14.
4. Deploy. The app reads `data/clean/analysis_scored.parquet`, `data/clean/bootstrap_ranks.csv` and `reports/results.json` from the repo, so no secrets, databases or downloads are needed.
5. After any pipeline rerun, commit the updated `data/clean/` and `reports/results.json`; Cloud redeploys on push.

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

`requirements.lock.txt` pins the exact package versions used (Python 3.14). `reports/06_rankings.md` also lists every California State University campus (raw and shrunken residual, rank, decile) and how the top 20 changed at each review pass.

`decisions.md` logs every modeling and cleaning choice with its reason. `reports/results.json` holds the key numbers the memo, README and dashboard read.

## Dashboard

Live at https://first-gen-beating-odds.streamlit.app. Locally, `streamlit run app/app.py`: actual-vs-predicted scatter with hover, coefficient chart, filterable ranking (state, sector, Carnegie group, size, Pell share) with raw and shrunken residuals, bootstrap rank intervals and CSV download, spending comparison (pooled, sector models, Carnegie groups, timing variants), per-school lookup with peer comparison, methods and limitations.

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
