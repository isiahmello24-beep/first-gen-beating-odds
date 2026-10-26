# Memo: Budgets explain 5.1% of why some colleges beat the odds on first-generation completion. Look at the peers.

**To:** Director of Student Success · **From:** Isiah Luna · **Date:** 2026-10-25

## How much of over-performance is money?

Not much. Among 1,198 four-year colleges, the top tenth graduated first-generation students at least 11.2 points above what their 2017-18 student mix predicts. Spending level and mix together explain **5.1%** of the variation in that residual. With the budget size held fixed, one standard deviation more academic-support share is worth +0.9 points and one SD more instruction share +0.7; doubling core spending per student is worth about +3 points. All three are real (p = 0.004, 0.047, <0.001) and all are small against an 11.2-point gap. Most over-performance sits outside budget data: advising, course design, culture. So the recommendation is a list of schools to call, not a reallocation.

## What the budget data do show

Over-performers spent more per student, and the pattern differs by sector. Publics, ranked against publics: more on every core function (instruction 1.25×, academic support 1.48×, student services 1.28×). Privates: instruction 1.44× and academic support 1.36×, student services flat (1.03×). After correcting for 100 comparisons, the instruction and academic-support gaps survive everywhere; the student-services gap survives nowhere.

**Method.** Completion of first-gen federal-aid students at the same school within 6 years, predicted from 2017-18 Pell share, admission rate, enrollment, part-time, first-gen, adult and online shares, HBCU and Carnegie type, with slopes that differ by sector (R² 0.55). Residual = actual − predicted, shrunk for small cohorts; stable across 1,000 bootstrap resamples.

## The recommendation: call these peers (Pell share ≥ 50%)

| School | Type | Cohort | Pell | Actual | Predicted | Residual |
|---|---|---:|---:|---:|---:|---:|
| Warner Pacific University (OR) | Baccalaureate | 135 | 52% | 64% | 32% | +27 |
| Heritage University (WA) | Master's | 174 | 76% | 55% | 27% | +25 |
| California State University-Channel Islands (CA) | Master's | 1,105 | 51% | 71% | 48% | +22 |
| Universidad Adventista de las Antillas (PR) | Baccalaureate | 139 | 83% | 54% | 29% | +21 |
| Saint Peter's University (NJ) | Master's | 414 | 60% | 62% | 39% | +21 |

Ask about first-year advising, gateway courses and first-gen programming. Full ranking: `streamlit run app/app.py`.

## Limitations

1. **School-level data.** We see institutions, not students; program mix or unmeasured preparation can produce a residual unrelated to practice. Special-focus, adult-dominant and online-dominant campuses are listed separately.
2. **Correlation only.** Nothing here shows that moving dollars would change completion.
3. **Definition.** Transfer-out completers count as non-completers; privacy suppression removes the smallest schools.
