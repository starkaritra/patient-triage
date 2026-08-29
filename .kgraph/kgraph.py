#!/usr/bin/env python3
"""
kgraph.py — Persistent Project Knowledge Graph for PatientTriage.ai.
Tracks components, data contracts, ADRs, provenance facts, and architecture.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def get_repo_root() -> Path:
    current = Path(__file__).resolve().parent.parent
    return current


class KnowledgeGraph:
    def __init__(self, file_path: Path, repo_root: Path):
        self.file_path = file_path
        self.repo_root = repo_root
        self.data: Dict[str, Any] = {
            "version": "1.0.0",
            "project": {
                "name": "PatientTriage.ai",
                "summary": "Explainable, safety-biased clinical decision-support triage system with dynamic deterioration tracking, active VOI, and audit trail.",
                "root": str(repo_root),
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
            },
            "nodes": {},
            "edges": [],
            "facts": [],
        }
        self.load()

    def load(self):
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data["version"] = loaded.get("version", "1.0.0")
                    self.data["project"] = loaded.get("project", self.data["project"])
                    self.data["nodes"] = loaded.get("nodes", {})
                    self.data["edges"] = loaded.get("edges", [])
                    self.data["facts"] = loaded.get("facts", [])
            except Exception as e:
                print(f"[kgraph] Warning: Failed to load {self.file_path}: {e}", file=sys.stderr)

    def save(self):
        self.data["project"]["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def set_project(self, name: Optional[str] = None, summary: Optional[str] = None):
        if name:
            self.data["project"]["name"] = name
        if summary:
            self.data["project"]["summary"] = summary
        self.save()

    def set_node(self, key: str, node_type: str, label: str, summary: str, file_path: Optional[str] = None):
        node = self.data["nodes"].get(key, {})
        node.update({
            "key": key,
            "type": node_type,
            "label": label,
            "summary": summary,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        })
        if file_path:
            node["file"] = file_path
        if "created_at" not in node:
            node["created_at"] = datetime.utcnow().isoformat() + "Z"
        self.data["nodes"][key] = node
        self.save()

    def delete_node(self, key: str):
        if key in self.data["nodes"]:
            del self.data["nodes"][key]
        self.data["edges"] = [e for e in self.data["edges"] if e["src"] != key and e["dst"] != key]
        self.data["facts"] = [f for f in self.data["facts"] if f.get("node") != key]
        self.save()

    def add_edge(self, src: str, dst: str, rel: str):
        for e in self.data["edges"]:
            if e["src"] == src and e["dst"] == dst and e["rel"] == rel:
                return
        self.data["edges"].append({
            "src": src,
            "dst": dst,
            "rel": rel,
            "created_at": datetime.utcnow().isoformat() + "Z",
        })
        self.save()

    def delete_edge(self, src: str, dst: str, rel: Optional[str] = None):
        self.data["edges"] = [
            e for e in self.data["edges"]
            if not (e["src"] == src and e["dst"] == dst and (rel is None or e["rel"] == rel))
        ]
        self.save()

    def add_fact(self, fact: str, source: str, node: Optional[str] = None):
        for f in self.data["facts"]:
            if f["fact"] == fact and f["source"] == source and f.get("node") == node:
                return
        self.data["facts"].append({
            "fact": fact,
            "source": source,
            "node": node,
            "created_at": datetime.utcnow().isoformat() + "Z",
        })
        self.save()

    def verify(self) -> Dict[str, Any]:
        broken_files = []
        for key, node in self.data["nodes"].items():
            if "file" in node and node["file"]:
                fpath = self.repo_root / node["file"]
                if not fpath.exists():
                    broken_files.append({"node": key, "file": node["file"]})

        broken_fact_sources = []
        for f in self.data["facts"]:
            src = f.get("source", "")
            file_part = src.split(":")[0]
            if file_part and not (self.repo_root / file_part).exists() and not file_part.startswith("http"):
                broken_fact_sources.append({"fact": f["fact"], "source": src})

        broken_edges = []
        for e in self.data["edges"]:
            if e["src"] not in self.data["nodes"] or e["dst"] not in self.data["nodes"]:
                broken_edges.append(e)

        return {
            "status": "clean" if not (broken_files or broken_fact_sources or broken_edges) else "warnings",
            "broken_files": broken_files,
            "broken_fact_sources": broken_fact_sources,
            "broken_edges": broken_edges,
            "total_nodes": len(self.data["nodes"]),
            "total_edges": len(self.data["edges"]),
            "total_facts": len(self.data["facts"]),
        }

    def scan(self, apply: bool = False) -> Dict[str, Any]:
        discovered_nodes = {}
        for path in self.repo_root.rglob("*.py"):
            rel = str(path.relative_to(self.repo_root)).replace("\\", "/")
            if any(part.startswith(".") or part in ["venv", "__pycache__", "build", "dist"] for part in path.parts):
                continue
            
            key = rel.replace("/", ".").replace(".py", "")
            if key.endswith(".__init__"):
                key = key[:-9]
            
            node_type = "module"
            if key == "app" or key.endswith("main"):
                node_type = "service"
            elif "model" in key:
                node_type = "data"
            elif "rule" in key or "engine" in key:
                node_type = "component"

            label = path.name
            summary = f"Source module at {rel}"
            discovered_nodes[key] = {
                "key": key,
                "type": node_type,
                "label": label,
                "summary": summary,
                "file": rel,
            }

        for path in self.repo_root.glob("*.md"):
            rel = path.name
            key = f"doc.{path.stem}"
            discovered_nodes[key] = {
                "key": key,
                "type": "concept",
                "label": path.name,
                "summary": f"Canonical documentation {rel}",
                "file": rel,
            }

        if apply:
            for k, n in discovered_nodes.items():
                if k not in self.data["nodes"]:
                    self.set_node(k, n["type"], n["label"], n["summary"], n.get("file"))
            self.save()

        return {
            "discovered_nodes": list(discovered_nodes.values()),
            "applied": apply,
        }

    def recall_summary(self) -> str:
        lines = []
        p = self.data["project"]
        lines.append(f"🧠 Project Knowledge Graph: {p.get('name', 'Unnamed')}")
        lines.append(f"🎯 North-Star Goal: {p.get('summary', 'None')}")
        lines.append(f"📁 Storage: {self.file_path}")
        lines.append(f"📊 Totals: {len(self.data['nodes'])} nodes | {len(self.data['edges'])} relationships | {len(self.data['facts'])} provenance facts\n")

        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for n in self.data["nodes"].values():
            t = n.get("type", "other")
            by_type.setdefault(t, []).append(n)

        type_order = ["service", "component", "interface", "data", "metric", "decision", "concept", "fact", "module"]
        sorted_types = sorted(by_type.keys(), key=lambda x: type_order.index(x) if x in type_order else 99)

        for t in sorted_types:
            nodes = by_type[t]
            lines.append(f"[{t.upper()}S] ({len(nodes)})")
            for n in nodes:
                f_info = f" -> {n['file']}" if n.get("file") else ""
                lines.append(f"  • {n['key']} ({n['label']}): {n['summary']}{f_info}")
            lines.append("")

        if self.data["edges"]:
            lines.append("[KEY RELATIONSHIPS]")
            for e in self.data["edges"]:
                lines.append(f"  • {e['src']} --[{e['rel']}]--> {e['dst']}")
            lines.append("")

        if self.data["facts"]:
            lines.append("[PROVENANCE FACTS]")
            for f in self.data["facts"]:
                n_str = f" [{f['node']}]" if f.get("node") else ""
                lines.append(f"  • \"{f['fact']}\" (src: {f['source']}){n_str}")
            lines.append("")

        return "\n".join(lines)

    def ascii_map(self, focus: Optional[str] = None, depth: int = 2) -> str:
        lines = []
        lines.append(f"=== Knowledge Map: {self.data['project'].get('name', '')} ===")
        if focus and focus in self.data["nodes"]:
            root_node = self.data["nodes"][focus]
            lines.append(f"[{root_node['type'].upper()}] {focus} ({root_node['label']})")
            lines.append(f"  Summary: {root_node['summary']}")
            lines.append("  Connections:")
            for e in self.data["edges"]:
                if e["src"] == focus:
                    dst = self.data["nodes"].get(e["dst"], {"label": e["dst"], "type": "unknown"})
                    lines.append(f"    └── [{e['rel']}] ──> {e['dst']} ({dst.get('type')}: {dst.get('label')})")
                elif e["dst"] == focus:
                    src = self.data["nodes"].get(e["src"], {"label": e["src"], "type": "unknown"})
                    lines.append(f"    ┌── [{e['rel']}] ──< {e['src']} ({src.get('type')}: {src.get('label')})")
        else:
            by_type: Dict[str, List[Dict[str, Any]]] = {}
            for n in self.data["nodes"].values():
                by_type.setdefault(n.get("type", "other"), []).append(n)
            for t, nodes in by_type.items():
                lines.append(f"├── [{t.upper()}]")
                for i, n in enumerate(nodes):
                    prefix = "│   └── " if i == len(nodes) - 1 else "│   ├── "
                    lines.append(f"{prefix}{n['key']} ({n['label']})")
        return "\n".join(lines)

    def ascii_arch(self) -> str:
        lines = []
        lines.append("=== Layered Architecture & Clinical Data Flow ===")
        lines.append("[1. Clinical UI HUD]")
        lines.append("  ▼ app (Streamlit Clinical HUD: Intake, Waiting Room Radar, Audit Log)")
        lines.append("\n[2. Core Evaluation Engines & Rules]")
        lines.append("  ▼ triage.engine (BaseTriageEngine -> AlgorithmicTriageEngine)")
        lines.append("  ▼ triage.rules (Deterministic Physiological Red-Lines: PEWS, NEWS2, qSOFA)")
        lines.append("  ▼ triage.voi (Active Value-of-Information Question Generator)")
        lines.append("\n[3. Dynamic Queue & Audit Infrastructure]")
        lines.append("  ▼ triage.queue (Deterioration Tracker, Safe Time Windows, 3x Surge Engine)")
        lines.append("  ▼ triage.audit (Immutable JSON Audit Trail & Clinician Overrides)")
        lines.append("\n[4. Data Contracts & Validation Benchmark]")
        lines.append("  • triage.models (Pydantic v2 Contracts: PatientRecord, Vitals, TriageResult)")
        lines.append("  • triage.cohort (20-Patient Multi-Age Benchmark Cohort)")
        return "\n".join(lines)

    def mermaid(self) -> str:
        lines = ["flowchart TD"]
        lines.append("  classDef service fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;")
        lines.append("  classDef component fill:#e8f5e9,stroke:#388e3c,stroke-width:2px;")
        lines.append("  classDef data fill:#fff3e0,stroke:#f57c00,stroke-width:2px;")
        lines.append("  classDef metric fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;")
        lines.append("  classDef decision fill:#fbe9e7,stroke:#d84315,stroke-width:2px;")

        for key, n in self.data["nodes"].items():
            safe_key = re.sub(r"[^a-zA-Z0-9_]", "_", key)
            label = n.get("label", key).replace('"', "'")
            t = n.get("type", "other")
            lines.append(f'  {safe_key}["{label}<br/><small>({t})</small>"]')

        for e in self.data["edges"]:
            src_safe = re.sub(r"[^a-zA-Z0-9_]", "_", e["src"])
            dst_safe = re.sub(r"[^a-zA-Z0-9_]", "_", e["dst"])
            rel = e.get("rel", "uses")
            lines.append(f"  {src_safe} -->|{rel}| {dst_safe}")

        for key, n in self.data["nodes"].items():
            safe_key = re.sub(r"[^a-zA-Z0-9_]", "_", key)
            t = n.get("type", "other")
            if t in ["service", "component", "data", "metric", "decision"]:
                lines.append(f"  class {safe_key} {t};")

        return "\n".join(lines)

    def generate_doc(self) -> str:
        lines = []
        p = self.data["project"]
        lines.append(f"# {p.get('name', 'Architecture Specification')}")
        lines.append(f"\n**North-Star Goal:** {p.get('summary', '')}\n")
        lines.append("## System Topology Diagram\n")
        lines.append("```mermaid")
        lines.append(self.mermaid())
        lines.append("```\n")
        lines.append("## Registered Components & Data Contracts\n")
        lines.append("| Key | Type | Label | Summary | Source |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for k, n in sorted(self.data["nodes"].items()):
            src = n.get("file", "-")
            lines.append(f"| `{k}` | {n.get('type')} | **{n.get('label')}** | {n.get('summary')} | `{src}` |")
        lines.append("\n## Provenance Facts & Guarantees\n")
        for f in self.data["facts"]:
            lines.append(f"- **{f['fact']}** (Source: `{f['source']}`)")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="kgraph — Project Knowledge Graph")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    subparsers.add_parser("recall", help="Recall project knowledge map")
    subparsers.add_parser("verify", help="Verify integrity of paths and edges")

    scan_p = subparsers.add_parser("scan", help="Scan codebase and discover structure")
    scan_p.add_argument("--apply", action="store_true", help="Apply discovered nodes to graph")

    proj_p = subparsers.add_parser("project", help="Set project name or summary")
    proj_p.add_argument("--name", type=str, help="Project name")
    proj_p.add_argument("--summary", type=str, help="North-star goal summary")

    node_p = subparsers.add_parser("node", help="Manage nodes")
    node_sub = node_p.add_subparsers(dest="node_cmd")
    node_set = node_sub.add_parser("set", help="Set node")
    node_set.add_argument("key", type=str, help="Node unique key")
    node_set.add_argument("--type", type=str, required=True, help="Node type")
    node_set.add_argument("--label", type=str, required=True, help="Node display label")
    node_set.add_argument("--summary", type=str, required=True, help="Node summary")
    node_set.add_argument("--file", type=str, help="Relative file path")

    node_del = node_sub.add_parser("delete", help="Delete node")
    node_del.add_argument("key", type=str, help="Node key")

    edge_p = subparsers.add_parser("edge", help="Manage edges")
    edge_sub = edge_p.add_subparsers(dest="edge_cmd")
    edge_add = edge_sub.add_parser("add", help="Add edge")
    edge_add.add_argument("src", type=str, help="Source node key")
    edge_add.add_argument("dst", type=str, help="Destination node key")
    edge_add.add_argument("--rel", type=str, required=True, help="Relationship type")

    edge_del = edge_sub.add_parser("delete", help="Delete edge")
    edge_del.add_argument("src", type=str, help="Source node key")
    edge_del.add_argument("dst", type=str, help="Destination node key")
    edge_del.add_argument("--rel", type=str, help="Relationship type")

    fact_p = subparsers.add_parser("fact", help="Manage facts")
    fact_sub = fact_p.add_subparsers(dest="fact_cmd")
    fact_add = fact_sub.add_parser("add", help="Add fact")
    fact_add.add_argument("fact", type=str, help="Fact text")
    fact_add.add_argument("--source", type=str, required=True, help="Provenance source")
    fact_add.add_argument("--node", type=str, help="Associated node key")

    map_p = subparsers.add_parser("map", help="ASCII knowledge map")
    map_p.add_argument("--focus", type=str, help="Focus node key")
    map_p.add_argument("--depth", type=int, default=2, help="Depth")

    subparsers.add_parser("arch", help="ASCII layered architecture")
    subparsers.add_parser("mermaid", help="Mermaid flowchart")
    
    doc_p = subparsers.add_parser("doc", help="Generate or update architecture.md")
    doc_p.add_argument("--output", type=str, help="Output markdown file path")

    args = parser.parse_args()

    repo_root = get_repo_root()
    storage_path = repo_root / ".kgraph" / "graph.json"
    kg = KnowledgeGraph(storage_path, repo_root)

    if args.command == "recall" or args.command is None:
        if args.json:
            print(json.dumps(kg.data, indent=2))
        else:
            print(kg.recall_summary())
    elif args.command == "verify":
        res = kg.verify()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Status: {res['status'].upper()}")
            print(f"Nodes: {res['total_nodes']} | Edges: {res['total_edges']} | Facts: {res['total_facts']}")
            if res["broken_files"]:
                print("\nBroken File References:")
                for b in res["broken_files"]:
                    print(f"  • Node '{b['node']}': {b['file']}")
            if res["broken_fact_sources"]:
                print("\nBroken Fact Sources:")
                for b in res["broken_fact_sources"]:
                    print(f"  • \"{b['fact']}\" -> {b['source']}")
            if res["broken_edges"]:
                print("\nBroken Edges:")
                for b in res["broken_edges"]:
                    print(f"  • {b['src']} -> {b['dst']}")
    elif args.command == "scan":
        res = kg.scan(apply=args.apply)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Discovered {len(res['discovered_nodes'])} nodes.")
            for n in res["discovered_nodes"]:
                print(f"  • [{n['type']}] {n['key']} ({n['label']}) -> {n.get('file')}")
            if args.apply:
                print("Applied successfully to graph.")
            else:
                print("Dry-run only. Use 'python .kgraph/kgraph.py scan --apply' to persist.")
    elif args.command == "project":
        kg.set_project(name=args.name, summary=args.summary)
        print(f"Project updated: {kg.data['project']['name']}")
    elif args.command == "node":
        if args.node_cmd == "set":
            kg.set_node(args.key, args.type, args.label, args.summary, args.file)
            print(f"Node set: {args.key}")
        elif args.node_cmd == "delete":
            kg.delete_node(args.key)
            print(f"Node deleted: {args.key}")
    elif args.command == "edge":
        if args.edge_cmd == "add":
            kg.add_edge(args.src, args.dst, args.rel)
            print(f"Edge added: {args.src} --[{args.rel}]--> {args.dst}")
        elif args.edge_cmd == "delete":
            kg.delete_edge(args.src, args.dst, args.rel)
            print(f"Edge deleted: {args.src} -> {args.dst}")
    elif args.command == "fact":
        if args.fact_cmd == "add":
            kg.add_fact(args.fact, args.source, args.node)
            print(f"Fact recorded with provenance ({args.source})")
    elif args.command == "map":
        print(kg.ascii_map(focus=args.focus, depth=args.depth))
    elif args.command == "arch":
        print(kg.ascii_arch())
    elif args.command == "mermaid":
        print(kg.mermaid())
    elif args.command == "doc":
        md = kg.generate_doc()
        if args.output:
            out_p = Path(args.output)
            out_p.write_text(md, encoding="utf-8")
            print(f"Architecture documentation written to {out_p}")
        else:
            print(md)


if __name__ == "__main__":
    main()
