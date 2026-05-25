# /// script
# dependencies = [
#   "pandas",
#   "numpy",
# ]
# ///

import os
import sys
import pandas as pd
import numpy as np

def group_dataset(input_csv, sorted_output_csv, columns_output_csv, name_prefix):
    print(f"\nProcessing {name_prefix} dataset: {input_csv}")
    if not os.path.exists(input_csv):
        print(f"Error: Input file {input_csv} not found.")
        return False
        
    # Load original clustered results
    df = pd.read_csv(input_csv)
    
    # 1. Generate Row-Sorted CSV (Sorted by Cluster ID)
    df_sorted = df.sort_values(by=["Cluster_ID", "Concept"])
    df_sorted.to_csv(sorted_output_csv, index=False)
    print(f"  - Saved sorted-row CSV to: {sorted_output_csv}")
    
    # 2. Generate Column-Grouped CSV
    # Extract unique cluster IDs sorted
    cluster_ids = sorted(df["Cluster_ID"].unique())
    
    # Construct a dictionary mapping each Cluster ID to its list of concepts
    cluster_groups = {}
    max_len = 0
    for cid in cluster_ids:
        concepts_in_cluster = df[df["Cluster_ID"] == cid]["Concept"].sort_values().tolist()
        col_name = f"Cluster_{cid}" if cid != -1 else "Noise/Outliers"
        cluster_groups[col_name] = concepts_in_cluster
        max_len = max(max_len, len(concepts_in_cluster))
        
    # Pad lists to the same length so we can create a DataFrame
    padded_groups = {}
    for col_name, concepts in cluster_groups.items():
        padded_groups[col_name] = concepts + [""] * (max_len - len(concepts))
        
    # Create column-grouped DataFrame and save
    df_columns = pd.DataFrame(padded_groups)
    df_columns.to_csv(columns_output_csv, index=False)
    print(f"  - Saved column-grouped CSV to: {columns_output_csv}")
    return True

def main():
    print("=" * 60)
    print("FORMATTING CONCEPTS GROUPED BY CLUSTER")
    print("=" * 60)

    # Paths for HDBSCAN results
    hdbscan_input = "/Users/srichandrasamanapalli/Downloads/physics_concepts_clustered.csv"
    hdbscan_sorted = "/Users/srichandrasamanapalli/Downloads/physics_concepts_hdbscan_sorted.csv"
    hdbscan_columns = "/Users/srichandrasamanapalli/Downloads/physics_concepts_hdbscan_grouped_columns.csv"

    # Paths for Agglomerative results
    agg_input = "/Users/srichandrasamanapalli/Downloads/physics_concepts_agglomerative.csv"
    agg_sorted = "/Users/srichandrasamanapalli/Downloads/physics_concepts_agglomerative_sorted.csv"
    agg_columns = "/Users/srichandrasamanapalli/Downloads/physics_concepts_agglomerative_grouped_columns.csv"

    # Run HDBSCAN grouping
    group_dataset(hdbscan_input, hdbscan_sorted, hdbscan_columns, "HDBSCAN")

    # Run Agglomerative grouping
    group_dataset(agg_input, agg_sorted, agg_columns, "Agglomerative")

    print("\n" + "=" * 60)
    print("CSV CONVERSION COMPLETED SUCCESSFULLY")
    print("=" * 60)

if __name__ == "__main__":
    main()
