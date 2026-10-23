#!/usr/bin/env python3
"""Build blind labelling packets for the grading truth set (one per real model answer).

Usage: python3 scripts/build_truth_packets.py jobs/<run> [jobs/<run2> ...]
Writes cases_src/truth_set/packets/<id>.json: the answer, the case context and the checklist items, WITHOUT any
grader verdict (labellers must not be anchored). Labels go to cases_src/truth_set/labels/<id>.json; the grader
verdicts are joined back in by scripts/truth_report.py.
"""
import json, sys, tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cases_src" / "truth_set" / "packets"
sys.path.insert(0, str(ROOT / "scripts"))


def context(case_dir: Path, layer: str | None) -> str:
    labels = json.loads((case_dir / "review_labels.json").read_text()) if (case_dir / "review_labels.json").exists() else {}
    card = labels.get("case_card", {})
    ctx = f"Patient: {card.get('patient', '')}\nWhat this case tests: {' | '.join(card.get('tests', []))}"
    if layer:
        j = tomllib.loads((ROOT / "cases_src/dlbcl_0003_journey/journey.toml").read_text())
        L = next(x for x in j["layers"] if x["id"] == layer)
        if L.get("documents"):
            ctx = (f"Journey stage {layer} ({L['date']}), same patient later in the disease course.\n"
                   + "\n\n".join(d["text"].strip() for d in L["documents"]) + "\n\nQuestions: " + " | ".join(L["questions"]))
    return ctx


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for job in (Path(a).resolve() for a in sys.argv[1:]):
        for tdir in sorted(p for p in job.iterdir() if (p / "result.json").exists()):
            res = json.loads((tdir / "result.json").read_text())
            model = ((res.get("config") or {}).get("agent") or {}).get("model_name", "?").split("/")[-1]
            task = Path(res["config"]["task"]["path"]).name
            if res.get("step_results"):
                units = [(f"{s['step_name'][:2]}", tdir / "steps" / s["step_name"] / "verifier", s["step_name"]) for s in res["step_results"]]
            else:
                units = [(None, tdir / "verifier", None)]
            for layer, vdir, step in units:
                ans = vdir / "final_answer.json"
                if ans.exists():
                    answer = json.loads(ans.read_text())
                elif layer is None:   # older runs: rebuild the answer from the agent's own logs
                    import rescore_job
                    raw, _src = rescore_job.rebuild_answer(tdir)
                    if not raw:
                        continue
                    try:
                        answer = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                else:
                    continue
                if layer and layer != "L1":
                    rubric = ROOT / f"cases_src/dlbcl_0003_journey/{layer}_rubric.toml"; case_dir = ROOT / "cases_src/dlbcl_0003"
                else:
                    case = task.split("_v2")[0][:10] if not task.startswith("dlbcl_0003_journey") else "dlbcl_0003"
                    case_dir = ROOT / "cases_src" / case; rubric = case_dir / "rubric_v2.toml"
                items = [{"id": i["id"], "kind": i["kind"], "severity": i["severity"], "points": i["points"], "criterion": i["text"]}
                         for i in tomllib.loads(rubric.read_text())["items"]]
                pid = f"{job.name}__{tdir.name.split('__')[-1]}" + (f"__{layer}" if layer else "")
                (OUT / f"{pid}.json").write_text(json.dumps({
                    "id": pid, "model": model, "task": task, "layer": layer, "rubric": str(rubric.relative_to(ROOT)),
                    "answer_path": str(ans.relative_to(ROOT)) if ans.exists() else f"{tdir.relative_to(ROOT)} (rebuilt from agent logs)", "context": context(case_dir, layer if layer != "L1" else None),
                    "answer": answer, "items": items}, indent=1, ensure_ascii=False))
                n += 1
    print(f"{n} packets -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
