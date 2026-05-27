import sys
from pathlib import Path

ROOT = Path("/Users/srichandrasamanapalli/Documents/curriculum")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine import CurriculumGraph

def find_relations():
    graph = CurriculumGraph.from_repo(ROOT, usable_only=True)
    chapter_id = "ncert:physics:11:6"
    print(f"Inspecting Chapter: {chapter_id}")
    
    rels = [r for r in graph.relationships if r.get("chapter_id") == chapter_id]
    
    print("\nRelationships with 'torque':")
    for r in rels:
        from_id = str(r.get("from_id"))
        to_id = str(r.get("to_id"))
        rel_type = str(r.get("type"))
        if "torque" in from_id.lower() or "torque" in to_id.lower() or "torque" in str(r.get("source_labels")).lower():
            print(f"  {from_id} --({rel_type})--> {to_id}")
            
    print("\nRelationships with 'mass':")
    for r in rels:
        from_id = str(r.get("from_id"))
        to_id = str(r.get("to_id"))
        rel_type = str(r.get("type"))
        if "mass" in from_id.lower() or "mass" in to_id.lower() or "mass" in str(r.get("source_labels")).lower():
            print(f"  {from_id} --({rel_type})--> {to_id}")

if __name__ == "__main__":
    find_relations()
