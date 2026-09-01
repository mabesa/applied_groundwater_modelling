"""T2 S14 -- run the matrix-evaluable components through the frozen evaluator."""
import sys, json, glob, os
sys.path.insert(0, "_SUPPORT/src")
import t1_claim_support_state as css

ARTS = "/tmp/s14_arts"
TOL = {"TOL_CONC_REL": 0.02, "TOL_TIME_REL": 0.02, "TOL_WIDTH_REL": 0.05}
HAVE_METRIC = {"peak_mgL", "t_peak"}

# --- load every artifact once -------------------------------------------------
art = {}
for p in glob.glob(f"{ARTS}/*.json"):
    if "acceptance" in p: continue
    d = json.load(open(p))
    art[os.path.basename(p)[:-5]] = d

def record(identity, metric, threshold=None):
    d = art[identity]
    h = d["run_health"]
    m = d["metrics"].get(metric)
    val = m["value"] if isinstance(m, dict) else m
    return css.RunRecord(
        run_id=d["run_identity"]["run_id"],
        axis="temporal" if identity.startswith("temporal") else "spatial",
        health=css.RunHealth(solved=h["solver_status"] == "solved",
                             provenance_valid=bool(h["provenance_valid"]),
                             horizon_censored=bool(h["horizon_censored"])),
        metric_value=None if val is None else float(val),
        decision=None if (threshold is None or val is None) else bool(float(val) > threshold),
        event_occurred=None if (threshold is None or val is None) else bool(float(val) > threshold),
        # the evaluator treats grid_spec as an OPAQUE HASHABLE identity
        # (it de-duplicates the grid series with dict.fromkeys), so the raw
        # dict must be canonicalised rather than passed through
        grid_spec=json.dumps(d["run_identity"].get("grid_spec"), sort_keys=True),
        cr_target=d["run_identity"].get("cr_target"))

# --- the components -----------------------------------------------------------
pre = json.load(open("DOCUMENTATION/contracts/T2_preregistration.json"))
comps = []
def walk(o):
    if isinstance(o, dict):
        if o.get("disposition") == "evaluated_by_matrix": comps.append(o)
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(pre)

results, skipped = [], []
for c in comps:
    if c["metric"] not in HAVE_METRIC:
        skipped.append({"id": c["id"], "metric": c["metric"],
                        "reason": "no producer emits this metric"})
        continue
    idents = [i for i in c["identities"] if i in art]
    missing = [i for i in c["identities"] if i not in art]
    claim_type = "threshold-decision" if "THRESHOLD-DECISION" in c["verdict_rule"] else "numeric"
    kw = {}
    thr = None
    if claim_type == "threshold-decision":
        # the notebook's default 1.0 mg/L compliance record, per the verdict rule
        kw["threshold_record_id"] = "notebook_default_1mgL"
        thr = 1.0
    series = [record(i, c["metric"], thr) for i in idents]
    claim = css.Claim(claim_type=claim_type, metric=c["metric"],
                      tolerance=TOL[c["tolerance"]], **kw)
    try:
        out = css.claim_support_state(claim, series, css.canonical_trend_predicate,
                                      stopping_rule="tolerance_reached")
        results.append({"id": c["id"], "metric": c["metric"], "claim_type": claim_type,
                        "n_runs": len(series), "missing_identities": missing,
                        "state": out.get("state"), "reason": out.get("reason_code"),
                        "source_path": c["source_path"]})
    except Exception as e:
        results.append({"id": c["id"], "metric": c["metric"], "claim_type": claim_type,
                        "error": f"{type(e).__name__}: {str(e)[:180]}"})

json.dump({"evaluated": results, "not_evaluable": skipped}, open(sys.argv[1], "w"), indent=1)
from collections import Counter
print(f"  evaluated    : {len(results)}")
print(f"  not evaluable: {len(skipped)}  {dict(Counter(s['metric'] for s in skipped))}")
print("  states:", dict(Counter((r.get('state') or 'ERROR') for r in results)))
errs = [r for r in results if r.get('error')]
for e in errs[:3]: print("   error:", e['id'], e['error'][:120])
print("  reasons:", dict(Counter(r.get('reason') for r in results if r.get('reason'))))
