"""Step 10: generate the one page memo and README from reports/results.json.

No number in either document is typed by hand. Every figure is read from results.json,
which Steps 4 to 8 wrote from code output, and src/check_numbers.py fails the build if one drifts.
"""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "reports/results.json").read_text())
s4, s5, s6, s7, s8 = R["step4"], R["step5"], R["step6"], R["step7"], R["step8"]
pf, f1819, real = s7["per_fte"], s7["per_fte_fy1819"], s7["per_fte_real"]
bs, sec = s8["bootstrap"], s8["sector"]
pub, prv = s7["within_control"]["Public"]["per_fte"], s7["within_control"]["Private nonprofit"]["per_fte"]   # the within sector splits that sit in the BH family
miss_main, miss_sup = s4["missingness"]["main sample"], s4["missingness"]["privacy suppressed"]
thr = s4["thresholds"]
today = date.today().strftime("%B %Y")


def pv(x):
    return "<0.001" if x < 0.001 else f"{x:.3f}"


def peers(rows):
    return "\n".join(f"| {r['school']} ({r['state']}) | {r['carnegie']} | {r['cohort']:,} | {r['pell']:.0%} | {r['actual']:.0%} | {r['predicted']:.0%} | {r['resid_eb_pp']:+.0f} |" for r in rows)


lm = s5["money"]                                   # Model B-mix: partial R² against the ranking model, one coefficient per quantity
pp_double = lm["pp_per_doubling"]
r2_pct = lm["r2"] * 100
cut = s6["top_decile_cut_pp"]
headline = f"Budgets explain {r2_pct:.1f}% of beating the odds on first gen completion. Call the peers."

memo = f"""# Memo: {headline}

**To:** Director of Student Success. **From:** Isiah Luna. **Date:** {today}

## How much is money?

Among {s5['n']:,} four year colleges, the top tenth graduated first gen students at least {cut:.1f} points above prediction from their student mix. Adding spending level and mix explains **{r2_pct:.1f}%** of what that model left unexplained. Doubling core spending per student is associated with {pp_double:+.1f} points, one SD more academic support share with {lm['pp_per_sd_acad_share']:+.1f}, one SD more instruction share with {lm['pp_per_sd_instr_share']:+.1f} (budget held fixed). All three are small against the {cut:.1f} point gap. Call peers, do not reallocate.

## What budgets do show

Public over performers spent {pub['Instruction']['median_ratio']:.2f} times as much on instruction as public under performers, {pub['Academic support']['median_ratio']:.2f} on academic support, {pub['Student services']['median_ratio']:.2f} on student services. Private over performers: {prv['Instruction']['median_ratio']:.2f}, {prv['Academic support']['median_ratio']:.2f} and {prv['Student services']['median_ratio']:.2f}. After Benjamini and Hochberg correction across {s7['bh']['n_tests']} comparisons, instruction and academic support gaps survive everywhere, student services nowhere.

**Method.** Same school completion within six years, predicted from Pell share, admission rate, enrollment, part time, first gen, adult and online shares, HBCU and Carnegie type at entry (2017 to 2018), slopes by sector (R² {s5['r2_main']:.2f}). Residual = actual minus predicted, shrunk for small cohorts. P values: spending {pv(lm['p']['log_core_per_fte'])}, academic support share {pv(lm['p']['acad_share'])}, instruction share {pv(lm['p']['instr_share'])}.

## Call these peers ({s6['large_cohort_min']} or more first gen students)

| School | Kind | Cohort | Pell | Actual | Expected | Points above |
|---|---|---:|---:|---:|---:|---:|
{peers(s6['top_large'])}

Ask about advising, gateway courses and first gen support.

## Limitations

1. **School level data.** Institutions, not students. Unmeasured program mix or preparation can produce a residual unrelated to practice. {s5['n_excluded']} special focus, adult, online and shared campus schools are scored, not ranked.
2. **Correlation only.** The {pf['Instruction']['median_ratio']:.2f} times instruction gap describes who over performs, not what to change. Moving dollars may change nothing.
3. **Who is missing.** Transfer out completers count as non completers. Privacy suppression removes {miss_sup['schools']:.0f} schools, median {miss_sup['median_undergrads']:,.0f} undergraduates, {miss_sup['private_share']:.0%} private, so the ranking over represents larger, public colleges.
"""
(ROOT / "memo/memo.md").write_text(memo)

readme = f"""# Which four year colleges graduate first gen students above prediction, and how much of it is money?

**Live dashboard:** https://first-gen-beating-odds.streamlit.app

[![Overview of the dashboard: the share of the gap explained by money beside the large schools that beat expectations](assets/linkedin/01_overview_hero_1200x627.png)](https://first-gen-beating-odds.streamlit.app)

Some colleges graduate far more of their first gen students than you would expect from who they enroll. This project finds them and asks how much of the gap lines up with spending. The answer: how much a college spends, and what it spends it on, explains about {r2_pct:.0f} percent of why some schools beat the odds. A college that wants to do better can learn more from the peers that beat the odds with similar students than from moving money between budget lines.

Portfolio project by Isiah Luna, a first gen transfer student at SDSU. Python, DuckDB, pandas, statsmodels, plotly, Streamlit.

## Question

Which US four year colleges graduated first gen students at higher rates than their student mix and structure predict, and how did their spending differ, during the years those students were enrolled, from schools that fell short?

## Headline results (every number is generated by the pipeline from `reports/results.json`)

- How much money explains: spending level and mix together explain **{r2_pct:.1f}%** of the variance the ranking model leaves unexplained (partial R² of nested models). Doubling core spending per FTE is associated with about {pp_double:+.1f} points, one SD more academic support share with {lm['pp_per_sd_acad_share']:+.1f} and one SD more instruction share with {lm['pp_per_sd_instr_share']:+.1f}, against a top decile cut of +{cut:.1f} points. Most over performance sits outside budget data, so the memo's recommendation is a peer list, not a reallocation.
- Cohort alignment: the outcome is first gen students who entered in the 2017 to 2018 academic year, measured in 2023 to 2024 (Scorecard cohort map). Predictors are the schools' values in the entry year. Spending is the FY2018 to FY2023 average per FTE.
- Sample: {s5['n']:,} four year public and private nonprofit colleges (Carnegie doctoral, master's, baccalaureate). Scored but not ranked: {s5['n_special_focus']} special focus or tribal schools, {s5['n_nontraditional']} campuses with more than {thr['nontraditional_cut']:.0%} of undergraduates aged 25 or older or exclusively online, {s5['n_anomaly']} schools with implausible Scorecard completion rates (San Jose State's {s4['anomalies'][0]['firstgen_rate']:.1%} against an IPEDS graduation rate of {s4['anomalies'][0]['ipeds_grad_rate_c150_4']:.0%}), and {s5['n_shared_opeid']} campuses whose first gen outcome is pooled with other campuses under one OPEID (a campus is kept only if it holds at least {thr['opeid_share_cut']:.0%} of its group's undergraduates).
- Model: OLS of first gen same institution six year completion on Pell share, admission rate, log enrollment, part time share, first gen share, share aged 25 or older, share exclusively online, HBCU and Carnegie group, with private × every trait (R² {s5['r2_main']:.3f}, pooled version {s5['r2_A']:.3f}), HC3 robust SEs. The interaction model is the ranking model because its top decile overlaps the sector only rankings at {s5['ranking_comparison']['overlap_int_vs_sector_public']:.0%} (public) and {s5['ranking_comparison']['overlap_int_vs_sector_private']:.0%} (private). Spending is not in the model.
- Ranking: residual = actual minus predicted, shrunk toward zero for small cohorts (empirical Bayes, τ = {s6['tau_pp']:.1f} points). Shrinkage removed {s6['top_decile_left']} small cohort schools from the top decile. The top decile ({s6['top_decile_n']} schools) beat prediction by {cut:.1f} points or more.
- Spending, by sector: among public colleges, the top decile of the main ranking spent {pub['Instruction']['median_ratio']:.2f} times as much as the bottom decile on instruction, {pub['Academic support']['median_ratio']:.2f} times on academic support and {pub['Student services']['median_ratio']:.2f} times on student services. Among private colleges the gap is {prv['Instruction']['median_ratio']:.2f} times on instruction and {prv['Academic support']['median_ratio']:.2f} times on academic support, with student services at {prv['Student services']['median_ratio']:.2f} times. Pooled: instruction {pf['Instruction']['median_ratio']:.2f} times, academic support {pf['Academic support']['median_ratio']:.2f} times, student services {pf['Student services']['median_ratio']:.2f} times.
- Slopes differ by sector: joint Wald F test of the eight private × trait terms, F({s5['joint_F_interactions']['df_num']}, {s5['joint_F_interactions']['df_denom']}) = {s5['joint_F_interactions']['F']:.2f}, p {'< 0.001' if s5['joint_F_interactions']['p'] < 0.001 else f"= {s5['joint_F_interactions']['p']:.3f}"}. A fractional logit version of the model ranks schools the same in practice (Spearman {s8['fractional_logit']['spearman_vs_main']:.3f}, top decile overlap {s8['fractional_logit']['top_decile_overlap_vs_main']:.0%}).
- Level vs mix: in the nested model, {'both shares stay significant with the level fixed' if lm['shares_hold'] else 'the shares are not significant once the level is fixed'} (instruction share p = {lm['p']['instr_share']:.3f}, academic support p = {lm['p']['acad_share']:.3f}), and the level explains more (partial R² {lm['r2_level_only']:.3f} for the level alone against {lm['r2_mix_only']:.3f} for the mix alone). The earlier regression of the shrunken residual on raw spending (R² {s7['residual_on_raw_spending']['r2']:.3f}) is kept in Step 7 as a sensitivity.
- Robustness: a Benjamini and Hochberg correction across {s7['bh']['n_tests']} spending tests keeps the instruction and academic support gaps in every comparison and the student services gap in none. Dropping the {s7['n_cooks_dropped']} schools flagged by Cook's distance (4/n rule) leaves them at {s7['per_fte_no_cooks']['Instruction']['median_ratio']:.2f} and {s7['per_fte_no_cooks']['Academic support']['median_ratio']:.2f} times. The gaps hold with FY2018 to FY2019 spending only ({f1819['Instruction']['median_ratio']:.2f} and {f1819['Academic support']['median_ratio']:.2f} times), in constant FY2023 dollars ({real['Instruction']['median_ratio']:.2f} and {real['Academic support']['median_ratio']:.2f} times), and within each Carnegie group.
- Ranking stability: a {bs['B']:,} resample bootstrap redraws each school's graduation count from Binomial(cohort, rate) inside every resample, so the intervals carry each school's own sampling noise as well as the uncertainty in the prediction line. Top decile schools stay in the top decile {bs['mean_p_top_among_point_top']:.0%} of the time, and the rank interval of a typical top decile school spans {bs['median_rank_ci_width_top_decile']:.1f} positions (median width) out of {s5['n']:,}.

![spending](reports/figures/07_spending_top_vs_bottom.png)

## What changed after review (see `decisions.md`)

Six review passes tested timing, sample composition, small school noise, sector differences, multiple comparisons and the campus grain of the outcome. Every change sits in `decisions.md`. Only {s6['top20_overlap_vs_v1']} of the original top 20 schools survive in the corrected ranking (Spearman {s6['spearman_vs_v1_mistimed']:.2f}). The instruction and academic support finding held through every change. The earlier rankings are archived in `reports/archive/`.

## Data

| Source | File(s) | Role |
|---|---|---|
| College Scorecard (US Department of Education), October 2026 release | Most-Recent-Cohorts-Institution_10152026.csv, MERGED2017_18_PP.csv from the raw archive | outcome (first gen completion, 2017 to 2018 cohort), entry year Pell share, admission rate, enrollment, part time share |
| IPEDS (NCES) | HD2023, IC2023, F1718 through F2223 finance (F1A public, F2 private nonprofit), EFIA2018 through EFIA2023 | four year filter, Carnegie 2018, open admission flag, FY2018 to FY2023 functional expenses per FTE |
| BLS CPI for all urban consumers, via FRED | CPIAUCSL | fiscal year deflators for the constant dollar check |
| Opportunity Insights | mrc_table2, mrc_table11 | mobility rate and parent income (context) |

Join key: `UNITID`. Opportunity Insights is reached through OPEID and `super_opeid`. Raw files are gitignored, and `src/01_download.py` recreates them (about {R['step1']['raw_total_mb']:,} MB, mostly the Scorecard raw archive).

## Reproduce

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # or requirements.lock.txt for the exact versions used (Python 3.14)
for s in src/0[1-8]_*.py src/10_memo.py; do python "$s"; done
python src/check_numbers.py              # every number in the memo, README and dashboard text must trace to results.json
streamlit run app/app.py
```

Raw data (about {R['step1']['raw_total_mb']:,} MB) is gitignored and re downloaded by the first script. The cleaned outputs in `data/clean/` are committed, so the dashboard and all reports work without downloading anything.

## Deploy the dashboard (Streamlit Community Cloud)

1. Push this repository to GitHub (public or private, Community Cloud can read either).
2. At share.streamlit.io choose New app, select the repo and branch, and set the main file path to `app/app.py`.
3. Under advanced settings pick Python 3.12 or 3.13 (Cloud does not offer 3.14 yet) and leave the requirements file as `requirements.txt`. The lock file is for local reproduction on 3.14.
4. Deploy. The app reads `data/clean/analysis_scored.parquet`, `data/clean/bootstrap_ranks.csv` and `reports/results.json` from the repo, so no secrets, databases or downloads are needed.
5. After any pipeline rerun, commit the updated `data/clean/` and `reports/results.json`. Cloud redeploys on push.

## Pipeline (one script per build step)

| Step | Script | Output |
|---|---|---|
| 1 | `src/01_download.py` | `data/raw/`, `reports/01_raw_inventory.md` (row counts, columns) |
| 2 | `src/columns.py`, `src/02_columns.py` | `reports/02_column_selection.md` (every column, plain description, timing) |
| 3 | `src/03_join.py` | `data/clean/joined.parquet`, `finance_by_year.parquet`, `reports/03_join_report.md` (drop funnel, CPI table) |
| 4 | `src/04_clean.py` | `data/clean/analysis.parquet`, `reports/04_data_quality.md` (row accounting, missingness, shared OPEID campuses) |
| 5 | `src/05_regress.py` | `reports/05_regression.md`, diagnostic plots in `reports/figures/` |
| 6 | `src/06_rank.py` | `data/clean/ranked_schools.csv`, `reports/06_rankings.md` (shrinkage, before and after each review pass) |
| 7 | `src/07_spending.py` | `reports/07_spending_comparison.md` (pooled, by sector, by Carnegie, timing variants) |
| 8 | `src/08_robustness.py` | `reports/08_robustness.md`, `data/clean/bootstrap_ranks.csv` |
| 9 | `app/app.py` | Streamlit dashboard |
| 10 | `src/10_memo.py` | `memo/memo.md`, this README |
| check | `src/check_numbers.py`, `src/check_headlines.py`, `reports/11_spot_check.md` | number trace, independent recompute of the three headlines, three schools checked by hand against the College Scorecard website |

`requirements.lock.txt` pins the exact package versions used (Python 3.14). `reports/06_rankings.md` also lists every California State University campus (raw and shrunken residual, rank, decile) and how the top 20 changed at each review pass.

`decisions.md` logs every modeling and cleaning choice with its reason. `reports/results.json` holds the numbers the memo, README and dashboard read.

## Dashboard

Live at https://first-gen-beating-odds.streamlit.app. Locally, `streamlit run app/app.py`. Expected against actual scatter with hover, predictor chart, filterable ranking (state, sector, Carnegie group, size, Pell share) with raw and shrunken residuals, bootstrap rank intervals and CSV download, spending comparison (pooled, by sector, by Carnegie group, timing variants), per school lookup with peer comparison, methods and limitations.

## Limitations

- **School level data.** Institutions, not students, are the unit. Differences in program mix and preparation that the predictors do not capture can produce a residual unrelated to what the school does. Special focus colleges are set aside for this reason and listed in `reports/05_regression.md`.
- **Correlation only.** Spending differences describe over performers. They do not show that changing spending would change completion.
- **Outcome definition.** Completion at the same institution for federal aid students. Transfer out completers count as non completers.
- **Who is missing.** The {miss_sup['schools']:.0f} privacy suppressed schools have a median of {miss_sup['median_undergrads']:,.0f} undergraduates and are {miss_sup['private_share']:.0%} private, against {miss_main['median_undergrads']:,.1f} and {miss_main['private_share']:.0%} in the main sample, so the ranking over represents larger and public colleges and says nothing about colleges with fewer than {thr['min_cohort']} first gen federal aid students in the cohort.
- **Structural traits** (control, level, Title IV status, open admission) come from 2023 IPEDS files and are assumed unchanged since 2017.
- **Opportunity Insights** data describe students born 1980 to 1982 and are used as context only.

## Repository layout

```
app/        Streamlit dashboard
data/raw/   downloaded sources (gitignored)   data/clean/  joined, cleaned, scored datasets
memo/       one page memo to a student success director
reports/    step by step reports, figures, results.json, archive/ (earlier rankings)
src/        numbered pipeline scripts and the number trace
CLAUDE.md   original project brief      decisions.md  decisions log
```
"""
(ROOT / "README.md").write_text(readme)
print(memo[:3200])
