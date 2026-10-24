# Memo: Schools that beat their prediction spent more per student, and tilted that money toward instruction and academic support

**To:** Director of Student Success · **From:** Isiah Mello · **Date:** 2026-10-23

## The answer depends on your sector

For first-generation students who entered in 2017-18, schools that graduated them well above prediction spent more per student during those years than under-performers. Where the money sat differs by sector:

- **Public universities** (ranked against publics): more on every core function. Instruction 1.25×, academic support 1.48×, student services 1.28×, institutional support 1.23× (medians, FY2018-23).
- **Private nonprofits:** instruction 1.44× and academic support 1.36×, with no student-services difference (1.03×).

After correcting for 100 comparisons, the instruction and academic-support gaps survive in every sector, Carnegie group and timing window; the student-services gap survives in none. With total spending held fixed, the mix still matters, modestly: one standard deviation more academic-support share is associated with +0.9 points of residual (p = 0.004), one SD more instruction share +0.7 (p = 0.047); a 10% larger core budget adds +0.4. Level explains more than mix (R² 0.044 vs 0.018).

**Method.** 1,198 four-year public and private nonprofit colleges. Completion of first-gen federal-aid students at the same school within 6 years, predicted from 2017-18 Pell share, admission rate, enrollment, part-time, first-gen, adult and online shares, HBCU and Carnegie type, with slopes that differ by sector (R² 0.55). Residual = actual − predicted, shrunk for small cohorts. Top 10% = 120 schools at +11 points or better; the ranking is stable across 1,000 bootstrap resamples.

## Peers worth a call (Pell share ≥ 50%)

| School | Type | Cohort | Pell | Actual | Predicted | Residual |
|---|---|---:|---:|---:|---:|---:|
| Warner Pacific University (OR) | Baccalaureate | 135 | 52% | 64% | 32% | +27 |
| Heritage University (WA) | Master's | 174 | 76% | 55% | 27% | +25 |
| California State University-Channel Islands (CA) | Master's | 1,105 | 51% | 71% | 48% | +22 |
| Universidad Adventista de las Antillas (PR) | Baccalaureate | 139 | 83% | 54% | 29% | +21 |
| Saint Peter's University (NJ) | Master's | 414 | 60% | 62% | 39% | +21 |

## Limitations

1. **School-level data.** We see institutions, not students; program mix or unmeasured preparation can produce a residual that has nothing to do with practice. Special-focus, adult-dominant and online-dominant campuses are listed separately for this reason.
2. **Correlation only.** Over-performers spent differently; nothing here shows that reallocating dollars would change completion.
3. **Definition.** Transfer-out completers count as non-completers, and privacy suppression removes the smallest schools.

Full method and rankings: `streamlit run app/app.py`.
