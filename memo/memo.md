# Memo: Which colleges beat the odds on first-generation completion, and what they spent on

**To:** Director of Student Success  **From:** Isiah Mello  **Date:** 2026-10-23
**Data:** College Scorecard (Oct 2026 release), IPEDS finance FY2018-FY2023, Opportunity Insights; 1,198 four-year public and private nonprofit colleges (103 special-focus, adult- or online-dominant, or anomalous-data schools listed separately).

## Bottom line: the answer depends on your sector

For first-generation students who entered college in 2017-18, the schools that graduated them well above what their student mix predicts spent more per student than comparable under-performers, but *where* the extra money sat differs by sector:

- **Public universities.** Ranked against other publics, over-performers spent more on every core function during the cohort's years: instruction 1.25× (p = 0.004), academic support 1.48× (p = <0.001), student services 1.28× (p = 0.048), institutional support 1.23×. The public signal is "more of everything that touches students," not a reallocation.
- **Private nonprofits.** Over-performers spent 1.44× on instruction and 1.36× on academic support (both p < 0.001), with **no** student-services difference (1.03×, p = 0.732).

Pooling both sectors, the instruction (1.32×) and academic-support (1.37×) gaps are clear and the student-services gap is zero (0.97×), but that pooled picture is driven by private colleges: restricted to publics, the pooled-decile gaps shrink to 1.08× and 1.38× and are not statistically significant. A public director should read the public-only row, not the headline. This is a school-level correlation, not proof that moving money moves completion.

## What we measured

- **Outcome:** share of first-generation federal-aid students in the 2017-18 entry cohort who completed at the same school within 6 years (mean 51%, standard deviation 15%).
- **Timing:** predictors are the school's 2017-18 values; spending is averaged over fiscal years 2018-2023, the years the cohort was enrolled.
- **Prediction model:** OLS on Pell share, admission rate, enrollment, part-time share, first-gen share, share of students aged 25+, share exclusively online, public/private, HBCU and Carnegie classification, all measured in 2017-18. R² = 0.53. Spending is deliberately left out so the comparison above is not circular.
- **Residual = actual − predicted,** shrunk toward zero for small cohorts (empirical Bayes). A 60-student cohort keeps about 66% of its raw residual, a 3,000-student cohort nearly all of it. Shrinkage removed 10 schools from the top decile, all 10 with cohorts under 100. Top 10% = 120 schools at **+12 points or better**.

## What the model says about student mix

Holding other traits fixed, each 10-point rise in Pell share predicts 3.2 points lower first-gen completion; each 10-point rise in admission rate predicts 1.6 points lower; a 10-point rise in part-time share predicts 2.8 points lower; HBCUs run -10.3 points; private nonprofits +6.3 points relative to publics.

## Pooled spending, top 10% vs bottom 10% (median dollars per FTE, FY2018-23 average)

| Category | Top 10% | Bottom 10% | Ratio | Mann-Whitney p |
|---|---:|---:|---:|---:|
| Instruction | $11,073 | $8,364 | 1.32× | <0.001 |
| Academic support (advising, tutoring, libraries) | $2,826 | $2,065 | 1.37× | <0.001 |
| Student services (admissions, counseling, activities) | $3,971 | $4,095 | 0.97× | 0.741 |
| Institutional support (administration) | $5,049 | $4,253 | 1.19× | 0.005 |

Budgets sum to 100%, so a larger instruction share is the same fact as more instruction dollars, not a second finding. The gap also holds within Carnegie type: doctoral universities instruction 1.39× and academic support 1.76×; master's 1.10× and 1.27×; baccalaureate 1.72× and 1.55×.

## Peers worth a phone call (high-Pell schools, Pell share ≥ 50% in 2017-18, largest shrunken residuals)

| School | Carnegie | First-gen cohort | Pell | Actual | Predicted | Residual (pts) |
|---|---|---:|---:|---:|---:|---:|
| University of California-Merced (CA) | Doctoral | 1,343 | 61% | 69% | 42% | +27 |
| California State University-Channel Islands (CA) | Master's | 1,105 | 51% | 71% | 45% | +25 |
| Warner Pacific University (OR) | Baccalaureate | 135 | 52% | 64% | 34% | +25 |
| University of California-Riverside (CA) | Doctoral | 2,503 | 56% | 76% | 53% | +23 |
| Heritage University (WA) | Master's | 174 | 76% | 55% | 32% | +20 |

## Does it hold up?

- **Timing variants:** using only FY2018-19 spending (the cohort's first two years) gives instruction 1.46× and academic support 1.39×; all six years in constant FY2023 dollars gives 1.32× and 1.36×. The gaps do not depend on the window or on inflation.
- **Bootstrap (1,000 resamples):** the 120 top-decile schools stay top-decile in 93% of resamples on average; 77% of them in at least 90% of resamples.
- **Sector models** rank schools consistently with the pooled model (Spearman 0.96 public, 0.98 private).
- **Spending in the model:** adding core spending per student and the undergraduate share of enrollment raises R² from 0.53 to 0.56; a 10% higher budget per student is associated with +0.8 points.
- **What the review changed:** the first version used a stale Scorecard file, 2024 traits, FY2023-only spending and no Carnegie control; only 4 of its top-20 schools survive (rank correlation 0.66). The instruction and academic-support finding survived every fix.

## Limitations

1. **School-level data.** We see institutions, not students; a school can over-perform because of program mix or who it enrolls in ways the model does not capture. Special-focus colleges (nursing, faith, arts), adult- or online-dominant campuses, and schools with implausible reported rates are excluded for this reason and listed separately.
2. **Correlation only.** Over-performers spent differently; we cannot say that reallocating dollars would change completion.
3. **Definition.** Completion at the same institution for federal-aid students; transfer-out completers count as non-completers. Privacy suppression removes the smallest schools.

## Suggested next step

Pick five peers from the table above in your own sector and compare advising ratios, tutoring reach and gateway-course redesign, the activities that sit inside "instruction" and "academic support" in IPEDS. The dashboard (`streamlit run app/app.py`) filters the ranking by state, sector, Carnegie group, size and Pell share.
