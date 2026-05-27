import sys
from pathlib import Path

ROOT = Path("/Users/srichandrasamanapalli/Documents/curriculum")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine import CurriculumGraph

def inspect_teachers():
    graph = CurriculumGraph.from_repo(ROOT, usable_only=True)
    concepts = ["concept:torque", "concept:centre_of_mass"]
    for c in concepts:
        teachers = graph.sections_teaching_concept(c)
        print(f"Concept: {c} is taught by: {teachers}")

if __name__ == "__main__":
    inspect_teachers()
