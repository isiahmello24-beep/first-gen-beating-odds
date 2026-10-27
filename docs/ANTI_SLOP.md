# Anti Slop Context: First Gen College Completion Project

Read this file before touching the dashboard, memo, README, or analysis code. Every session loads it through CLAUDE.md.

## Why this file exists

"Slop" is low quality content produced in quantity by AI. The problem is not that AI helped. The problem is output that looks finished but carries no decisions, no specifics, or wrong numbers. A reviewer who spots slop stops trusting the whole project, including the parts that are correct.

AI models drift toward the statistical average of their training data. Without constraints, you produce the average dashboard, the average memo, and the average analysis. Your job here is to replace every default with a decision you can defend.

Priority order: analysis correctness first, written claims second, charts third, visual style last. Fixing surface tells while a wrong number survives makes the slop harder to detect, not better.

## 1. Analysis slop (highest priority)

### Tells

* The metric answers a different question than the one asked. The code runs clean and the answer is wrong. Example: measuring ship to door when the question was order to door.
* Numbers in prose that no code computed. Prose around a code block is written, not computed, and nothing forces the two to agree.
* Rows silently dropped by aggregates (pandas `mean()` skips NaN) with no report of how many survived.
* Missing values treated as random when they are not. Blanks often belong to a specific group (newest records, smallest schools, suppressed cohorts).
* Grain errors: duplicate rows, one row per event treated as one row per entity.
* Trends computed on incomplete or censored records.
* Methods stacked on methods with no one line reason for each.
* Effect sizes hidden behind p values. Statistical significance presented as practical importance.
* Causal language on correlational data: "drives", "worth", "leads to", "boosts", "impact of".
* False precision: 3 decimals on a number with a 5 point uncertainty band.
* A self review pass that fixes arithmetic and approves wrong conclusions.

### Required checks for this project

1. Question to metric match. For every headline number, write the question in plain words, then read the column names in the code. Confirm they match.
2. Number trace. Every number in memo.md, README.md, and dashboard text must exist in `reports/results.json`. `src/check_numbers.py` extracts every number from those files and fails if any number lacks a match (allow rounding to the displayed precision). Run on every change.
3. Row accounting. Report n at every filter, join, and aggregate. Every chart and table shows its n.
4. Missingness test. For privacy suppressed and missing schools, compare their Pell share, size, and sector against included schools. State in the Methods tab which direction the bias likely runs.
5. Grain assertion. Assert UNITID unique after every join. Fail loudly.
6. Effect size first. Lead every finding with the size in plain units (points of graduation, dollars per student). P values go in Methods only.
7. Causal word scan. Search all prose for: drives, causes, leads to, worth, boosts, impact, effect of, results in, because of. Replace with "associated with" or "explains X% of".
8. Uncertainty visible. Rankings show bootstrap intervals. Never present rank 5 as meaningfully different from rank 9 when intervals overlap.
9. Independent check. For the 3 headline numbers, recompute in a fresh script that does not import project code. Results must match.

## 2. Written slop (memo, README, dashboard copy)

### Tells

* Significance inflation: "pivotal", "crucial", "key insight", "broader trend", "underscores".
* Promotional tone in analysis writing.
* Negative parallelism: "not just X, but Y", "this isn't about X, it's about Y".
* Rule of three lists added for rhythm, not content.
* Summary throat clearing: "In summary", "Overall", "Ultimately", "It's worth noting".
* Vague attribution: "studies show", "experts say", "some argue".
* Excessive bold, emojis, Title Case Headings, em dashes.
* Hedging stacks: "may potentially suggest".
* Boilerplate repeated under every chart with the same sentence shape.
* Workslop: polished text that hands the thinking back to the reader.

### Rules

* Every sentence carries a number, a name, or a decision. Delete sentences carrying none.
* Name schools, dollar amounts, and point gaps. "CSU Channel Islands: expected 48%, graduated 71%" beats "several schools exceed expectations."
* One idea per sentence. Short sentences. Active voice.
* State limits in one plain line each. No apologetic padding.
* "What this means" captions: write each one by hand for its chart. Vary length. If a chart needs no explanation, cut the caption. If a chart needs a caption to make sense, fix the chart first.
* No dashes of any kind in user facing text. No semicolons.
* Author voice: first person where natural ("I compared", "I set aside"). The author is Isiah Luna, a first gen transfer student at SDSU.

## 3. Chart and dashboard slop

### Tells

* Default Plotly or Streamlit theme left untouched.
* Chart titles describing the chart ("Spending by Category") instead of stating the finding.
* Legends where direct labels fit.
* Dual y axes.
* Rainbow or many color palettes with no meaning per color.
* A row of 5 or more KPI cards with equal weight.
* Truncated axes that exaggerate gaps.
* Smooth lines drawn through gaps in data.
* Inconsistent color meaning across charts.
* Decorative elements that look interactive and do nothing.
* Every panel the same size, padding, border, and radius.

### Rules

* Chart title = the finding. "Top schools spend 1.4x more on teaching" not "Spending comparison."
* One accent color, reserved for the subject of the finding (top 10% schools). Everything else neutral.
* Same color meaning on every chart. Write the mapping once in code as constants.
* Direct labels on bars and lines. Remove legends where labels fit.
* Show n on every chart. Show uncertainty where it exists.
* Bar charts start at zero. No dual axes.
* At most 3 headline numbers. The 5% stays the hero. Everything else is supporting.
* Mobile check at 375px wide: hero number visible in the first screen, no horizontal scroll, labels readable at 12px minimum.

## 4. Frontend slop

### Tells (the 2024 to 2026 AI fingerprint)

* Inter, Roboto, Open Sans, Lato, Arial, or unstyled system fonts as the primary face. Also watch for convergence on the "safe alternative" fonts models now overuse, such as Space Grotesk.
* Times New Roman everywhere reads as "styles failed to load."
* Purple to blue gradients, gradient text, glassmorphism, glow, neon on dark.
* Three equal cards with icons. Emoji used as icons.
* Centered hero with two buttons.
* Uniform border radius and shadow on every container.
* Placeholder text or names.
* Labels like "OPTIONS" or dropdown arrows with no function.

### Direction for this project

* Visual reference: newspaper data desk, editorial explainer. Warm paper background, ink text, one accent.
* Type: one distinctive serif for headlines and hero numbers, one clean sans for body and labels, tabular figures for numbers in tables. Self host the font files in `app/static/fonts` so the site works without an outside font server. Pick fonts with a reason, and write the reason in decisions.md.
* Layout: asymmetric columns. The opening row carries the whole argument: the 5% hero beside the list of large over performing schools. Everything below is subordinate.
* Separation by hairline rules and whitespace, not boxes and shadows.
* No component looks clickable unless it is.

## 5. Workflow for every session

1. Audit before editing. Write `reports/slop_audit.md` as a table: item, area (analysis, text, chart, frontend), severity 1 to 3, evidence (file and line or screenshot), fix. Severity 3 = could mislead a reader or contains a wrong number.
2. Fix severity 3 items first, then 2. Leave severity 1 unless the fix takes under 5 minutes.
3. Run `src/check_numbers.py`. It must pass.
4. Screenshot the dashboard at 375px and 1280px. Review each screenshot against section 3 and 4 tells.
5. Self critique in 5 lines: the strongest decision on the page, the weakest element, any number you did not trace, any causal word left, any caption you would cut.
6. Log every change in decisions.md with one line of reasoning.
7. Commit with a message naming the slop item fixed.

## 6. Done means

* Zero untraced numbers in user facing text.
* Zero causal words on correlational findings.
* Every chart: finding as title, n shown, consistent colors, direct labels.
* Hero number visible on first screen at 375px.
* No Inter, no default theme, no fake controls, no gradients.
* A reader learns the answer to the project question within 10 seconds of opening the dashboard.
