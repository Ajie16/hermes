#!/usr/bin/env python3
"""
OntologyBridge - Connect memory-extract to ontology knowledge graph

Bridges the gap between memory-extract.py output (structured facts) 
and ontology.py graph (typeized knowledge entries).

Usage:
    # Extract from cron outputs and bridge to ontology
    python3 ontology_bridge.py --source ~/.hermes/cron/output/c33aac8ca375/latest.md --cycle 659
    
    # Manual fact injection
    python3 ontology_bridge.py --fact '{"type":"learning","title":"Test","description":"..."}'
    
    # Dry run (validate without writing)
    python3 ontology_bridge.py --source ~/.hermes/cron/output/xxx.md --dry-run

Workflow:
    memory-extract.py (extracted.jsonl)
        ↓
    OntologyBridge (this script)
        ↓
    ontology.py create (graph.jsonl)
        ↓
    ontology.py validate
"""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── Path Configuration ────────────────────────────────────────────────────────
# Must run from ~/.hermes/ontology/ OR provide --graph/--schema args
ONTOLOGY_SKILL_DIR = Path.home() / ".hermes" / "skills" / "ontology"
SCRIPT_DIR = ONTOLOGY_SKILL_DIR / "scripts"
GRAPH_DIR = Path.home() / ".hermes" / "ontology"
SCHEMA_PATH = GRAPH_DIR / "schema.yaml"

sys.path.insert(0, str(SCRIPT_DIR))
import ontology


# ─── Type Mapping: memory-extract → ontology types ─────────────────────────────
# memory-extract outputs: decision, preference, learning, commitment, fact
# ontology types: Skill, Learning, Error, Project, Task, Decision, Preference
TYPE_MAP = {
    "decision": "Decision",
    "preference": "Preference",
    "learning": "Learning",
    "commitment": "Task",      # commitment → Task
    "fact": "Learning",       # facts → Learning (generic insights)
    # error detection
    "error": "Error",
    "issue": "Error",
}

# Properties to extract from each fact type
PROPS_MAP = {
    "Decision": ["content", "reason", "alternatives", "source_run"],
    "Preference": ["content", "category", "source_run", "confidence"],
    "Learning": ["title", "description", "source_run", "severity", "tags"],
    "Error": ["title", "error_type", "symptoms", "root_cause", "solution", "prevention", "source_run"],
    "Task": ["title", "status", "priority", "due_date"],
    "Skill": ["name", "description", "category", "status", "source_run"],
    "Project": ["name", "description", "status", "start_date", "target_date"],
}


def generate_id(type_name: str) -> str:
    """Generate a unique entity ID."""
    prefix = type_name.lower()[:4]
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{suffix}"


def extract_facts_from_text(text: str) -> list[dict]:
    """
    Extract structured facts from raw text (markdown/diary).
    Falls back to heuristic extraction when no LLM API available.
    
    Returns list of {type, content, source_run, ...} dicts.
    """
    facts = []
    
    # Pattern: ## 20XX-MM-DD HH:MM - [经验标题]
    date_pattern = re.compile(r"## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) - (.+)")
    # Pattern: **来源**: Run #NNN
    source_pattern = re.compile(r"\*\*来源\*\*:\s*Run #(\d+)")
    # Pattern: **场景**: ...
    scenario_pattern = re.compile(r"\*\*场景\*\*:\s*(.+)")
    # Pattern: **问题/目标**: ...
    goal_pattern = re.compile(r"\*\*问题/目标\*\*:\s*(.+)")
    # Pattern: **方法/解决方案**: ...
    method_pattern = re.compile(r"\*\*方法/解决方案\*\*:\s*(.+)")
    # Pattern: **效果**: ...
    effect_pattern = re.compile(r"\*\*效果\*\*:\s*(.+)")
    # Pattern: **适用场景**: ...
    applicable_pattern = re.compile(r"\*\*适用场景\*\*:\s*(.+)")
    # Pattern: **错误现象**: ...
    error_pattern = re.compile(r"\*\*错误现象\*\*:\s*(.+)")
    # Pattern: **解决方案**: (for errors)
    sol_pattern = re.compile(r"\*\*解决方案\*\*:\s*(.+)")
    
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check for learning entry
        date_match = date_pattern.search(line)
        if date_match:
            timestamp = date_match.group(1)
            title = date_match.group(2).strip()
            
            # Look for source run in next ~10 lines
            source_run = None
            scenario = ""
            description = ""
            effect = ""
            applicable = ""
            
            for j in range(i+1, min(i+20, len(lines))):
                next_line = lines[j].strip()
                src_match = source_pattern.search(next_line)
                if src_match:
                    source_run = f"Run #{src_match.group(1)}"
                sc_match = scenario_pattern.search(next_line)
                if sc_match:
                    scenario = sc_match.group(1).strip()
                ef_match = effect_pattern.search(next_line)
                if ef_match:
                    effect = ef_match.group(1).strip()
                appl_match = applicable_pattern.search(next_line)
                if appl_match:
                    applicable = appl_match.group(1).strip()
                
                # Blank line or next heading = end of this entry
                if next_line.startswith("## ") or (not next_line and j > i+3):
                    break
            
            # Try to get description from goal/method section
            for j in range(i+1, min(i+20, len(lines))):
                next_line = lines[j].strip()
                goal_match = goal_pattern.search(next_line)
                if goal_match:
                    description = goal_match.group(1).strip()
                    break
                method_match = method_pattern.search(next_line)
                if method_match:
                    description = method_match.group(1).strip()
                    break
            
            fact = {
                "type": "learning",
                "title": title,
                "description": description or scenario or "",
                "source_run": source_run or f"Run #unknown ({timestamp})",
                "effect": effect,
                "applicable_scenarios": applicable,
            }
            facts.append(fact)
        
        # Check for error entry
        if "**错误现象**" in line or "**错误标题**" in line:
            # Try to extract error title
            error_title = ""
            error_symptoms = ""
            error_solution = ""
            error_prevention = ""
            source_run = None
            
            # Extract title from nearby context
            for j in range(max(0, i-5), i):
                prev = lines[j].strip()
                if prev.startswith("## "):
                    error_title = prev.replace("## ", "").strip()
                    break
            
            for j in range(i, min(i+25, len(lines))):
                next_line = lines[j].strip()
                src_match = source_pattern.search(next_line)
                if src_match:
                    source_run = f"Run #{src_match.group(1)}"
                err_match = error_pattern.search(next_line)
                if err_match:
                    error_symptoms = err_match.group(1).strip()
                sol_match = sol_pattern.search(next_line)
                if sol_match:
                    error_solution = sol_match.group(1).strip()
                if "**预防措施**" in next_line:
                    prevention_line = lines[j].strip()
                    error_prevention = prevention_line.replace("**预防措施**:", "").strip()
                if next_line.startswith("## ") and j > i:
                    break
            
            fact = {
                "type": "error",
                "title": error_title,
                "symptoms": error_symptoms,
                "solution": error_solution,
                "prevention": error_prevention,
                "source_run": source_run or "Run #unknown",
            }
            facts.append(fact)
        
        i += 1
    
    return facts


def extract_facts_from_jsonl(jsonl_path: str) -> list[dict]:
    """Load facts from memory-extract.py output (extracted.jsonl format)."""
    facts = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("op") == "extract" and "entity" in record:
                facts.append(record["entity"])
    return facts


def fact_to_entity(fact: dict) -> tuple[str, dict]:
    """
    Convert a fact dict to an ontology entity.
    Returns (entity_id, entity_dict).
    """
    raw_type = fact.get("type", "learning")
    ont_type = TYPE_MAP.get(raw_type, "Learning")
    
    props = {}
    for key in PROPS_MAP.get(ont_type, []):
        if key in fact:
            props[key] = fact[key]
    
    # Always set source_run if missing
    if "source_run" not in props and "source" in fact:
        props["source_run"] = fact["source"]
    
    # Generate title from content if needed
    if "title" not in props and "content" in fact:
        props["title"] = fact["content"][:100]
    
    entity_id = generate_id(ont_type)
    entity = {
        "id": entity_id,
        "type": ont_type,
        "properties": props,
        "created": datetime.now(timezone.utc).isoformat(),
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    
    return entity_id, entity


def bridge_facts(facts: list[dict], graph_path: str, dry_run: bool = False) -> list[dict]:
    """
    Process facts through OntologyBridge:
    1. Convert each fact to an ontology entity
    2. Validate against schema
    3. Write to graph.jsonl
    
    Returns list of created entities.
    """
    created = []
    
    for fact in facts:
        entity_id, entity = fact_to_entity(fact)
        
        if dry_run:
            print(f"  [DRY RUN] Would create: {entity['type']} {entity_id}")
            print(f"    title: {entity['properties'].get('title', entity['properties'].get('content', '?')[:60])}")
            created.append(entity)
            continue
        
        # Write to graph
        record = {
            "op": "create",
            "entity": entity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        with open(graph_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        
        # Try to create relation to Project "Hermes Autonomous Agent" if it exists
        try:
            proj_entities = ontology.list_entities("Project", graph_path)
            if proj_entities:
                proj_id = proj_entities[0]["id"]
                rel_type = "has_learning" if entity["type"] == "Learning" else "has_error"
                rel_record = {
                    "op": "relate",
                    "from": proj_id,
                    "rel": rel_type,
                    "to": entity_id,
                    "properties": {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                with open(graph_path, "a") as f:
                    f.write(json.dumps(rel_record, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"  Warning: Could not create relation: {e}", file=sys.stderr)
        
        created.append(entity)
        print(f"  ✓ Created {entity['type']} {entity_id}: {entity['properties'].get('title', entity['properties'].get('content', '?')[:50])}")
    
    return created


def validate_bridge_output(graph_path: str, schema_path: str) -> bool:
    """Validate the graph after bridging."""
    try:
        errors = ontology.validate_graph(graph_path, schema_path)
        if errors:
            print(f"\n⚠ Validation errors ({len(errors)}):")
            for err in errors[:5]:
                print(f"  - {err}")
            return False
        print(f"\n✓ Graph is valid ✓")
        return True
    except Exception as e:
        print(f"\n⚠ Validation failed: {e}", file=sys.stderr)
        return False


def print_stats(graph_path: str):
    """Print entity counts by type."""
    try:
        all_types = ["Skill", "Learning", "Error", "Project", "Task", "Decision", "Preference"]
        print("\n📊 Ontology Stats:")
        for etype in all_types:
            entities = ontology.list_entities(etype, graph_path)
            if entities:
                print(f"  {etype}: {len(entities)}")
    except Exception as e:
        print(f"  (Could not load stats: {e})")


def main():
    parser = argparse.ArgumentParser(description="OntologyBridge - Connect facts to knowledge graph")
    parser.add_argument("--source", "-i", help="Source file (markdown日记 or extracted.jsonl)")
    parser.add_argument("--fact", help="Single fact as JSON string")
    parser.add_argument("--cycle", type=int, help="Current run cycle number")
    parser.add_argument("--graph", "-g", default=str(GRAPH_DIR / "graph.jsonl"),
                        help=f"Graph path (default: {GRAPH_DIR}/graph.jsonl)")
    parser.add_argument("--schema", "-s", default=str(SCHEMA_PATH),
                        help=f"Schema path (default: {SCHEMA_PATH})")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing")
    parser.add_argument("--stats", action="store_true", help="Show graph stats and exit")
    args = parser.parse_args()
    
    # Change to graph directory so ontology.py relative paths work
    graph_dir = Path(args.graph).parent
    if graph_dir.exists():
        import os
        os.chdir(graph_dir)
    
    if args.stats:
        print_stats(args.graph)
        return
    
    facts = []
    
    # Load facts from source
    if args.source:
        src_path = Path(args.source).expanduser()
        if not src_path.exists():
            print(f"❌ Source file not found: {src_path}", file=sys.stderr)
            sys.exit(1)
        
        if src_path.suffix == ".jsonl":
            print(f"Loading facts from {src_path} (extracted.jsonl format)...")
            facts = extract_facts_from_jsonl(str(src_path))
        else:
            print(f"Extracting facts from {src_path} (markdown/text)...")
            text = src_path.read_text(encoding="utf-8")
            facts = extract_facts_from_text(text)
        
        print(f"  Found {len(facts)} facts")
    
    # Single fact mode
    if args.fact:
        fact = json.loads(args.fact)
        if args.cycle:
            fact["source_run"] = f"Run #{args.cycle}"
        facts.append(fact)
    
    if not facts:
        print("No facts to bridge. Use --source or --fact.")
        print("\nExample usage:")
        print("  python3 ontology_bridge.py --source ~/.hermes/cron/output/xxx.md --cycle 659")
        print("  python3 ontology_bridge.py --source extracted.jsonl")
        print("  python3 ontology_bridge.py --fact '{\"type\":\"learning\",\"title\":\"Test\"}'")
        sys.exit(1)
    
    # Bridge facts
    print(f"\n🔗 Bridging {len(facts)} facts to ontology...")
    created = bridge_facts(facts, args.graph, dry_run=args.dry_run)
    
    if not args.dry_run:
        # Validate
        validate_bridge_output(args.graph, args.schema)
    
    print_stats(args.graph)
    
    if created:
        print(f"\n✅ OntologyBridge complete: {len(created)} entities created/updated")


if __name__ == "__main__":
    main()
