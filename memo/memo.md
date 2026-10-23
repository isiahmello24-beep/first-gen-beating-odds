# Memo: Which colleges beat the odds on first-generation completion, and what they spend on

**To:** Director of Student Success  **From:** Isiah Mello  **Date:** 2026-10-23
**Data:** College Scorecard (Oct 2026 release), IPEDS finance FY2018-FY2023, Opportunity Insights; 1,251 four-year public and private nonprofit colleges (special-focus schools analyzed separately).

## Bottom line

For the cohort of first-generation students who entered college in 2017-18, the schools that graduated them well above what their student mix predicts spent more per student on **instruction** and **academic support** during the years those students were enrolled. Student-services spending was no different overall. This is a school-level correlation, not proof that moving money would move completion, but it points to where the strongest peers put their resources.

## What we measured

- **Outcome:** share of first-generation federal-aid students in the 2017-18 entry cohort who completed at the same school within 6 years (mean 51%, standard deviation 15%).
- **Timing:** predictors are the school's 2017-18 values and spending is averaged over fiscal years 2018-2023, so every input describes the years the cohort was actually on campus.
- **Prediction model:** OLS on Pell share, admission rate, enrollment, part-time share, first-gen share, public/private, HBCU, online-only status and Carnegie classification. R² = 0.49: these traits explain about 49% of the school-to-school variation. Spending is deliberately left out of this model so the comparison below is not circular.
- **Residual = actual − predicted.** Top 10% = 125 schools at **+14 points or better**; bottom 10% at -14 or worse.

## What the model says about student mix

Holding other traits fixed, each 10-point rise in Pell share predicts 2.8 points lower first-gen completion; each 10-point rise in admission rate predicts 1.7 points lower; a 10-point rise in part-time share predicts 1.7 points lower; HBCUs run -11.3 points. Private nonprofits run +4.9 points relative to publics. These are the headwinds the ranking adjusts for.

## What over-performers spent (top 10% vs bottom 10%, median dollars per FTE student, FY2018-23 average)

| Category | Top 10% | Bottom 10% | Ratio | Mann-Whitney p |
|---|---:|---:|---:|---:|
| Instruction | $11,136 | $8,063 | 1.38× | <0.001 |
| Academic support (advising, tutoring, libraries) | $2,646 | $1,869 | 1.42× | <0.001 |
| Student services (admissions, counseling, activities) | $4,107 | $4,253 | 0.97× | 0.835 |
| Institutional support (administration) | $5,075 | $4,224 | 1.20× | 0.003 |

Because budgets sum to 100%, more instruction dollars also means a larger instruction *share*; that is the same fact, not a second finding.

**Sector matters.** In a public-only model, over-performing publics spent more on all four categories, including student services (1.32×, p = 0.022): the signal there is "more of everything that touches students". In a private-only model the gap is concentrated in instruction (1.55×) and academic support (1.60×) with no student-services difference (1.01×).

## Peers worth a phone call (high-Pell schools, Pell share ≥ 50% in 2017-18, largest residuals)

| School | Carnegie | Pell | Actual | Predicted | Residual (pts) |
|---|---|---:|---:|---:|---:|
| Whitworth University-Adult Degree Programs (WA) | Baccalaureate | 55% | 64% | 27% | +38 |
| Warner Pacific University (OR) | Baccalaureate | 52% | 64% | 34% | +30 |
| California State University-Channel Islands (CA) | Master's | 51% | 71% | 42% | +29 |
| Heritage University (WA) | Master's | 76% | 55% | 27% | +28 |
| University of California-Merced (CA) | Doctoral | 61% | 69% | 43% | +26 |

## Does it hold up?

- **Bootstrap (1,000 resamples):** the 125 top-decile schools stay in the top decile in 93% of resamples on average; 78% of them in at least 90% of resamples. The ranking is not an artifact of which schools happen to define the prediction line.
- **Separate sector models:** Spearman 0.94 (public) and 0.97 (private) with the pooled ranking; the spending pattern above holds in each.
- **Timing check:** using only FY2023 spending (after the cohort left) gives instruction 1.33× and academic support 1.47×, similar ratios, but the earlier version of this analysis also used 2024 traits and no Carnegie control, and only 7 of its top-20 schools survive in the corrected ranking (rank correlation 0.68).
- **Spending in the model:** adding core spending per student raises R² from 0.49 to 0.53; a 10% higher budget per student is associated with +0.9 points.

## Limitations

1. **School-level data.** We see institutions, not students; a school can over-perform because of program mix or who it enrolls in ways the model does not capture. Special-focus colleges (nursing, faith, arts) are excluded for this reason and listed separately.
2. **Correlation only.** Over-performers spend differently; we cannot say that reallocating dollars would change completion.
3. **Definition.** Completion at the same institution for federal-aid students; transfer-out completers count as non-completers. Privacy suppression removes the smallest schools.

## Suggested next step

Pick five peers from the table above with a similar Pell share and sector, and compare advising ratios, tutoring reach and gateway-course redesign, the activities that sit inside "instruction" and "academic support" in IPEDS. The dashboard (`streamlit run app/app.py`) filters the full ranking by state, sector, Carnegie group, size and Pell share.
