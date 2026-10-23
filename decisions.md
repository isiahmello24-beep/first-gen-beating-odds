# Decisions log

One line per decision: what was chosen and why.

- Project folder `firstgen-college-analysis` under home, own git repo: keeps the portfolio project self-contained and pushable to GitHub as-is.
- Python 3.14 virtual environment in `.venv` (gitignored): isolates dependencies so the project reproduces on a reviewer's machine from `requirements.txt`.
- Numbered scripts in `src/` instead of one notebook: each build step is re-runnable and reviewable on its own; notebooks are kept for exploration only.
