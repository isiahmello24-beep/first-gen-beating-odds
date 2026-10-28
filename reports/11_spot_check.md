# Spot check against the College Scorecard website (2026-10-23)

Three schools from `data/clean/ranked_schools.csv` were looked up by hand at `collegescorecard.ed.gov/school/?<UNITID>` and compared with (a) the raw Scorecard CSV in `data/raw/` and (b) the pipeline output. Website values are what the public site displayed on the day of the check; the site rounds to whole percents.

## Fields the website displays

| School (UNITID) | Field | Website | Raw CSV (Oct-2026 file) | Match |
|---|---|---:|---:|---|
| CSU Channel Islands (441937) | Undergraduates | 5,013 | UGDS 5,013 | exact |
| | Acceptance rate | 95% | ADM_RATE 0.9481 | exact |
| | Return after first year | 73% | RET_FT4 0.7243 | exact |
| | Average annual cost | $8,534 | NPT4_PUB 8,534 | exact |
| | Pell share | 50% | PCTPELL 0.5227 | off by 2 pts |
| Rutgers University-Camden (186371) | Undergraduates | 3,753 | UGDS 3,753 | exact |
| | Acceptance rate | 66% | ADM_RATE 0.6629 | exact |
| | Return after first year | 81% | RET_FT4 0.80 | off by 1 pt |
| | Average annual cost | $15,732 | NPT4_PUB 15,732 | exact |
| | Pell share | 49% | PCTPELL 0.4866 | exact |
| University of California-Merced (445188) | Undergraduates | 8,372 | UGDS 8,372 | exact |
| | Acceptance rate | 91% | ADM_RATE 0.9053 | exact |
| | Return after first year | 83% | RET_FT4 0.8213 | off by 1 pt |
| | Average annual cost | $11,583 | NPT4_PUB 11,583 | exact |
| | Pell share | 60% | PCTPELL 0.6198 | off by 2 pts |

Enrollment, acceptance rate and net price match to the digit at all three schools, which confirms (1) the file in `data/raw/` is the release behind the public site and (2) each UNITID in the pipeline points at the right school. The Pell share and retention figures differ by 1-2 points at two schools: the site appears to draw those from a different Scorecard variable or pooled year than `PCTPELL` / `RET_FT4` (the data dictionary lists several Pell and retention measures). This is recorded, not resolved; it does not affect the analysis, which uses the 2017-18 values below.

## Fields the website does not display

The public site does not show the first-generation 6-year completion rate or the 2017-18 Pell share, so those were checked raw file → pipeline:

| School | FIRSTGEN_COMP_ORIG_YR6_RT raw | in ranked_schools.csv | PCTPELL 2017-18 raw (MERGED2017_18_PP) | in ranked_schools.csv |
|---|---:|---:|---:|---:|
| CSU Channel Islands | 0.708597 | 0.708597 | 0.5065 | 0.5065 |
| Rutgers University-Camden | 0.743728 | 0.743728 | 0.4312 | 0.4312 |
| University of California-Merced | 0.691735 | 0.691735 | 0.6125 | 0.6125 |

All six values are identical, so the join and cleaning steps carried the outcome and the entry-year Pell share through unchanged.

## What this check does and does not prove

It proves the data file is current, the UNITID key is right, and the pipeline does not alter the values it ranks on. It does not independently verify the Department of Education's own numbers, and it leaves a small, documented discrepancy in how the public site reports Pell share.


Note added 2026-10-27: Rutgers University-Camden matched the Scorecard website because both show the pooled Rutgers system rate (the Scorecard reports NSLDS completion per 6-digit OPEID). A spot check cannot catch that, so Step 3 now measures each campus's share of its OPEID group and Step 4 sets Camden aside.
