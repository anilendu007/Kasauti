# Kasauti evaluation results

Run on 2026-11-01. Re-run with `python run_eval.py`. Labels are in `eval/`; they were written before the checks were run.

## Claim checker

- Labelled drafts: 33; every verdict correct on 31 of them (94%)
- Planted problems (anything other than Supported): 27; flagged correctly: 25 (93%)
- False alarms (a problem reported that should not be): 1
- False assurances (marked Supported when it should not be): 0

| Draft | Expected | Got |
|---|---|---|
| यह चाय 100% ऑर्गेनिक है। | Overclaim | Unsupported |
| Free delivery on all orders. | Contradicted | (no findings) |

## Translation drift

- Labelled pairs: 22 (11 should drift, 11 should not)
- Drift caught: 9 of 11 (recall 82%); false alarms: 1 (precision 90%)

| English | Translation | Expected | Got |
|---|---|---|---|
| Natural ingredients. | Sau pratishat prakritik samagri. | Drift | Consistent |
| Good for you. | Aapke liye lajawab. | Drift | Consistent |
| Three flavours. | 3 flavours. | Consistent | Drift |
