# Memo: Which colleges beat the odds on first-generation completion, and what they spend on

**To:** Director of Student Success  **From:** Isiah Mello  **Date:** 2026-10-23
**Data:** College Scorecard, IPEDS FY2022-23 finance, Opportunity Insights; 1,397 four-year public and private nonprofit colleges.

## Bottom line

Across 1,397 four-year colleges, the schools that graduate first-generation students well above what their student mix predicts spend more per student on **instruction** and **academic support**, not on student services. Under-performers spend similar dollars on student services but a larger *share* of their budget there. This is a correlation at the school level, not proof that moving money would move completion, but it points to where the strongest peers put their resources.

## What we measured

- **Outcome:** share of first-generation federal-aid students who complete at the same school within 6 years (sample mean 51%, standard deviation 16%).
- **Prediction model:** OLS regression on Pell share, admission rate, enrollment, part-time share, first-gen share, public/private, HBCU, and online-only status. R² = 0.54: these traits explain about 54% of the school-to-school variation.
- **Residual = actual − predicted.** A residual of +10 points means a school graduates first-gen students 10 points above what similar schools achieve. Top 10% = 140 schools at **+13 points or better**; bottom 10% at -13 or worse.

## What the model says about student mix

Holding other traits fixed, each 10-point rise in Pell share predicts 2.7 points lower first-gen completion; each 10-point rise in admission rate predicts 1.6 points lower; a 10-point rise in part-time share predicts 2.0 points lower. Private nonprofits run +5.4 points relative to publics. These are the headwinds the ranking adjusts for.

## What over-performers spend on (top 10% vs bottom 10%, median dollars per FTE student)

| Category | Top 10% | Bottom 10% | Ratio | Share of core budget: top vs bottom |
|---|---:|---:|---:|---|
| Instruction | $12,137 | $8,554 | 1.42× | 46% vs 42% |
| Academic support (advising, tutoring, libraries) | $3,027 | $1,840 | 1.64× | 13% vs 11% |
| Student services (admissions, counseling, activities) | $4,799 | $4,571 | 1.05× | 18% vs 23% |
| Institutional support (administration) | $6,154 | $4,654 | 1.32× | 22% vs 24% |

Instruction and academic support differences are statistically clear (Mann-Whitney p < 0.001 for both); the student-services dollar difference is not (p = 0.18), while the student-services *share* difference is (p < 0.001). Among private nonprofits alone the gap is wider (instruction 1.53×, academic support 2.18×); among publics it is smaller (instruction 1.08×, academic support 1.09×, student services 1.33×), so for a public institution the signal is "more of everything that touches academics", not a reallocation away from student services.

## Peers worth a phone call (high-Pell schools, Pell share ≥ 50%, largest residuals)

| School | Pell | Actual | Predicted | Residual (pts) |
|---|---:|---:|---:|---:|
| Pacific Oaks College (CA) | 62% | 56% | 21% | +35 |
| Methodist College (IL) | 56% | 63% | 31% | +32 |
| Dewey University-Hato Rey (PR) | 95% | 45% | 15% | +30 |
| Columbia College Hollywood (CA) | 55% | 69% | 40% | +30 |
| California State University-Stanislaus (CA) | 60% | 63% | 33% | +30 |

## Does it hold up?

Dropping the largest 5% of schools (70 universities over 23,686 undergrads) leaves the ranking essentially unchanged (rank correlation 0.998, 96% of the top decile identical) and the spending pattern intact (instruction 1.37×, academic support 1.87×). Adding spending per student to the model raises R² from 0.54 to 0.59; a 10% higher core budget per student is associated with +0.9 points of first-gen completion.

## Limitations

1. **School-level data.** We see institutions, not students; a school can over-perform because of program mix or who it enrolls in ways the model does not capture. The raw top of the list is small nursing and health colleges for exactly this reason.
2. **Correlation only.** Over-performers spend differently; we cannot say that reallocating dollars would change completion.
3. **Timing and definition.** Finance is FY2023; the completion cohorts entered 6-8 years earlier. Students who transfer and finish elsewhere count as non-completers.

## Suggested next step

Pick five peers from the table above with a similar Pell share and sector, and compare advising ratios, tutoring reach and gateway-course redesign, the activities that sit inside "instruction" and "academic support" in IPEDS. The dashboard (`streamlit run app/app.py`) filters the full ranking by state, sector, size and Pell share.
