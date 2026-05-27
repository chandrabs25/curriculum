import sys
from pathlib import Path

ROOT = Path("/Users/srichandrasamanapalli/Documents/curriculum")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from curriculum_engine import CurriculumGraph, CurriculumRetriever

def simulate():
    # Load curriculum graph
    print("Loading Curriculum Graph...")
    graph = CurriculumGraph.from_repo(ROOT, usable_only=True)
    retriever = CurriculumRetriever(graph)
    
    # Run search for gravity (without vector to keep it fast)
    results = retriever.search("gravity", limit=3, include_prerequisites=True)
    if not results:
        print("No results found.")
        return
    
    print("\n--- TOP MATCHES RETRIEVED ---")
    for idx, row in enumerate(results, 1):
        print(f"{idx}. {row.section_id} - {row.title} (Score: {row.score})")
        
    # Take top match
    top_match = results[0]
    print(f"\nAnalyzing Top Match: {top_match.section_id} - {top_match.title}")
    
    # Get required concepts for this section
    requires = graph.requires_concept_details(top_match.section_id)
    hard_edges = graph.hard_dependency_edges_for_section(top_match.section_id)
    
    if not requires and not hard_edges:
        print("No prerequisites required for this section.")
        return
        
    print("\n--- GRAPH RELATIONSHIP ANALYSIS (DEPTH EXTRACT) ---")
    
    # Output required concepts
    print("Required Concepts:")
    for req in requires:
        print(f"  - Concept ID: {req['concept_id']}")
        print(f"    Label: {req['label']}")
        print(f"    Pedagogical Reason: {req['pedagogical_reason']}")
        print(f"    Source Labels: {req['source_labels']}")
        
    # Output hard same-chapter unit dependencies
    print("\nHard Same-Chapter Section Dependencies:")
    for edge in hard_edges:
        print(f"  - Section dependency: {edge['to_section_id']} must be learned before {edge['from_section_id']}")
        print(f"    Bridge Concept: {edge['bridge_concept_id']}")
        print(f"    Reasoning: {edge['evidence_reason']}")
        
    print("\n--- COMPILED ONBOARDING DIAGNOSTIC QUESTIONS ---")
    print("To determine how deep to construct your study plan, the system asks you the following:")
    for req in requires:
        print(f"\n[Question for Concept: {req['label']}]")
        print(f"\"Are you familiar with the concept of '{req['label']}'?\"")
        print(f"Context: {req['pedagogical_reason']}")
        print("Select one:")
        print("  [ ] Yes, I know this well. (Marks as mastered; streamlines/skips prerequisite sections)")
        print("  [ ] No, I am not familiar. (Triggers deeper graph query; pulls full teaching context and summaries into LLM)")

if __name__ == "__main__":
    simulate()
