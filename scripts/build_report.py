#!/usr/bin/env python3
"""Build the oncologist-facing results report for one or more Harbor runs.

Usage: python3 scripts/build_report.py jobs/<run> [jobs/<run2> ...] [--out reports/<name>.html] [--open]

Runs passed together are treated as repeated attempts of the same cases (attempt 1 = first run given). The page is
written for a clinician: plain-language criteria (cases_src/<case>/review_labels.json), patient summaries, the model's
own words quoted next to every verdict, charts per model, and review controls whose verdicts are saved (in the
published page's shared store, or in the browser plus a JSON export when opened as a local file).

Default output: reports/<first run>.html
"""
import argparse
import html
import json
import re
import sys
import tomllib
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "graders" / "oncoworld_grader"))
sys.path.insert(0, str(ROOT / "scripts"))
import grader_v2 as G  # noqa: E402

MODELS = {  # display name, how it was run; order = colour slot (colour follows the model, never its rank)
    "claude-haiku-5-5": ("Claude Haiku 5.5", "Claude Code, Anthropic API"),
    "deepseek-v4.1-flash-free": ("DeepSeek V4.1 Flash", "OpenCode, free tier"),
    "deepseek-v4.1-flash": ("DeepSeek V4.1 Flash", "OpenCode Go"),
    "minimax-m3.1-flash-free": ("MiniMax M3.1 Flash", "OpenCode, free tier"),
    "claude-opus-5-5": ("Claude Opus 5.5", "Claude Code, Anthropic API"),
    "beam-free": ("Beam", "OpenCode, free tier"),
}
DOMAINS = [  # clinical order used everywhere in the report
    ("diagnosis", "Diagnosis"),
    ("staging", "Staging"),
    ("molecular_classification", "Molecular classification"),
    ("prognosis", "Prognostic scores"),
    ("first_line_treatment", "First-line treatment"),
    ("cns_management", "CNS risk and prophylaxis"),
    ("pretreatment_workup", "Pre-treatment work-up"),
    ("supportive_care", "Supportive care"),
    ("response_assessment", "Response assessment"),
    ("fitness_and_goals", "Fitness and goals of care"),
    ("missing_information", "Missing information"),
]
FIELDS = ["diagnosis", "stage", "biology", "prognosis", "first_line_treatment", "cns_risk", "response_assessment",
          "pretreatment_workup", "supportive_care", "fitness_and_goals", "missing_information", "decisions"]


def task_dir(path: str) -> Path:
    p = ROOT / path
    moved = ROOT / "harbor_cases_narrative" / Path(path).name
    return p if p.exists() or not moved.exists() else moved


def iso(s):
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def case_of(task: str) -> str:
    m = re.match(r"(dlbcl_\d{4}|breast_\d{4})", task)
    return m.group(1) if m else task


def load_labels(case: str, rubric: dict) -> tuple[dict, dict, bool]:
    """Plain-language labels written and checked by oncologist agents; falls back to the criterion text."""
    p = ROOT / "cases_src" / case / "review_labels.json"
    if p.exists():
        d = json.loads(p.read_text())
        return d.get("case_card", {}), {i["id"]: i for i in d.get("items", [])}, True
    fallback = {}
    for it in rubric["items"]:
        t = re.sub(r"^The response\s+", "", it["text"]).rstrip(".")
        fallback[it["id"]] = {"label": t[:1].upper() + t[1:], "why": ""}
    return {}, fallback, False


def pretty(s: str) -> str:
    """A sentence from the serialised answer, as the model wrote it (no JSON key, no escapes)."""
    s = re.sub(r'^\s*"?[a-z0-9_]+"\s*:\s*"?', "", s)
    s = s.replace('\\n', " ").replace('\\"', '"').replace("\\u2013", "–").replace("\\u2014", "—")
    s = re.sub(r'"\s*,?\s*$', "", s).strip()
    return re.sub(r"\s+", " ", s)


def _clause_at(text: str, low: str, i: int, j: int) -> str:
    """The clause around a match: bounded by sentence ends, semicolons, list markers or line breaks; max ~300 chars."""
    toks = (". ", "; ", "\\n", '": "', '",', " (1)", " (2)", " (3)", " (4)", " (5)", " (6)")
    a = max([k + len(x) for x in toks for k in [low.rfind(x, 0, i)] if k >= 0] + [0])
    ends = [k for k in (low.find(x, j) for x in (". ", "; ", "\\n", '",')) if k >= 0]
    b = min(ends + [len(low)])
    a, b = max(a, i - 220), min(b + 1, j + 220)
    return pretty(text[a:b] if len(text) == len(low) else low[a:b]).lstrip(".;,:) ")


def _main_patterns(item: dict) -> list[str]:
    main = list(item.get("affirm", [])) + list(item.get("recommend", []))
    check = item.get("check")
    if check and check.startswith("affirms_"):
        main.append(G.DOUBLE_HIT if "double_hit" in check else G.DOUBLE_EXPRESSOR)
    return main


def _parts_in(item: dict, clause: str) -> tuple[int, bool, int]:
    """(main claims, any alternative, 'all' parts) that one clause carries on its own."""
    c = clause.lower()
    return (sum(bool(re.search(p, c)) for p in _main_patterns(item)),
            any(re.search(p, c) for p in item.get("any", [])),
            sum(bool(re.search(p, c)) for p in item.get("all", [])))


def _support(item: dict, clause: str) -> int:
    m, a, n = _parts_in(item, clause)
    return 2 * m + int(a) + n


def quote_support(item: dict, quotes: list[str]) -> bool:
    """False when no quoted clause carries the rule's key claim by itself (the rule matched across sentences), so the
    credit is shown as 'please check'."""
    parts = [_parts_in(item, q) for q in quotes]
    if _main_patterns(item):
        return any(m for m, _, _ in parts)
    if item.get("any"):
        return any(a for _, a, _ in parts)
    return any(n for _, _, n in parts)


def item_parts(item: dict, spec: list[dict], low: str) -> list[dict]:
    """Per-part result of a multi-part requirement, named in review_labels.json ("parts")."""
    out = []
    for p in spec:
        pats = item.get(p["rule"], [])
        if p["i"] >= len(pats):
            continue
        pat = pats[p["i"]]
        if p["rule"] == "affirm":
            ok = any(not neg and G.affirms(s, pat) for s, neg in G._mentions(low, pat))
        elif p["rule"] == "recommend":
            ok = any(G.recommends(s, pat) for s, _ in G._mentions(low, pat))
        else:
            ok = bool(re.search(pat, low))
        out.append({"label": p["label"], "met": ok})
    return out


def item_quotes(item: dict, text: str, low: str, related: bool = False) -> list[str]:
    """The clauses in the answer that decided this criterion, in the model's own capitalisation, best support first.

    related=True (for a requirement that was NOT met): the clauses that mention its parts, so a reviewer sees what the
    note did say and where it fell short.
    """
    found = []
    for p in item.get("affirm", []):
        for s, neg in G._mentions(low, p):
            if related or (not neg and G.affirms(s, p)):
                m = low.find(s)
                if m >= 0:
                    found.append((m, m + len(s)))
    for p in item.get("recommend", []):
        for s, neg in G._mentions(low, p):
            if related or G.recommends(s, p):
                m = low.find(s)
                if m >= 0:
                    found.append((m, m + len(s)))
    for key in ("any", "all"):
        for p in item.get(key, []):
            m = re.search(p, low)
            if m:
                found.append((m.start(), m.end()))
    check = item.get("check")
    if check and check.startswith("affirms_"):
        term = G.DOUBLE_HIT if "double_hit" in check else G.DOUBLE_EXPRESSOR
        for s, neg in G._mentions(low, term):
            if related or (not neg and G.affirms(s, term)):
                m = low.find(s)
                if m >= 0:
                    found.append((m, m + len(s)))
    seen, res = set(), []
    # for an unmet requirement keep rule order (the main claim, then each part)
    for i, j in (found if related else sorted(found)):
        q = _clause_at(text, low, i, j)
        if q and q not in seen and not any(q in r or r in q for r in res):
            seen.add(q)
            res.append(q[:360])
    if not related:  # a met item shows the clauses that carry most of the rule, not the first ones in the note
        res.sort(key=lambda q: -_support(item, q))
    return res[:3 if related or len(item.get("all", [])) > 1 else 2]


def not_run_reason(tdir: Path, exc: str | None) -> str:
    log = tdir / "agent" / "opencode.txt"
    if log.exists():
        for line in log.read_text().splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("type") == "error":
                data = (e.get("error") or {}).get("data") or {}
                msg, code = data.get("message", ""), data.get("statusCode")
                return (f"The model provider refused the request" + (f" (HTTP {code})" if code else "")
                        + f" before any answer was written (“{msg}”); this is not a clinical result.")
    cc = tdir / "agent" / "claude-code.txt"
    if cc.exists():
        m = re.findall(r'"result":"(API Error[^"]*)"', cc.read_text())
        if m:
            return f"The API rejected the request before any answer was written: “{m[-1][:160]}”."
    return {"AgentSetupTimeoutError": "Setting up the model's environment ran past the time limit, so the model never started.",
            "NonZeroAgentExitCodeError": "The model's program stopped with an error before writing an answer."
            }.get(exc or "", f"The trial stopped before an answer was graded ({exc or 'unknown reason'}).")


def trial_cost(tdir: Path) -> float | None:
    cc = tdir / "agent" / "claude-code.txt"
    if cc.exists():
        m = re.findall(r'"total_cost_usd":([0-9.]+)', cc.read_text())
        return round(float(m[-1]), 4) if m else None
    return 0.0 if (tdir / "agent" / "opencode.txt").exists() else None


def collect(jobs: list[Path]):
    """Single-visit trials only. Multi-step journey trials (result.json has step_results) are listed in
    collect.skipped and summarized per layer by scripts/summarize_job.py instead."""
    import rescore_job
    cases, trials, models_seen, via_seen = {}, [], [], {}
    collect.skipped = []
    for attempt, job in enumerate(jobs, 1):
        timeline = {}
        if (job / "timeline_summary.json").exists():
            timeline = json.loads((job / "timeline_summary.json").read_text()).get("trials", {})
        for tdir in sorted(p for p in job.iterdir() if (p / "result.json").exists()):
            res = json.loads((tdir / "result.json").read_text())
            if res.get("step_results"):
                collect.skipped.append(f"{job.name}/{tdir.name}")
                continue
            cfg = json.loads((tdir / "config.json").read_text())
            tpath = task_dir(cfg["task"]["path"])
            case = case_of(tpath.name)
            model = cfg["agent"].get("model_name", "?").split("/")[-1]
            if model not in models_seen:
                models_seen.append(model)
            if cfg["agent"].get("model_name", "").startswith("opencode-go/"):   # same model ids, Go endpoint
                via_seen[model] = "OpenCode Go"
            rubric_path = tpath / "tests" / "rubric_v2.toml"
            rubric = tomllib.loads(rubric_path.read_text()) if rubric_path.exists() else {"items": []}
            if case not in cases:
                card, labels, checked = load_labels(case, rubric)
                gold_p = tpath / "solution" / "final_answer.json"
                cases[case] = {"id": case, "task": tpath.name, "card": card, "labels_checked": checked,
                               "gold": json.loads(gold_p.read_text()) if gold_p.exists() else {},
                               "passing": round(rubric.get("passing_score", 0.75) * 100), "_labels": labels,
                               "format": "FHIR" if tpath.name.endswith("_fhir") else "narrative",
                               "domains": sorted({i["domain"] for i in rubric["items"]})}
            labels = cases[case]["_labels"]
            tl = timeline.get(tdir.name, {})
            ph = {}
            for k in ("environment_setup", "agent_setup", "agent_execution", "verifier"):
                p = res.get(k) or {}
                if p.get("started_at") and p.get("finished_at"):
                    ph[k] = round((iso(p["finished_at"]) - iso(p["started_at"])).total_seconds(), 1)
            t = {"key": f"{job.name}/{tdir.name}", "run": job.name, "attempt": attempt, "model": model, "case": case,
                 "timing": {"env": ph.get("environment_setup"), "install": ph.get("agent_setup"),
                            "work": ph.get("agent_execution"), "grade": ph.get("verifier"),
                            "llm_calls": tl.get("llm_calls"), "tokens": tl.get("tokens")},
                 "cost": trial_cost(tdir)}
            rev_p = tdir / "verifier" / ("rescored_review.json" if (tdir / "verifier" / "rescored_review.json").exists()
                                         else "review.json")
            exc = (res.get("exception_info") or {}).get("exception_type")
            review = json.loads(rev_p.read_text()) if rev_p.exists() else None
            if exc or not review or not review.get("items"):
                t.update(status="did_not_run", reason=not_run_reason(tdir, exc))
                trials.append(t)
                continue
            raw, _ = rescore_job.rebuild_answer(tdir)
            answer = json.loads(raw) if raw else {}
            text = G.read_response_text(raw) if raw else ""
            low = text.lower()
            by_id = {i["id"]: i for i in rubric["items"]}
            items = []
            for it in review["items"]:
                r = by_id.get(it["id"], {})
                lab = labels.get(it["id"], {})
                error = (it["kind"] == "must_not" and it["met"])
                missed = (it["kind"] != "must_not" and not it["met"])
                quotes = item_quotes(r, text, low) if (it["met"] and r) else []
                items.append({"id": it["id"], "label": lab.get("label") or it["id"], "why": lab.get("why", ""),
                              "domain": it["domain"], "kind": it["kind"], "severity": it["severity"],
                              "points": it["points"], "met": it["met"], "error": error, "missed": missed,
                              "review": bool(it.get("needs_review")), "regex": it.get("regex"), "judge": it.get("judge_met"),
                              "text": r.get("text", ""), "quotes": quotes,
                              "supported": quote_support(r, quotes) if quotes else not it["met"],
                              "parts": item_parts(r, lab["parts"], low) if (lab.get("parts") and r) else [],
                              "related": item_quotes(r, text, low, related=True) if (missed and r) else []})
            unsafe = [i["id"] for i in items if i["id"] in review.get("dangerous_errors", [])]
            t.update(status="scored", score=round(review["reward"] * 100), passed=bool(review["passed"]),
                     unsafe=unsafe, items=items, answer=answer)
            trials.append(t)
    for c in cases.values():
        c.pop("_labels", None)
    order = [m for m in MODELS if m in models_seen] + [m for m in models_seen if m not in MODELS]
    models = [{"key": m, "name": MODELS.get(m, (m, ""))[0], "via": via_seen.get(m) or MODELS.get(m, ("", "unknown"))[1], "slot": i + 1}
              for i, m in enumerate(order)]
    return cases, trials, models


def grader_validation():
    try:
        import check_rules
        import probe_rules
        tc = tcb = tp = tpb = th = thb = 0
        for _, rp, gp, ad, pp, hp in check_rules.rubric_sets():
            rub = tomllib.loads(rp.read_text())
            n, bad = check_rules.calibration(rub, json.loads(gp.read_text()), ad)
            probes = json.loads(pp.read_text()) if pp.exists() else []
            held = json.loads(hp.read_text()) if hp.exists() else []
            tc, tcb = tc + n, tcb + len(bad)
            tp, tpb = tp + len(probes), tpb + len(probe_rules.run_probes(rub, probes, quiet=True))
            th, thb = th + len(held), thb + len(probe_rules.run_probes(rub, held, quiet=True))
        return {"calibration": [tc - tcb, tc], "probes": [tp - tpb, tp], "heldout": [th - thb, th]}
    except Exception as e:  # the report still renders without these numbers
        return {"error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--title", default="OncoWorld Results")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--fragment", action="store_true",
                    help="write page content only (for publishing as a claude.ai Artifact, which adds the document skeleton)")
    args = ap.parse_args()
    cases, trials, models = collect(args.jobs)
    if collect.skipped:
        print(f"{len(collect.skipped)} multi-step journey trial(s) skipped; per-layer results: "
              f"python3 scripts/summarize_job.py {' '.join(str(j) for j in args.jobs)}")
    if not trials:
        print("no single-visit trials to report; no report written")
        return
    runs = []
    for i, j in enumerate(args.jobs, 1):
        r = json.loads((j / "result.json").read_text()) if (j / "result.json").exists() else {}
        runs.append({"name": j.name, "attempt": i, "started": r.get("started_at"), "finished": r.get("finished_at")})
    data = {
        "title": args.title,
        "generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "runs": runs, "models": models, "domains": [{"key": k, "label": v} for k, v in DOMAINS],
        "cases": sorted(cases.values(), key=lambda c: c["id"]), "trials": trials, "fields": FIELDS,
        "grader": grader_validation(),
        "labels_checked": all(c["labels_checked"] for c in cases.values()),
    }
    out = args.out or (ROOT / "reports" / f"{args.jobs[0].name}.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = (Path(__file__).with_name("report_template.html").read_text()
            .replace("__TITLE__", html.escape(args.title)).replace("__DATA__", payload))
    if not args.fragment:  # a standalone file needs its own document skeleton (no doctype = quirks mode)
        page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>'
                + page + "</body></html>")
    out.write_text(page)
    scored = sum(1 for t in trials if t["status"] == "scored")
    print(f"wrote {out} ({len(trials)} attempts, {scored} graded, {len(cases)} cases, {len(models)} models, "
          f"{out.stat().st_size // 1024} KB)")
    if args.open:
        webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
