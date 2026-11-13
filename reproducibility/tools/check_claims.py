"""Check every number in a text against registered claims and their source files.

AI-assisted tool (Claude, 9 November 2026). It checks that numbers agree with
saved outputs; it does not judge whether an interpretation is right.

Usage:
  python tools/check_claims.py --text notes.txt --claims tools/claims/claims_study_notes.json \
      --output results/claims-check-001

Each claim in the claims file names one value and where it comes from:
  csv      a cell (or the min/max of a column) in a CSV file
  json     a value at a path in a JSON file, or a count of list items
  sqlite   one value returned by a read-only SQL query
  regex    a number captured from a text or code file
  expr     arithmetic on other claims (+ - * / ** and exp, sin, cos, tan, atan, sqrt, min, max)
  external a value from an outside document; reported, never auto-verified

Every number found in the text gets one status:
  matched     a repository claim whose keyword is in the sentence has this value
  external    only an external claim matches; check that source by hand
  unverified  no registered claim matches; nobody has checked it
A claim with "anchors" is reported MISMATCHED when a sentence contains all its
anchors but none of its numbers equals the claim's value.
Values match when they agree to the number of decimals written in the text.
"""
from __future__ import annotations

import argparse
import ast
import csv
import gzip
import json
import math
import re
import sqlite3
import sys
from pathlib import Path

SUPER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
SCI = re.compile(r"(\d+(?:\.\d+)?)\s*[×x]\s*10\s*([⁻\-−]?[⁰¹²³⁴⁵⁶⁷⁸⁹\d]+)")
NUMBER = re.compile(r"(?<![\w.\-/])[−\-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w])")
SKIP = [re.compile(p, re.I) for p in (
    r"https?://\S+", r"\[[\d,\s–\-]+\]", r"\bref(?:erence)?s?\s*\[?\d+\]?",
    r"\b(?:section|sections|eq|eqs|equation|table|tables|fig|figure|figures|comment|comments|point|step|part|version|v)\.?\s*\d+(?:\.\d+)?(?:\s*(?:and|,|–|-)\s*\d+(?:\.\d+)?)*",
    r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}\b",
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}\b",
    r"\b(?:19|20)\d{2}\b", r"^\s*\d+\.\s", r"\b[\w./-]+\.(?:py|json|csv|gz|md|hsmdb|mat|txt|pdf)\b")]
SAFE_FUNCS = {"exp": math.exp, "sin": math.sin, "cos": math.cos, "tan": math.tan,
              "atan": math.atan, "sqrt": math.sqrt, "abs": abs, "min": min, "max": max}


class ClaimError(ValueError):
    pass


def safe_eval(expr: str, names: dict) -> float:
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in names:
                raise ClaimError(f"unknown name {node.id!r} in expr")
            return names[node.id]
        if isinstance(node, ast.BinOp):
            ops = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
                   ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b}
            if type(node.op) in ops:
                return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in SAFE_FUNCS:
            return SAFE_FUNCS[node.func.id](*[ev(a) for a in node.args])
        raise ClaimError(f"unsupported expression part: {ast.dump(node)[:60]}")
    return float(ev(ast.parse(expr, mode="eval")))


def read_rows(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def json_path(obj, path):
    for key in path:
        obj = obj[key]
    return obj


def matches_where(item, where):
    return all(str(json_path(item, k.split("."))) == str(v) for k, v in where.items())


def resolve(claim: dict, base: Path, done: dict) -> float | None:
    src = claim["source"]
    kind = src["kind"]
    if kind == "external":
        return float(claim["value"])
    if kind == "expr":
        return safe_eval(src["expr"], done)
    path = base / src["file"]
    if not path.is_file():
        raise ClaimError(f"source file missing: {src['file']}")
    if kind == "csv":
        rows = [r for r in read_rows(path) if all(r[k] == str(v) for k, v in src.get("where", {}).items())]
        values = [float(r[src["column"]]) for r in rows]
        if not values:
            raise ClaimError("no CSV row matched")
        agg = src.get("agg")
        if agg in ("min", "max", "sum"):
            return {"min": min, "max": max, "sum": sum}[agg](values)
        if len(values) != 1:
            raise ClaimError(f"{len(values)} CSV rows matched; add 'where' or 'agg'")
        return values[0]
    if kind == "json":
        data = json_path(json.loads(path.read_text(encoding="utf-8")), src.get("path", []))
        if "count_where" in src:
            return float(sum(1 for item in data if matches_where(item, src["count_where"])))
        return float(data)
    if kind == "sqlite":
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as con:
            row = con.execute(src["sql"]).fetchone()
        if row is None or row[0] is None:
            raise ClaimError("SQL returned no value")
        return float(row[0])
    if kind == "regex":
        found = re.search(src["pattern"], path.read_text(encoding="utf-8"))
        if not found:
            raise ClaimError("pattern not found")
        return float(found.group(1))
    raise ClaimError(f"unknown source kind {kind!r}")


def resolve_all(claims: list[dict], base: Path) -> dict:
    done, errors, pending = {}, {}, list(claims)
    while pending:
        progressed = False
        for claim in list(pending):
            try:
                value = resolve(claim, base, done)
            except ClaimError as exc:
                if claim["source"]["kind"] == "expr" and "unknown name" in str(exc):
                    continue
                errors[claim["id"]] = str(exc)
                pending.remove(claim)
                progressed = True
                continue
            done[claim["id"]] = value * claim.get("scale", 1.0)
            pending.remove(claim)
            progressed = True
        if not progressed:
            for claim in pending:
                errors[claim["id"]] = "expr refers to an unresolved claim"
            break
    return {"values": done, "errors": errors}


def parse_number(token: str) -> tuple[float, int]:
    token = token.replace("−", "-").replace(",", "")
    decimals = len(token.split(".")[1]) if "." in token else 0
    return float(token), decimals


def find_numbers(sentence: str):
    masked = sentence
    found = []
    for m in SCI.finditer(sentence):
        mant, exp = m.group(1), m.group(2).translate(SUPER).replace("−", "-")
        decimals = len(mant.split(".")[1]) if "." in mant else 0
        found.append((m.group(0), float(mant) * 10 ** int(exp), decimals - int(exp)))
        masked = masked.replace(m.group(0), " " * len(m.group(0)))
    for pattern in SKIP:
        masked = pattern.sub(lambda m: " " * len(m.group(0)), masked)
    for m in NUMBER.finditer(masked):
        value, decimals = parse_number(m.group(0))
        found.append((m.group(0), value, decimals))
    return found


def agrees(text_value: float, decimals: int, true_value: float) -> bool:
    """True when the source value rounds to the text value at the decimals written."""
    tol = 0.5 * 10 ** (-decimals) * (1 + 1e-9)
    return abs(text_value - true_value) <= tol


def split_sentences(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("|"):
            out.append(line)
        else:
            out.extend(s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", line) if s.strip())
    return out


def check(text: str, claims: list[dict], values: dict, ignore: list[str] = ()) -> tuple[list[dict], list[dict]]:
    """Ignore patterns mask structural numbers (section, row, comment numbers) before scanning."""
    rows, mismatches = [], []
    masks = [re.compile(p, re.M) for p in ignore]
    for sentence in split_sentences(text):
        low = sentence.lower()
        scanned = sentence
        for mask in masks:
            scanned = mask.sub(lambda m: " " * len(m.group(0)), scanned)
        numbers = find_numbers(scanned)
        hit_claims = set()
        for token, value, decimals in numbers:
            repo, ext = [], []
            for claim in claims:
                cid = claim["id"]
                if cid not in values or not any(k.lower() in low for k in claim["keywords"]):
                    continue
                if agrees(value, decimals, values[cid]):
                    (ext if claim["source"]["kind"] == "external" else repo).append(cid)
            status = "matched" if repo else "external" if ext else "unverified"
            hit_claims.update(repo + ext)
            rows.append({"status": status, "number": token, "claims": ";".join(repo or ext), "sentence": sentence})
        for claim in claims:
            anchors = claim.get("anchors")
            if anchors and claim["id"] in values and claim["id"] not in hit_claims \
                    and all(a.lower() in low for a in anchors) and numbers:
                mismatches.append({"claim": claim["id"], "expected": values[claim["id"]],
                                   "numbers_in_sentence": ", ".join(n[0] for n in numbers), "sentence": sentence})
    return rows, mismatches


def write_report(out: Path, text_path: Path, claims: list[dict], resolved: dict, rows: list, mismatches: list):
    out.mkdir(parents=True)
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in ("matched", "external", "unverified")}
    with open(out / "CLAIMS_REPORT.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["status", "number", "claims", "sentence"])
        writer.writeheader()
        writer.writerows(rows)
    by_id = {c["id"]: c for c in claims}
    lines = ["# Claims report", "",
             f"Text checked: `{text_path}`. Numbers found: {len(rows)}.", "",
             f"- **Matched to repository outputs:** {counts['matched']}",
             f"- **External source only (check by hand):** {counts['external']}",
             f"- **Unverified (no registered claim):** {counts['unverified']}",
             f"- **Mismatched claims:** {len(mismatches)}",
             f"- **Claims that could not be resolved:** {len(resolved['errors'])}", ""]
    lines += ["## Mismatched", ""] + ([f"- `{m['claim']}` expected {m['expected']:.6g}; sentence has {m['numbers_in_sentence']}: {m['sentence'][:200]}" for m in mismatches] or ["None."]) + [""]
    if resolved["errors"]:
        lines += ["## Claims that could not be resolved", ""] + [f"- `{k}`: {v}" for k, v in resolved["errors"].items()] + [""]
    for status, title in (("unverified", "Unverified numbers"), ("external", "External-source numbers")):
        lines += [f"## {title}", "", "| Number | Sentence |", "| --- | --- |"]
        lines += [f"| {r['number']} | {r['sentence'][:180].replace('|', '/')} |" for r in rows if r["status"] == status] or ["| — | none |"]
        lines.append("")
    lines += ["## Matched numbers", "", "| Number | Claim | Source |", "| --- | --- | --- |"]
    for r in rows:
        if r["status"] == "matched":
            cid = r["claims"].split(";")[0]
            src = by_id[cid]["source"]
            where = src.get("file") or src.get("expr")
            lines.append(f"| {r['number']} | `{cid}` | `{where}` |")
    lines += ["", "## Claim values used", "", "| Claim | Value | Kind | Label |", "| --- | --- | --- | --- |"]
    lines += [f"| `{c['id']}` | {resolved['values'].get(c['id'], 'ERROR')} | {c['source']['kind']} | {c.get('label', '')} |" for c in claims]
    (out / "CLAIMS_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--text", required=True, type=Path, help="Plain text or Markdown to check")
    parser.add_argument("--claims", required=True, type=Path, help="Claims JSON file")
    parser.add_argument("--base", type=Path, default=Path.cwd(), help="Folder that source paths are relative to")
    parser.add_argument("--output", required=True, type=Path, help="New folder for the report")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output folder already exists: {args.output}")
    spec = json.loads(args.claims.read_text(encoding="utf-8"))
    claims = spec["claims"]
    ids = [c["id"] for c in claims]
    if len(ids) != len(set(ids)):
        parser.error("duplicate claim ids")
    resolved = resolve_all(claims, args.base)
    rows, mismatches = check(args.text.read_text(encoding="utf-8"), claims, resolved["values"],
                             spec.get("ignore_patterns", []))
    counts = write_report(args.output, args.text, claims, resolved, rows, mismatches)
    print(f"{len(rows)} numbers: {counts['matched']} matched, {counts['external']} external, "
          f"{counts['unverified']} unverified; {len(mismatches)} mismatched; "
          f"{len(resolved['errors'])} unresolved claims -> {args.output / 'CLAIMS_REPORT.md'}")
    return 1 if mismatches or resolved["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
