#!/usr/bin/env python3
"""Recover a step's final_answer.json from a raw opencode.txt trajectory log.

test.sh's RESPONSE_FILE copy-step only runs as part of verification - a trial run with
--disable-verification never produces steps/<step>/verifier/final_answer.json at all, even though the agent
genuinely wrote its answer inside the container. This finds the last write to /app/answers/*.json in the
step's agent/opencode.txt (JSON-lines format), trying three ways an agent may have written it, in order: a
dedicated `write` tool call (filePath/content), a bash heredoc running a hand-rolled Python script, or an
`apply_patch` tool call using the OpenAI-style "Add File" patch format - and saves its content to a clean file.

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


_ANSWER_DICT_NAMES = ("out", "answer", "result", "data", "obj")


def _resolve_literal(node: ast.AST, constants: dict[str, object]):
    """Resolve an AST node to a plain Python value without executing anything - handles the shapes seen in
    real heredoc scripts: a literal, a name referencing an already-assigned literal, parenthesized/`+`-joined
    string concatenation (e.g. ("a" "b") or ("a" + "b")), and a list of any of those. Returns a sentinel-free
    None for anything else (f-strings, function calls, ...) rather than guessing."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _resolve_literal(node.left, constants), _resolve_literal(node.right, constants)
        if isinstance(left, str) and isinstance(right, str):
            return left + right
        return None
    if isinstance(node, ast.List):
        items = [_resolve_literal(e, constants) for e in node.elts]
        return items if all(i is not None for i in items) else None
    return None


def _try_bash_heredoc_python(entries: list[dict]) -> tuple[str, str] | None:
    """Fallback: some agents write a Python script via a bash heredoc instead of the `write` tool, building
    the answer dict from separate string-literal variables (e.g. q1 = "..."; out = {"q1": q1, ...}). Parses
    the heredoc as Python AST and resolves the literal values without executing anything - ast.parse() only
    builds a syntax tree, never runs the script; only literal values are read, via _resolve_literal."""
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
                value = _resolve_literal(node.value, constants)
                if value is not None:
                    constants[t.id] = value
                if isinstance(node.value, ast.Dict) and t.id in _ANSWER_DICT_NAMES:
                    out_dict_node = node.value
        if out_dict_node is None:
            continue
        resolved = {}
        for k, v in zip(out_dict_node.keys, out_dict_node.values):
            if not isinstance(k, ast.Constant):
                continue
            value = _resolve_literal(v, constants)
            if value is not None:
                resolved[k.value] = value
        if resolved:
            return file_match.group(0), json.dumps(resolved, ensure_ascii=False)
    return None


def _apply_hunk(content_lines: list[str], hunk: list[str]) -> list[str]:
    """Apply one unified-diff-style hunk (lines prefixed ' ' context / '-' remove / '+' add, an optional
    leading '@@...' marker already stripped by the caller) to content_lines, by locating the hunk's old
    subsequence (context + removed lines) as a contiguous run and splicing in its new subsequence (context +
    added lines) in its place. Returns content_lines unchanged if the old subsequence isn't found verbatim,
    rather than guessing."""
    old_seq = [ln[1:] for ln in hunk if ln[:1] in (" ", "-")]
    new_seq = [ln[1:] for ln in hunk if ln[:1] in (" ", "+")]
    if not old_seq:
        return content_lines
    n = len(old_seq)
    for i in range(len(content_lines) - n + 1):
        if content_lines[i:i + n] == old_seq:
            return content_lines[:i] + new_seq + content_lines[i + n:]
    return content_lines  # old subsequence not found verbatim - leave content_lines as-is rather than guess


def _patch_sections(patch: str):
    """Yield (op, path, lines) for each "*** Add File: <path>" or "*** Update File: <path>" section in one
    apply_patch patchText - op is "add" (lines are the new file's content, "+"-prefix already stripped) or
    "update" (lines are one hunk, prefixes kept, for _apply_hunk)."""
    op, path, buf = None, None, []
    for ln in patch.split("\n"):
        m_add = re.match(r"\*\*\* Add File: (/app/answers/[\w.-]+\.json)\s*$", ln)
        m_upd = re.match(r"\*\*\* Update File: (/app/answers/[\w.-]+\.json)\s*$", ln)
        if m_add or m_upd:
            if op and buf:
                yield op, path, buf
            op, path, buf = ("add" if m_add else "update"), (m_add or m_upd).group(1), []
            continue
        if ln.startswith("*** "):
            if op and buf:
                yield op, path, buf
            op, path, buf = None, None, []
            continue
        if op == "add" and ln.startswith("+"):
            buf.append(ln[1:])
        elif op == "update" and ln[:1] in (" ", "-", "+"):
            buf.append(ln)
    if op and buf:
        yield op, path, buf


def _try_apply_patch(entries: list[dict]) -> tuple[str, str] | None:
    """Fallback: some agents write their answer via one or more `apply_patch` tool calls using the OpenAI-
    style "apply patch" diff format ("*** Begin Patch" / "*** Add File: <path>" + "+"-prefixed content lines,
    or "*** Update File: <path>" + a unified-diff hunk / "*** End Patch") instead of the `write` tool or a
    bash heredoc. A single answer file is often built across TWO SEPARATE tool-call entries in opencode.txt
    (one Add, one immediately-following Update that edits a field) rather than two sections in one call, so
    state is carried across entries here, not reset per entry."""
    files: dict[str, list[str]] = {}
    last_touched: str | None = None
    for entry in entries:
        part = entry.get("part", {})
        if part.get("type") != "tool" or part.get("tool") != "apply_patch":
            continue
        patch = part.get("state", {}).get("input", {}).get("patchText", "")
        if "/app/answers/" not in patch:
            continue
        for op, path, lines in _patch_sections(patch):
            if op == "add":
                files[path] = lines
            elif op == "update" and path in files:
                files[path] = _apply_hunk(files[path], lines)
            else:
                continue
            last_touched = path
    if last_touched is None:
        return None
    return last_touched, "\n".join(files[last_touched])


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

    found = _try_write_tool(entries) or _try_bash_heredoc_python(entries) or _try_apply_patch(entries)
    if found is None:
        print(f"NO write to /app/answers/*.json found (tried `write` tool, bash-heredoc-python, and "
              f"apply_patch fallbacks) in {args.opencode_txt}", file=sys.stderr)
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
