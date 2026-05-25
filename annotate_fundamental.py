# /// script
# dependencies = [
#   "pandas",
# ]
# ///

import os
import pandas as pd

def main():
    print("=" * 60)
    print("ANNOTATING FUNDAMENTAL CONCEPTS IN CLUSTERS")
    print("=" * 60)

    input_csv = "/Users/srichandrasamanapalli/Downloads/physics_concepts_agglomerative_grouped_columns.csv"
    output_csv = "/Users/srichandrasamanapalli/Downloads/grouped_clusters.csv"
    backup_csv = "/Users/srichandrasamanapalli/Downloads/physics_concepts_agglomerative_grouped_columns.csv"

    if not os.path.exists(input_csv):
        print(f"Error: CSV file not found at {input_csv}")
        return

    # Load column grouped CSV
    df = pd.read_csv(input_csv)

    # Dictionary of fundamental choices for each column/cluster
    # Structure: Column Name -> (Fundamental #1, Fundamental #2)
    fundamentals = {
        "Cluster_0": ("force", "work"),
        "Cluster_1": ("atoms", "temperature"),
        "Cluster_2": ("wave propagation", "potential difference"),
        "Cluster_3": ("concept of measurement", "vectors"),
        "Cluster_4": ("energy", "conservation of energy"),
        "Cluster_5": ("first law of thermodynamics", "superposition principle"),
        "Cluster_6": ("newtons laws of motion", "gravity"),
        "Cluster_7": ("electric charge", "electric field"),
        "Cluster_8": ("magnetic field", "magnetism"),
        "Cluster_9": ("einsteins mass energy equivalence", "ideal gas equation")
    }

    # Iterate over columns and apply annotations
    for col in df.columns:
        if col in fundamentals:
            f1, f2 = fundamentals[col]
            print(f"Annotating {col}:")
            print(f"  - (1) Most Fundamental: '{f1}'")
            print(f"  - (2) Second Fundamental: '{f2}'")
            
            # Update cells
            df[col] = df[col].apply(lambda x: f"(1) {x}" if str(x).strip() == f1 
                                           else (f"(2) {x}" if str(x).strip() == f2 else x))

    # Save to both file names to ensure consistency
    df.to_csv(output_csv, index=False)
    df.to_csv(backup_csv, index=False)
    print("\n" + "=" * 60)
    print("FUNDAMENTAL CONCEPTS ANNOTATED SUCCESSFULLY")
    print("Saved files to:")
    print(f"  - {output_csv}")
    print(f"  - {backup_csv}")
    print("=" * 60)

if __name__ == "__main__":
    main()
