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
