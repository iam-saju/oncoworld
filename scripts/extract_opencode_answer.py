#!/usr/bin/env python3
"""Recover a step's final_answer.json from a raw opencode.txt trajectory log.

test.sh's RESPONSE_FILE copy-step only runs as part of verification - a trial run with
--disable-verification never produces steps/<step>/verifier/final_answer.json at all, even though the agent
genuinely wrote its answer inside the container. This finds the last `write` tool call whose filePath matches
/app/answers/*.json in the step's agent/opencode.txt (JSON-lines format: each line has a "part" with
type=="tool", tool=="write", state.input.{filePath,content}) and saves its content to a clean file.

Deliberately prints only metadata (byte length, filePath, whether it parses as valid JSON) - never the content
itself - so this is safe to run against held-out trials without breaking their blind status.

Usage: python3 scripts/extract_opencode_answer.py <opencode.txt> <output.json>
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path


def _try_write_tool(entries: list[dict]) -> tuple[str, str] | None:
    """The common case: a dedicated `write` tool call with filePath/content."""
    found = None
    for entry in entries:
        part = entry.get("part", {})
        if part.get("type") != "tool" or part.get("tool") != "write":
            continue
        inp = part.get("state", {}).get("input", {})
        file_path = inp.get("filePath", "")
        if file_path.startswith("/app/answers/") and file_path.endswith(".json"):
            found = (file_path, inp.get("content", ""))  # last match wins - the final write for this step
    return found


def _try_bash_heredoc_python(entries: list[dict]) -> tuple[str, str] | None:
    """Fallback: some agents write a Python script via a bash heredoc instead of the `write` tool, building
    the answer dict from separate string-literal variables (e.g. q1 = "..."; out = {"q1": q1, ...}). Parses
    the heredoc as Python AST and resolves the literal values without executing anything - ast.parse() only
    builds a syntax tree, never runs the script; only Constant node values are read."""
    for entry in entries:
        part = entry.get("part", {})
        if part.get("type") != "tool" or part.get("tool") != "bash":
            continue
        cmd = part.get("state", {}).get("input", {}).get("command", "")
        if "/app/answers/" not in cmd or "<<" not in cmd:
            continue
        m = re.search(r"<<\s*['\"]?(\w+)['\"]?\s*\n", cmd)
        if not m:
            continue
        marker = m.group(1)
        body_start = m.end()
        end = cmd.find("\n" + marker, body_start)
        if end == -1:
            continue
        script = cmd[body_start:end]
        file_match = re.search(r"/app/answers/[\w.-]+\.json", cmd)
        if not file_match:
            continue
        try:
            tree = ast.parse(script)
        except SyntaxError:
            continue
        constants: dict[str, object] = {}
        out_dict_node = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for t in node.targets:
                if not isinstance(t, ast.Name):
                    continue
                if isinstance(node.value, ast.Constant):
                    constants[t.id] = node.value.value
                elif isinstance(node.value, ast.Dict) and t.id in ("out", "answer", "result", "data"):
                    out_dict_node = node.value
        if out_dict_node is None:
            continue
        resolved = {}
        for k, v in zip(out_dict_node.keys, out_dict_node.values):
            if not isinstance(k, ast.Constant):
                continue
            if isinstance(v, ast.Constant):
                resolved[k.value] = v.value
            elif isinstance(v, ast.Name) and v.id in constants:
                resolved[k.value] = constants[v.id]
        if resolved:
            return file_match.group(0), json.dumps(resolved, ensure_ascii=False)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("opencode_txt", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    entries = []
    with args.opencode_txt.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    found = _try_write_tool(entries) or _try_bash_heredoc_python(entries)
    if found is None:
        print(f"NO write to /app/answers/*.json found (tried `write` tool and bash-heredoc-python fallback) "
              f"in {args.opencode_txt}", file=sys.stderr)
        raise SystemExit(1)

    file_path, content = found
    try:
        parsed = json.loads(content)
        valid = True
        keys = list(parsed.keys()) if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        valid = False
        keys = None

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content)
    print(f"recovered {file_path} ({len(content)} bytes, valid_json={valid}, keys={keys}) -> {args.output}")


if __name__ == "__main__":
    main()
