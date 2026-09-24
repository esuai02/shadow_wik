from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "intent.md"
GRAPH = ROOT / "graph.json"

REQUIRED_CRITERION_FIELDS = {
    "id", "statement", "method", "target",
    "evidence_types", "benchmark_required", "benchmark_ids",
}
ALLOWED_EVIDENCE = {"test", "measurement", "observation", "case_analysis"}
FORBIDDEN_EXECUTION_MARKERS = (
    "/api/dostk/ordr",
    "send_order(",
    "place_order(",
    "create_order(",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    errors: list[str] = []
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    intent_hash = sha256(INTENT)

    if graph.get("kind") != "execution_graph":
        errors.append("graph.kind must be execution_graph")
    if graph.get("intent_sha256") != intent_hash:
        errors.append(
            f"intent_sha256 mismatch: graph={graph.get('intent_sha256')} actual={intent_hash}"
        )

    nodes = graph.get("nodes") or []
    ids = [node.get("id") for node in nodes]
    if len(ids) != len(set(ids)):
        errors.append("duplicate graph node id")
    known = set(ids)
    if graph.get("focus") not in known:
        errors.append("graph.focus does not reference a node")

    deps: dict[str, list[str]] = {}
    criteria_ids: set[str] = set()
    for node in nodes:
        node_id = node.get("id")
        deps[node_id] = list(node.get("depends_on") or [])
        for dep in deps[node_id]:
            if dep not in known:
                errors.append(f"{node_id}: unknown dependency {dep}")

        for artifact in node.get("artifacts") or []:
            path = (ROOT / artifact).resolve()
            try:
                path.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"{node_id}: artifact escapes repository: {artifact}")
                continue
            if not path.exists():
                errors.append(f"{node_id}: missing artifact: {artifact}")

        for criterion in node.get("criteria") or []:
            missing = REQUIRED_CRITERION_FIELDS - set(criterion)
            if missing:
                errors.append(f"{node_id}: criterion missing fields {sorted(missing)}")
            cid = criterion.get("id")
            if cid in criteria_ids:
                errors.append(f"duplicate criterion id: {cid}")
            criteria_ids.add(cid)
            bad = set(criterion.get("evidence_types") or []) - ALLOWED_EVIDENCE
            if bad:
                errors.append(f"{node_id}/{cid}: unsupported evidence types {sorted(bad)}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            errors.append(f"dependency cycle at {node_id}")
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        for dep in deps.get(node_id, []):
            visit(dep)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in known:
        visit(node_id)

    scan_paths = [ROOT / "run.py", *sorted((ROOT / "src").rglob("*.py"))]
    forbidden_hits: list[str] = []
    for path in scan_paths:
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_EXECUTION_MARKERS:
            if marker in text:
                forbidden_hits.append(f"{path.relative_to(ROOT)}:{marker}")
    if forbidden_hits:
        errors.append("real-order marker found: " + ", ".join(forbidden_hits))

    result = {
        "status": "PASS" if not errors else "FAIL",
        "intent_sha256": intent_hash,
        "graph_revision": graph.get("revision"),
        "focus": graph.get("focus"),
        "nodes": len(nodes),
        "criteria": len(criteria_ids),
        "real_order_markers": forbidden_hits,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
