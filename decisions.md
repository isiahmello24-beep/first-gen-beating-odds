# Decisions log

One line per decision: what was chosen and why.

- Project folder `firstgen-college-analysis` under home, own git repo: keeps the portfolio project self-contained and pushable to GitHub as-is.
- Python 3.14 virtual environment in `.venv` (gitignored): isolates dependencies so the project reproduces on a reviewer's machine from `requirements.txt`.
- Numbered scripts in `src/` instead of one notebook: each build step is re-runnable and reviewable on its own; notebooks are kept for exploration only.
- Data vintages: Scorecard most-recent-cohorts file (downloaded 2026-10-23), IPEDS 2023 collection (HD2023, IC2023, EFIA2023, F2223 finance = fiscal year 2022-23), OI mrc_table2: latest IPEDS finance file available at download time was F2223; HD/IC/EFIA chosen from the same collection year so all IPEDS fields describe the same academic year.
- Opportunity Insights joined through OPEID (mrc_table11 → Scorecard OPEID6 → UNITID): OI publishes no UNITID, so a two-hop key is the only way to honor the UNITID join requirement.
- Outcome = FIRSTGEN_COMP_ORIG_YR6_RT (first-gen completion at the same institution within 6 years): the question is about what a school does for its own students, so transfers-out are excluded from the numerator; 4-year and 8-year windows kept as sensitivity options.
- Selectivity = ADM_RATE with open-admission schools (IPEDS OPENADMP = 1) set to 1.0: SAT_AVG is missing for ~45% of 4-year schools, and a missing admission rate at an open-admission school means "admits everyone", not "unknown".
- Size = log(UGDS): enrollment is heavily right-skewed; logs make a 10% enrollment difference mean the same thing at a 1,000-student and a 40,000-student school.
- Spending per student = IPEDS functional expenses ÷ total 12-month FTE (undergrad + grad + professional): instruction and support spending serve all students, and this matches how Scorecard builds INEXPFTE, which we use as a cross-check.
- For-profit 4-year schools excluded: they file IPEDS finance form F3, which collapses academic support, student services and institutional support into one line, so their spending is not comparable.
- Column selection lives in src/columns.py and the report is generated from it: one source of truth so the docs cannot drift from the code.
- "4-year school" = Scorecard PREDDEG = 3 AND IPEDS ICLEVEL = 1, active and Title IV: PREDDEG captures what the school mainly awards (so a community college with a few bachelor's programs is out), ICLEVEL confirms the IPEDS classification; both are needed because they disagree for ~50 schools.
- Inner joins for HD, finance and FTE; LEFT joins for IC admissions policy and Opportunity Insights: spending per student is the core of the question so a school without finance data cannot be used, while OI covers only 73% of schools and is 20-year-old cohort data, so it is kept as context rather than a filter.
- Revised (_RV) IPEDS files used where NCES published one (IC2023, EFIA2023): the revised release corrects institution-reported errors found after the provisional release.
- Minimum first-gen cohort of 50 students (rule 2): a completion rate on 36 students moves 2.8 points per student, too noisy to rank; Scorecard's own suppression already removes most tiny cohorts, so only 9 schools are lost.
- Drop, do not impute, schools missing the outcome or a core predictor: imputing a completion rate and then ranking schools on it would rank the imputation, not the school.
- Blank expense lines on a filed IPEDS finance form = $0: IPEDS forms require every functional line, so a blank at a reporting school means no spending in that function (e.g., a liberal arts college with no research line).
- Spending outliers (Yale at $221k core spending per FTE, one online campus at $749) kept, not trimmed: they are real values and the regression uses log spending, which keeps them from dominating; they are listed in the quality report for the reader.
- Main model (A) predicts first-gen completion from Pell share, admission rate, log enrollment, part-time share, first-gen share, private, HBCU, distance-only, and leaves spending OUT: the residual then means "better than schools with similar students and structure", so the Step 7 spending comparison can ask what over-performers spend on without adjusting that away; Model B adds spending to show how much money alone explains.
- OLS with HC3 robust standard errors instead of plain OLS SEs: Breusch-Pagan rejects constant variance (p < 1e-8); HC3 keeps inference honest without changing coefficients.
- Unweighted OLS (one school = one observation): the question ranks schools, so each school should count once; weighting by cohort size would let large universities dominate the fit.
- Linear probability model on a 0-1 rate instead of logit/fractional logit: outcome is a proportion between 0.07 and 0.95 with no pile-up at the bounds, coefficients are directly in percentage points, and residuals (the ranking tool) are easiest to explain; a fractional logit is a listed extension.
- Top/bottom 10% compared on medians and on log-scale Welch t-tests plus Mann-Whitney, not raw means: per-student spending has a long right tail (Yale-type schools) that would let a few schools drive a mean difference.
- Spending comparison repeated within public and within private nonprofit: privates spend roughly twice as much per student as publics, so a pooled comparison could reflect sector mix rather than what over-performers do differently.
- Spending reported both as dollars per FTE and as share of core spending: dollars answer "do they spend more?", shares answer "do they allocate differently?", and the two can disagree.
- Robustness cut = largest 5% by undergraduate enrollment (UGDS > 23,686, 70 schools): matches the brief; Spearman 0.998 between full and trimmed residual rankings and 96% top-decile overlap mean the ranking is not driven by big universities.
- Memo and README generated by src/10_memo.py from reports/results.json: guarantees every number is code output and that re-running the pipeline updates the documents.

## Fixes after review (2026-10-23)

- Timing: the Scorecard data dictionary cohort map says FIRSTGEN_COMP_ORIG_YR6_RT in the Oct-2026 file is the NSLDS AY2017-18 entry cohort measured in AY2023-24, so predictors now come from the MERGED2017_18_PP.csv file (entry year) and spending is the FY2018-FY2023 average per FTE (the six fiscal years the cohort was enrolled); the first build compared outcomes of students who left by 2023 with 2024 traits and FY2023 spending.
- The undated Scorecard download URL served a stale August-2024 file: the download script now uses the dated file that matches the dictionary release, and the stale file is kept out of the pipeline.
- First-gen share stays from the most-recent file: Scorecard stopped publishing FIRST_GEN after the 2016-17 file and the most-recent file carries that value (AY2015-16 + 2016-17 pooled), one to two years before our cohort, which is the closest available.
- Spending is NOT a predictor in Model A (it never was; Model B adds it): if it were, residuals would already be net of spending and comparing deciles on spending would be circular; keeping it out makes the residual "better than schools with similar students and structure" and leaves spending free to differ.
- Carnegie 2018 classification added: doctoral / master's / baccalaureate dummies control for institution type, and special-focus and tribal schools (codes 24-33, mostly nursing, faith and arts colleges with one structured program) are excluded from the main model and scored separately, because the model predicts them badly for reasons that have nothing to do with student success practice; a dashboard filter would have hidden rather than fixed this.
- Bootstrap of residual ranks (1,000 resamples, fixed seed) and separate public and private models replace the drop-largest-5% check as the main robustness evidence: resampling schools tests whether the ranking depends on which schools define the prediction line; the 5% trim barely changes a 1,251-school sample and is kept only because the brief asked for it.
- Budget shares are reported as composition only: the four core shares sum to 100%, so a higher instruction share is the same fact as a lower student-services share, and the memo now treats dollar differences as the finding.
- The pre-review ranking is archived in reports/archive/ and compared in Step 6 so the effect of the fixes is visible: only 7 of the original top 20 survive.

## Second review pass (2026-10-23)

- Empirical Bayes shrinkage of residuals by first-gen cohort size is now the primary ranking: a residual on a 60-student cohort has binomial sampling noise several times that of a 3,000-student cohort, so raw residuals over-represent tiny schools in both tails; the shrink factor τ²/(τ²+σ²ᵢ) uses the predicted rate for σ² and a method-of-moments τ², and the raw ranking is kept alongside for transparency (10 schools left the top decile, all with cohorts under 100).
- Spending comparison repeated with FY2018-19 only and with all six years in FY2023 dollars (BLS CPI-U fiscal-year averages fetched from FRED, never typed): the first checks that the gap exists in the cohort's early years when most attrition happens, the second that inflation across the window does not drive the average; both leave the instruction and academic-support ratios essentially unchanged.
- Undergraduate share of total FTE added to Model B: per-FTE spending at graduate-heavy universities partly serves graduate students, so without the control a research university could look high-spending on undergraduates; the spending coefficient barely moves, which is itself worth reporting.
- Spending comparison shown within each Carnegie group (doctoral, master's, baccalaureate): confirms the instruction and academic-support gap is not a composition effect across institution types.
- Memo rewritten to lead with the sector split: the pooled student-services result is driven by private colleges, and restricted to publics the pooled-decile gaps lose significance, so a public-sector reader needs the public-only model's answer first.
- FRED download uses a plain user agent: browser-style agents from a scripted client stall on FRED; this is a transport detail, logged so the next person does not lose an hour to it.
- Spot check against the College Scorecard website recorded in reports/11_spot_check.md: three ranked schools' Pell share and completion figures compared by hand to the public site.

## Third review pass (2026-10-23)

- Share of undergraduates aged 25+ (Scorecard UG25ABV, Fall 2017) and share exclusively online (IPEDS EF2017A_DIST, Fall 2017) added to Model A; campuses above 50% on either are scored out of sample and listed with the special-focus schools: adult-degree and online programs enroll students whose completion patterns the main model cannot describe, and two of them (Whitworth's adult program, UF Online) had been ranked 1 and 3.
- The Scorecard has no exclusively-online share, only a yes/no flag, so the share comes from IPEDS; IPEDS leaves the item blank with imputation flag "A" (not applicable) when a school offers no distance education, and that blank is read as zero, which saved 132 schools from being dropped for a non-missing value.
- The distance-only flag was removed from Model A: with the online share in the model and online-dominant campuses excluded, it was constant and redundant.
- Outcome-anomaly screen added: a school whose first-gen AND non-first-gen 6-year Scorecard rates are both below 25% of its IPEDS 150%-time graduation rate is listed, not ranked. San Jose State (3.8% and 4.5% vs 68%) made this necessary; the two measures differ in definition but not by a factor of four, so this is treated as a reporting problem rather than a true outcome.
- The pre-pass ranking is archived as reports/archive/v2_... and compared in Step 6 (Spearman 0.980, 14 of 20 top-20 schools retained), so the effect of the new controls is visible.
- Pre-COVID (FY2018-19), constant-dollar and undergraduate-FTE-share checks were already completed in the second pass; they are reported again with the new sample in reports/07 and 05.

## Fourth review pass (2026-10-23)

- Interaction model (private × every trait, Carnegie dummies shared) adopted as the ranking model by a pre-stated rule: its shrunken top decile overlaps the public-only ranking at 96% and the private-only ranking at 96%, against 69% and 89% for the pooled model; the pooled coefficients are still reported for orientation because single slopes are easier to read.
- The switch moved large public universities down the list (e.g. SDSU from rank 47 to 116, still top decile) because the public slope on part-time share and enrollment differs from the pooled one; this is reported in Step 6 rather than hidden, and the v3 pooled-control ranking is archived.
- Spending comparison repeated without the schools flagged by Cook's distance (4/n rule) under the ranking model: the instruction and academic-support gaps grow slightly, so no handful of influential schools creates them.
- Benjamini-Hochberg false-discovery-rate correction applied across every Mann-Whitney p-value Step 7 produces (100 tests): the instruction and academic-support gaps survive at FDR 0.05 in every comparison and the student-services gap in none, which is the claim the memo now makes.
- VIF reported for every predictor; only the share aged 25+ exceeds 5 (5.03), driven by its overlap with part-time share and enrollment; Pell share (2.43) and first-gen share (2.58) correlate at 0.62, so the memo reads them as one combined headwind.

## Fifth review pass (2026-10-23)

- Joint Wald F test (HC3) on the eight private × trait terms: F(8, 1178) = 6.82, p < 1e-8, so the interaction model is justified by a test as well as by the ranking-overlap rule.
- Level vs mix: the shrunken residual regressed on log core spending per FTE, instruction share and academic-support share with sector and Carnegie controls keeps both shares significant (p 0.047 and 0.004) but total spending explains more (R² 0.044 vs 0.018 for the mix alone); the memo headline is generated from this verdict so it cannot drift from the result.
- Fractional logit (binomial GLM, logit link) of the main model: Spearman 0.999 and 96% top-decile overlap with the OLS ranking, so the linear model is kept for interpretability with the logit reported as a check.
- Memo cut to under 450 words: sector split first, peer table, three limitations; everything else lives in the reports and dashboard.
- Public release: raw data confirmed absent from git, requirements.lock.txt pinned from the working environment (Python 3.14), Streamlit Community Cloud steps in the README (select Python 3.12/3.13 there and use requirements.txt).
