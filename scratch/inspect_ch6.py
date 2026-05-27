import sys
from pathlib import Path

ROOT = Path("/Users/srichandrasamanapalli/Documents/curriculum")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine import CurriculumGraph

def inspect_chapter_6():
    graph = CurriculumGraph.from_repo(ROOT, usable_only=True)
    chapter_id = "ncert:physics:11:6"
    print(f"Inspecting Chapter: {chapter_id}")
    
    # Let's count how many relationships we have in this chapter
    rels = [r for r in graph.relationships if r.get("chapter_id") == chapter_id]
    print(f"Total relationships in Chapter 6: {len(rels)}")
    
    # Print taught relations in Chapter 6
    teaches = [r for r in rels if r.get("type") == "TEACHES_CONCEPT"]
    print(f"Total TEACHES_CONCEPT in Chapter 6: {len(teaches)}")
    
    # Print the first 10 taught relations
    print("\nFirst 10 taught relations:")
    for r in teaches[:10]:
        print(f"  Section: {r.get('from_id')} teaches {r.get('to_id')}")

if __name__ == "__main__":
    inspect_chapter_6()
