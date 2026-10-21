#!/usr/bin/env python3
"""Build a complete, timestamped event timeline for a Harbor job.

Merges every time source Harbor and OpenCode leave behind:
  job result.json              job start / end
  <trial>/result.json          trial start / end, environment_setup, agent_setup, agent_execution, verifier
  <trial>/agent/opencode.txt   per-step (= one LLM API call) start/finish, reasoning, text, tool calls, API errors
  <trial>/agent/opencode/xdg-data/opencode/log/opencode.log   OpenCode's internal log lines

Writes <job>/timeline.csv, <job>/timeline.md and <job>/timeline_summary.json, and prints the summary.

Usage: python3 scripts/job_timeline.py jobs/<job-name>
"""
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def iso(s):
    if not s:
        return None
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def ms(v):
    return datetime.fromtimestamp(v / 1000, tz=timezone.utc) if v else None


def load(p):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def trial_events(tdir: Path):
    """Yield (time, kind, name, duration_s, detail) for one trial."""
    r = load(tdir / "result.json") or {}
    if r.get("started_at"):
        yield iso(r["started_at"]), "trial", "trial_start", None, ""
    for phase in ("environment_setup", "agent_setup", "agent_execution", "verifier"):
        p = r.get(phase) or {}
        s, e = iso(p.get("started_at")), iso(p.get("finished_at"))
        if s:
            yield s, "phase", f"{phase}_start", None, ""
        if e:
            yield e, "phase", f"{phase}_end", (e - s).total_seconds() if s else None, ""
    if r.get("finished_at"):
        s, e = iso(r.get("started_at")), iso(r["finished_at"])
        yield e, "trial", "trial_end", (e - s).total_seconds() if s else None, ""

    step_start = {}  # messageID -> start time of the current step
    n_step = 0
    txt = tdir / "agent" / "opencode.txt"
    if txt.exists():
        for line in txt.read_text().splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            t, typ, part = ms(ev.get("timestamp")), ev.get("type"), ev.get("part") or {}
            if typ == "step_start":
                n_step += 1
                step_start[part.get("messageID")] = t
                yield t, "api_call", f"llm_request_{n_step}_start", None, ""
            elif typ == "step_finish":
                s = step_start.get(part.get("messageID"))
                tok = part.get("tokens") or {}
                detail = (f"reason={part.get('reason')} in={tok.get('input')} out={tok.get('output')} "
                          f"reasoning={tok.get('reasoning')} cost={part.get('cost')}")
                yield t, "api_call", f"llm_request_{n_step}_end", (t - s).total_seconds() if s else None, detail
            elif typ in ("reasoning", "text"):
                tm = part.get("time") or {}
                s, e = ms(tm.get("start")), ms(tm.get("end"))
                yield (e or t), "model_output", typ, (e - s).total_seconds() if s and e else None, f"{len(part.get('text') or '')} chars"
            elif typ == "tool_use":
                st = part.get("state") or {}
                tm = st.get("time") or {}
                s, e = ms(tm.get("start")), ms(tm.get("end"))
                inp = json.dumps(st.get("input"))[:160]
                yield (e or t), "tool_call", str(part.get("tool")), (e - s).total_seconds() if s and e else None, f"{st.get('status')} {inp}"
            elif typ == "error":
                err = ev.get("error") or {}
                data = err.get("data") or {}
                yield t, "api_error", str(err.get("name")), None, f"status={data.get('statusCode')} {str(data.get('message'))[:200]}"

    log = tdir / "agent" / "opencode" / "xdg-data" / "opencode" / "log" / "opencode.log"
    if log.exists():
        for line in log.read_text().splitlines():
            m = re.match(r"timestamp=(\S+) level=(\S+) (?:run=\S+ )?(.*)", line)
            if m:
                yield iso(m.group(1)), "opencode_log", m.group(2), None, m.group(3)[:240]

    yield from claude_session_events(tdir)


def claude_session_events(tdir: Path):
    """Claude Code session logs (<trial>/agent/sessions/projects/*/<id>.jsonl).

    One API response is split into several `assistant` entries sharing message.id. A call is timed from the entry
    before it (the prompt or the last tool_result) to its last assistant entry; a tool from its tool_use entry to
    the matching tool_result.
    """
    n_call = 0
    for sess in sorted((tdir / "agent" / "sessions" / "projects").glob("*/*.jsonl")):
        entries = []
        for line in sess.read_text().splitlines():
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("timestamp") and e.get("type") in ("user", "assistant"):
                entries.append(e)
        prev_t, calls, tool_start = None, {}, {}
        for e in entries:
            t, msg = iso(e["timestamp"]), e.get("message") or {}
            content = msg.get("content") if isinstance(msg.get("content"), list) else []
            if e["type"] == "assistant":
                c = calls.setdefault(msg.get("id"), {"start": prev_t, "end": t, "usage": msg.get("usage") or {}})
                c["end"], c["usage"] = t, msg.get("usage") or c["usage"]
                for b in content:
                    if b.get("type") == "tool_use":
                        tool_start[b.get("id")] = (t, b.get("name"), json.dumps(b.get("input"))[:160])
            else:
                for b in content:
                    if b.get("type") == "tool_result" and b.get("tool_use_id") in tool_start:
                        s, name, inp = tool_start.pop(b["tool_use_id"])
                        status = "error" if b.get("is_error") else "completed"
                        yield t, "tool_call", str(name), (t - s).total_seconds(), f"{status} {inp}"
                if e.get("isApiErrorMessage") or "error" in e:
                    yield t, "api_error", "claude_api_error", None, str(e.get("error") or content)[:200]
                prev_t = t
        for c in calls.values():
            n_call += 1
            u = c["usage"]
            if c["start"]:
                yield c["start"], "api_call", f"llm_request_{n_call}_start", None, ""
            detail = (f"in={u.get('input_tokens')} out={u.get('output_tokens')} "
                      f"cache_read={u.get('cache_read_input_tokens')} cache_write={u.get('cache_creation_input_tokens')}")
            yield c["end"], "api_call", f"llm_request_{n_call}_end", (c["end"] - c["start"]).total_seconds() if c["start"] else None, detail


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    job = Path(sys.argv[1])
    rows = []
    jr = load(job / "result.json") or {}
    if jr.get("started_at"):
        rows.append((iso(jr["started_at"]), "-", "-", "job", "job_start", None, ""))
    if jr.get("finished_at"):
        s, e = iso(jr.get("started_at")), iso(jr["finished_at"])
        rows.append((e, "-", "-", "job", "job_end", (e - s).total_seconds() if s else None, ""))

    summary = {"job": job.name, "job_seconds": rows[-1][5] if rows and rows[-1][4] == "job_end" else None, "trials": {}}
    for tdir in sorted(p for p in job.iterdir() if p.is_dir() and (p / "result.json").exists()):
        model = ((load(tdir / "config.json") or {}).get("agent") or {}).get("model_name") or "?"
        evs = list(trial_events(tdir))
        for t, kind, name, dur, detail in evs:
            if t:
                rows.append((t, tdir.name, model, kind, name, dur, detail))
        s = {"model": model, "phases": {}, "llm_calls": 0, "llm_seconds": 0.0, "tool_calls": 0, "tool_seconds": 0.0,
             "tokens": 0, "api_errors": 0}
        for t, kind, name, dur, detail in evs:
            if kind == "phase" and name.endswith("_end") and dur is not None:
                s["phases"][name[:-4]] = round(dur, 2)
            elif kind == "api_call" and name.endswith("_end"):
                s["llm_calls"] += 1
                s["llm_seconds"] += dur or 0
                s["tokens"] += sum(int(v) for v in re.findall(r"(?:in|out|reasoning)=(\d+)", detail))
            elif kind == "tool_call":
                s["tool_calls"] += 1
                s["tool_seconds"] += dur or 0
            elif kind == "api_error":
                s["api_errors"] += 1
            elif kind == "trial" and name == "trial_end":
                s["trial_seconds"] = round(dur, 2) if dur is not None else None
        s["llm_seconds"], s["tool_seconds"] = round(s["llm_seconds"], 2), round(s["tool_seconds"], 2)
        summary["trials"][tdir.name] = s

    by_model = {}
    for s in summary["trials"].values():
        b = by_model.setdefault(s["model"], {"trials": 0, "llm_calls": 0, "llm_seconds": 0.0, "tool_calls": 0,
                                             "tokens": 0, "api_errors": 0, "_t": [], "_exec": [], "_setup": []})
        b["trials"] += 1
        for k in ("llm_calls", "llm_seconds", "tool_calls", "tokens", "api_errors"):
            b[k] += s[k]
        for k, src in (("_t", s.get("trial_seconds")), ("_exec", s["phases"].get("agent_execution")),
                       ("_setup", s["phases"].get("agent_setup"))):
            if src is not None:
                b[k].append(src)
    for b in by_model.values():
        for k, out in (("_t", "mean_trial_s"), ("_exec", "mean_agent_execution_s"), ("_setup", "mean_agent_setup_s")):
            v = b.pop(k)
            b[out] = round(sum(v) / len(v), 2) if v else None
        b["llm_seconds"] = round(b["llm_seconds"], 2)
    summary["by_model"] = by_model

    rows.sort(key=lambda r: r[0])
    t0 = rows[0][0] if rows else None
    with open(job / "timeline.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "elapsed_s", "trial", "model", "kind", "event", "duration_s", "detail"])
        for t, trial, model, kind, name, dur, detail in rows:
            w.writerow([t.isoformat(), round((t - t0).total_seconds(), 3), trial, model, kind, name,
                        "" if dur is None else round(dur, 3), detail])
    with open(job / "timeline.md", "w") as f:
        f.write(f"# Timeline: {job.name}\n\n| utc | +s | trial | model | kind | event | dur s | detail |\n|---|---|---|---|---|---|---|---|\n")
        for t, trial, model, kind, name, dur, detail in rows:
            f.write(f"| {t.strftime('%H:%M:%S.%f')[:-3]} | {(t - t0).total_seconds():.2f} | {trial[:28]} | {model.split('/')[-1]} | {kind} | {name} | "
                    f"{'' if dur is None else f'{dur:.2f}'} | {detail.replace('|', '/')} |\n")
    (job / "timeline_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"\n{len(rows)} events -> {job}/timeline.csv, timeline.md, timeline_summary.json")


if __name__ == "__main__":
    main()
