import sys
from pathlib import Path

ROOT = Path("/Users/srichandrasamanapalli/Documents/curriculum")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine import CurriculumGraph

def find_exact_concept_ids():
    graph = CurriculumGraph.from_repo(ROOT, usable_only=True)
    queries = ["torque", "centre_of_mass", "center_of_mass", "equilibrium"]
    for q in queries:
        matches = graph.concept_ids_for_query(q)
        print(f"Query: '{q}' matched concept IDs: {matches}")

if __name__ == "__main__":
    find_exact_concept_ids()
