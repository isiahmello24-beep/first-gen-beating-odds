"""Number trace: every number in memo/memo.md, README.md, assets/linkedin/post.md and the dashboard's hand-written text must exist in reports/results.json
at the displayed precision (a value v matches a displayed x with d decimals if round(v, d) == x or round(100 v, d) == x).

Skipped on purpose (listed when --verbose): years and fiscal/academic-year ranges, dates, URLs, file paths, code spans and fenced code,
CSS and HTML style values, and the bare integers 0, 1, 2 and 100. Everything else must trace. Exit code 1 if anything is untraced.
Run from the project root: python src/check_numbers.py [--verbose]
"""
import ast, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "reports/results.json"
TEXT_FILES = [f for f in (ROOT / "memo/memo.md", ROOT / "README.md", ROOT / "assets/linkedin/post.md") if f.exists()]
APP = ROOT / "app/app.py"
NUM = re.compile(r"(?<![\w./-])[+\-−]?\$?\d[\d,]*(?:\.\d+)?(?:%|×|x)?(?![\w/])")
YEARish = re.compile(r"^(19|20)\d\d$")
RANGEish = re.compile(r"\b(?:19|20)\d\d-\d\d-\d\d\b|(?:FY|AY)?(?:19|20)\d\d(?:-|–|to )\s?(?:\d\d|\d{4})\b|\b(?:FY|AY)\s?(?:19|20)\d\d\b|\b\d{4}-\d{2}\b")
VERSIONish = re.compile(r"Python \d\.\d+(?: or \d\.\d+)?|offer \d\.\d+|on \d\.\d+\b")
TRIVIAL = {"0", "1", "2", "100"}


def leaves(o, out):
    if isinstance(o, dict):
        for v in o.values(): leaves(v, out)
    elif isinstance(o, list):
        for v in o: leaves(v, out)
    elif isinstance(o, bool):
        return
    elif isinstance(o, (int, float)) and o is not None:
        out.append(float(o))
    elif isinstance(o, str):
        m = re.fullmatch(r"[+-]?\d+(?:\.\d+)?", o.strip())
        if m: out.append(float(o))


def strip_text(t):
    t = re.sub(r"```.*?```", " ", t, flags=re.S)             # fenced code
    t = re.sub(r"`[^`]*`", " ", t)                           # code spans
    t = re.sub(r"https?://\S+", " ", t)                      # urls
    t = re.sub(r"\S+\.(?:py|csv|md|json|parquet|png|html|txt|toml|zip)\b", " ", t)   # file names
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", t)              # images
    t = RANGEish.sub(" ", t)                                  # years, FY/AY ranges, dates
    t = VERSIONish.sub(" ", t)                                # Python versions in the deploy notes
    return t


def app_strings():
    """Hand-written literal text in app/app.py: plain string constants and the constant parts of f-strings. Computed f-string expressions are traced by construction."""
    tree = ast.parse(APP.read_text())
    inner = {id(v) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr) for v in node.values}
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            text = "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
            out.append((node.lineno, text))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in inner:
            out.append((node.lineno, node.value))
    return [(ln, s) for ln, s in out if "<style>" not in s and "@font-face" not in s and re.search(r"[A-Za-z]{3}", s)]   # CSS blocks and bare numeric tokens (font weight ranges) are not claims


def clean_app_string(s):
    s = re.sub(r"<style>.*?</style>", " ", s, flags=re.S)
    s = re.sub(r"style=\"[^\"]*\"", " ", s)                   # inline CSS
    s = re.sub(r"<[^>]+>", " ", s)                             # html tags
    s = re.sub(r"#[0-9A-Fa-f]{6}\b", " ", s)                   # hex colors
    s = re.sub(r"\d+(?:\.\d+)?(?:px|rem|em|ch)\b", " ", s)     # css units
    s = re.sub(r"%\{[^}]*\}", " ", s)                          # plotly hovertemplate fields
    s = re.sub(r"\{[^}]*\}", " ", s)                           # f-string holes / format specs
    return strip_text(s)


def numbers_in(text):
    for m in NUM.finditer(text):
        raw = m.group(0)
        s = raw.replace(",", "").replace("$", "").replace("−", "-").rstrip("%×x")
        if YEARish.match(s.lstrip("+-")): continue
        if s.lstrip("+-") in TRIVIAL and not raw.endswith(("%", "×", "x")): continue
        try: x = float(s)
        except ValueError: continue
        d = len(s.split(".")[1]) if "." in s else 0
        suffix = raw[-1] if raw.endswith(("%", "×", "x")) else ("+" if raw[0] in "+-−" else "")
        ctx = text[max(0, m.start() - 40): m.end() + 25].replace("\n", " ")
        yield raw, x, d, suffix, ctx


def traced(x, d, suffix, vals):
    """A plain integer (no decimals, no % or x) may only match an integer-valued leaf (a count or threshold), so a '15' cannot
    ride on a 0.149 somewhere in results.json. Decimals, percentages and ratios match at the displayed precision, as v or 100 v."""
    for v in vals:
        if d == 0 and not suffix:
            if v == int(v) and v == x: return True
        elif round(v, d) == round(x, d) or round(v * 100, d) == round(x, d): return True
    return False


def main():
    verbose = "--verbose" in sys.argv
    vals = []; leaves(json.loads(RES.read_text()), vals); vals = sorted(set(vals))
    bad = []; total = 0
    for f in TEXT_FILES:
        for raw, x, d, suffix, ctx in numbers_in(strip_text(f.read_text())):
            total += 1
            if not traced(abs(x), d, suffix, vals): bad.append((f.relative_to(ROOT).as_posix(), raw, ctx))
    for ln, s in app_strings():
        for raw, x, d, suffix, ctx in numbers_in(clean_app_string(s)):
            total += 1
            if not traced(abs(x), d, suffix, vals): bad.append((f"app/app.py:{ln}", raw, ctx))
    print(f"{total} numbers checked against {len(vals)} values in reports/results.json; {len(bad)} untraced")
    for where, raw, ctx in bad: print(f"  {where:18s} {raw:>8s}   …{ctx}…")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
