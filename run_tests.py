"""Runs every test in test_engine.py in two orders and writes TEST_LOG.md. Usage: python run_tests.py"""
import importlib.util, os, platform, sys, time, traceback, datetime as dt
here = os.path.dirname(os.path.abspath(__file__))
path = next(p for p in (os.path.join(here, "test_engine.py"), os.path.join(here, "tests", "test_engine.py")) if os.path.exists(p))
spec = importlib.util.spec_from_file_location("t", path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
names = sorted(n for n in dir(m) if n.startswith("test_"))
rows, passed, total = [], 0, 0
for label, order in (("alphabetical order", names), ("reverse order", names[::-1])):
    for n in order:
        t0 = time.time(); total += 1
        try: getattr(m, n)(); ok, note = True, ""; passed += 1
        except Exception as e: ok, note = False, f"{type(e).__name__}: {e}".replace("|", "/")[:120]; traceback.print_exc()
        rows.append((label, n, ok, time.time() - t0, note))
out = [f"# Kasauti test log", "", f"- Run on: {dt.datetime.now():%Y-%m-%d %H:%M} (local time)", f"- Python {platform.python_version()} on {platform.system()} {platform.release()}",
       f"- Tests: {len(names)} (each run twice, in alphabetical and reverse order)", f"- **Result: {passed} of {total} runs passed**", "",
       "Run it yourself: `python run_tests.py`. The tests use a temporary database, so they never touch real data.", "", "| Order | Test | Result | Seconds | Note |", "|---|---|---|---|---|"]
out += [f"| {a} | {b} | {'pass' if c else 'FAIL'} | {d:.2f} | {e} |" for a, b, c, d, e in rows]
open(os.path.join(here, "TEST_LOG.md"), "w", encoding="utf-8").write("\n".join(out) + "\n")
print(f"{passed} of {total} runs passed; wrote TEST_LOG.md"); sys.exit(0 if passed == total else 1)
