# Project instructions (saved from the original build prompt)

You are helping me build a data analytics portfolio project for my UCSD MSBA application. Build the project end to end, then explain every step to me.

## Project

* Question: Which 4 year US colleges graduate first generation students at higher rates than predicted, and what do those schools spend money on?
* Data: College Scorecard (U.S. Department of Education), IPEDS finance and institutional characteristics files, Opportunity Insights college level mobility data.
* Join key: UNITID.
* Tools: Python, DuckDB for SQL, pandas, statsmodels for regression, plotly for charts, Streamlit for the dashboard.
* Output: cleaned dataset, regression model, ranked list of over performing schools, spending comparison, Streamlit dashboard, one page memo to a student success director, README.

## Project setup

* Create folders: data/raw, data/clean, notebooks, src, app, memo.
* Create requirements.txt and a .gitignore excluding data/raw.
* Save this full prompt as CLAUDE.md in the project root.
* Commit to git after every working step with a clear commit message.

## Build order

1. Download all three datasets into data/raw. Print row counts and columns.
2. Pick columns for first gen completion, Pell share, selectivity, size, and spending per student. List each column with a plain description.
3. Join the datasets in DuckDB on UNITID, 4 year schools only. Report how many schools drop at each join and why.
4. Clean missing and suppressed values. Write a data quality report.
5. Run OLS regression: first gen completion rate on school traits. Show coefficients, R squared, and diagnostic plots.
6. Rank schools by residual (actual minus predicted).
7. Compare the top 10 percent and bottom 10 percent of schools on spending categories.
8. Robustness check: rerun without the largest 5 percent of schools.
9. Build the Streamlit dashboard.
10. Draft the memo and README. Include limitations: school level data, correlation only.

## Explanation rules

After the build finishes, walk me through every step in order. For each step:

* What you did, in plain language. Define any jargon.
* Why you chose this approach, and the alternatives you rejected.
* What the output means, using a real number from my results.
* What could go wrong in this step, and how you checked.
* One interview question about this step, with a strong answer.

Teach in step by step chains and explain the why behind each detail. Pause after each step and wait for me to type "next" before moving on.

## Decisions log

* Keep a decisions.md file. One line per decision: what was chosen and why.

## Accuracy

* Never invent numbers. Every number in the memo comes from code output.
* If a dataset fails to download or a column is missing, stop and tell me.

## What each part of the prompt does

1. Opening line
   * Tells Claude Code the goal (MSBA portfolio) and the order: build first, explain after.
   * The goal shapes every choice, like adding interview questions and limitations.
2. Project section
   * Gives the exact question, data sources, join key, and tools.
   * Without this, Claude Code guesses, and guesses lead to random libraries or the wrong datasets.
   * The output list defines "done," so Claude Code doesn't stop halfway.
3. Project setup
   * Creates a clean folder structure reviewers expect on GitHub.
   * Saving the prompt as CLAUDE.md means Claude Code rereads the instructions every session, so you never repeat yourself.
   * Frequent commits give you a visible work history and an undo button if something breaks.
4. Build order
   * Ten steps in sequence, matching the 8 week plan.
   * Step 3 forces Claude Code to report dropped schools. Bad joins are the most common silent error in this type of project.
   * Step 8, the robustness check, shows reviewers you tested whether your results hold up.
   * Step 10 requires limitations, which signals honesty to an admissions reader.
5. Explanation rules
   * Five parts per step: what, why, meaning, risks, interview question.
   * "Using a real number from my results" ties every explanation to your project instead of a textbook example.
   * The interview question gives you a ready answer bank.
   * "Wait for me to type next" stops a wall of text and lets you go at your pace.
6. Decisions log
   * One file with every choice and the reason.
   * Reread this file before any interview.
7. Accuracy
   * Stops Claude Code from making up figures in your memo.
   * Forces a stop if data breaks, instead of a quiet workaround.

## Working conventions (added during the build)

* Always activate the venv first: `source .venv/bin/activate`.
* Pipeline scripts live in `src/` and are numbered in build order; run them with `python src/NN_name.py` from the project root.
* `data/raw/` is gitignored. `python src/01_download.py` recreates it.
* The Scorecard's undated download URL can serve a stale file. Always download the dated file that matches the data dictionary release, and read the dictionary's `Most_Recent_Inst_Cohort_Map` sheet to find each variable's cohort year before matching other data to it.
* Review fixes (timing, spending-in-model, Carnegie, bootstrap) are logged in `decisions.md` under "Fixes after review"; `reports/archive/` keeps the pre-review ranking.
