import sys
from pathlib import Path

ROOT = Path("/Users/srichandrasamanapalli/Documents/curriculum")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine import CurriculumGraph, CurriculumRetriever, LearnerConceptState, LearnerConceptStatus

def simulate_no_answers():
    print("Loading Curriculum Graph...")
    graph = CurriculumGraph.from_repo(ROOT, usable_only=True)
    retriever = CurriculumRetriever(graph)
    
    # 1. We start with the user's search for "gravity"
    # Target Section is ncert:physics:11:6:6.8.2 (Centre of gravity)
    target_id = "ncert:physics:11:6:6.8.2"
    print(f"\nTarget Topic: {target_id} - Centre of gravity")
    
    # 2. Define the learner state where user answered "No" (unfamiliar / misconception) to all prerequisites
    prereqs = [
        {"concept_id": "concept:centre_of_mass", "label": "Centre of Mass"},
        {"concept_id": "concept:torque", "label": "Torque"},
        {"concept_id": "concept:translational_and_rotational_equilibrium", "label": "Translational and Rotational Equilibrium"}
    ]
    
    # Simulate answering "No" by marking these concepts as MISCONCEPTION/struggling in learner state
    # This triggers the retriever to actively boost and pull in teaching sections for these concepts.
    learner_state = [
        LearnerConceptState(concept_id=p["concept_id"], status=LearnerConceptStatus.MISCONCEPTION, confidence=1.0)
        for p in prereqs
    ]
    
    print("\n--- SIMULATING USER ANSWER: 'NO' TO ALL DIAGNOSTICS ---")
    print("Marking prerequisite concepts in learner state as 'struggling'...")
    
    # 3. Query the graph to find exactly which sections teach these prerequisites
    print("\n--- DEEPER GRAPH RELATIONSHIP EXTRACTION ---")
    prereq_sections_to_add = []
    for p in prereqs:
        teaching_sections = graph.sections_teaching_concept(p["concept_id"])
        print(f"\nPrerequisite Concept: {p['label']} ({p['concept_id']})")
        if teaching_sections:
            print("  Taught by Sections:")
            for s_id in teaching_sections:
                sec_details = graph.sections_by_id.get(s_id, {})
                sum_details = graph.section_summaries_by_id.get(s_id, {})
                title = sum_details.get("title") or sec_details.get("title") or s_id
                print(f"    - {s_id} ({title})")
                if s_id not in prereq_sections_to_add:
                    prereq_sections_to_add.append(s_id)
        else:
            print("  (No direct teaching sections found in local corpus - LLM will generate self-contained explanation)")
            
    # 4. Compile the final sequence of sections that will be sent to the LLM
    print("\n--- FINAL GRAPH-SECURED SEQUENCE FOR LLM PLANNING ---")
    print("Because you answered 'No', the system expands the study list to include these foundational sections in order:")
    
    final_sequence = []
    # Add prerequisites first (Dependency order)
    for s_id in prereq_sections_to_add:
        sec_details = graph.sections_by_id.get(s_id, {})
        sum_details = graph.section_summaries_by_id.get(s_id, {})
        title = sum_details.get("title") or sec_details.get("title") or s_id
        final_sequence.append(f"{s_id} - {title} [Role: PREREQUISITE FOUNDATION]")
        
    # Add the target section at the end (Core goal)
    target_details = graph.sections_by_id.get(target_id, {})
    target_sum = graph.section_summaries_by_id.get(target_id, {})
    target_title = target_sum.get("title") or target_details.get("title") or target_id
    final_sequence.append(f"{target_id} - {target_title} [Role: CORE TARGET GOAL]")
    
    for idx, item in enumerate(final_sequence, 1):
        print(f"  Step {idx}: {item}")
        
    print("\nThis complete sequence, along with full section summaries and active teaching evidence, is now ready for the LLM!")

if __name__ == "__main__":
    simulate_no_answers()
