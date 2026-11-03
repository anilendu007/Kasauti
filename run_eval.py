"""Measures the claim checker and the translation-drift check on hand-labelled examples (eval/*.csv). Usage: python run_eval.py
The labels were written from what a careful human reviewer would say, before the checks were run. Misses are reported, not hidden."""
import csv, os, sys, tempfile, datetime as dt
from collections import Counter
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
os.environ.setdefault("KASAUTI_DB", os.path.join(tempfile.mkdtemp(), "eval.db"))
import engine as E, drift as D

def load(name): return list(csv.DictReader(open(os.path.join(here, "eval", name), encoding="utf-8")))

def evaluate():
    E.init(reset=True)
    rows, exact, planted, caught, false_alarms, false_assurance, misses = load("claims_eval.csv"), 0, 0, 0, 0, 0, []
    for r in rows:
        got = Counter(x["verdict"] for x in E.check(r["text"], use_llm=False)); exp = Counter(v for v in r["expected"].split("|") if v)
        missed, extra = exp - got, got - exp
        planted += sum(n for v, n in exp.items() if v != "Supported"); caught += sum(n for v, n in exp.items() if v != "Supported") - sum(n for v, n in missed.items() if v != "Supported")
        false_alarms += sum(n for v, n in extra.items() if v != "Supported"); false_assurance += max(0, got["Supported"] - exp["Supported"])
        if got == exp: exact += 1
        else: misses.append((r["text"], r["expected"] or "(no findings)", "|".join(sorted(got.elements())) or "(no findings)"))
    E.init(reset=True)
    d, tp, fn, fp, tn, dmiss = load("drift_eval.csv"), 0, 0, 0, 0, []
    for r in d:
        got = D.check_drift(r["english"], r["translation"])["verdict"]
        if r["expected"] == "Drift": tp, fn = tp + (got == "Drift"), fn + (got != "Drift")
        else: fp, tn = fp + (got == "Drift"), tn + (got != "Drift")
        if got != r["expected"]: dmiss.append((r["english"], r["translation"], r["expected"], got))
    return dict(n_claims=len(rows), exact=exact, planted=planted, caught=caught, false_alarms=false_alarms, false_assurance=false_assurance, misses=misses,
                n_drift=len(d), tp=tp, fn=fn, fp=fp, tn=tn, dmiss=dmiss)

def main():
    m = evaluate(); pct = lambda a, b: f"{round(100 * a / b)}%" if b else "n/a"
    out = ["# Kasauti evaluation results", "", f"Run on {dt.date.today()}. Re-run with `python run_eval.py`. Labels are in `eval/`; they were written before the checks were run.", "",
           "## Claim checker", "", f"- Labelled drafts: {m['n_claims']}; every verdict correct on {m['exact']} of them ({pct(m['exact'], m['n_claims'])})",
           f"- Planted problems (anything other than Supported): {m['planted']}; flagged correctly: {m['caught']} ({pct(m['caught'], m['planted'])})",
           f"- False alarms (a problem reported that should not be): {m['false_alarms']}", f"- False assurances (marked Supported when it should not be): {m['false_assurance']}", "",
           "| Draft | Expected | Got |", "|---|---|---|"] + [f"| {a} | {b} | {c} |" for a, b, c in m["misses"]]
    out += ["", "## Translation drift", "", f"- Labelled pairs: {m['n_drift']} ({m['tp'] + m['fn']} should drift, {m['fp'] + m['tn']} should not)",
            f"- Drift caught: {m['tp']} of {m['tp'] + m['fn']} (recall {pct(m['tp'], m['tp'] + m['fn'])}); false alarms: {m['fp']} (precision {pct(m['tp'], m['tp'] + m['fp'])})", "",
            "| English | Translation | Expected | Got |", "|---|---|---|---|"] + [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in m["dmiss"]]
    open(os.path.join(here, "EVAL_RESULTS.md"), "w", encoding="utf-8").write("\n".join(out) + "\n"); print("\n".join(out[:12]))

if __name__ == "__main__": main()
