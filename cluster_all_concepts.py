# /// script
# dependencies = [
#   "sentence-transformers",
#   "scikit-learn",
#   "pandas",
#   "numpy",
#   "matplotlib",
#   "seaborn",
# ]
# ///

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Set styles for premium aesthetics
plt.style.use('dark_background')
sns.set_theme(style="dark", palette="muted")

def main():
    print("=" * 60)
    print("ALL CONCEPTS EMBEDDING & HIERARCHICAL CLUSTERING PIPELINE")
    print("=" * 60)

    # 1. Define Paths
    base_dir = "/Users/srichandrasamanapalli/Documents/curriculum/concept csv"
    os.makedirs(base_dir, exist_ok=True)
    
    concepts_file = os.path.join(base_dir, "all_concepts.csv")
    model_dir = "/Users/srichandrasamanapalli/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181"
    
    output_embeddings = os.path.join(base_dir, "all_concepts_embeddings.npy")
    output_csv = os.path.join(base_dir, "all_concepts_agglomerative.csv")
    output_sorted_csv = os.path.join(base_dir, "all_concepts_agglomerative_sorted.csv")
    output_grouped_csv = os.path.join(base_dir, "all_concepts_agglomerative_grouped_columns.csv")
    output_simple_csv = os.path.join(base_dir, "grouped_all_concepts.csv")
    output_plot = os.path.join(base_dir, "all_concepts_clusters_agglomerative.png")

    # 2. Load Concepts
    print(f"\n[1/5] Loading concepts from: {concepts_file}")
    if not os.path.exists(concepts_file):
        print(f"Error: Concepts file not found at {concepts_file}")
        sys.exit(1)
        
    # Read using pandas to properly handle headers
    try:
        df_concepts = pd.read_csv(concepts_file)
        if "Concept" in df_concepts.columns:
            concepts = df_concepts["Concept"].str.strip().dropna().tolist()
        else:
            # Fallback to column 0
            concepts = df_concepts.iloc[:, 0].str.strip().dropna().tolist()
    except Exception as e:
        print(f"Failed to read CSV using pandas: {e}. Falling back to line-by-line reading...")
        with open(concepts_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        # Skip header if present
        if lines[0].lower() == "concept":
            concepts = lines[1:]
        else:
            concepts = lines
            
    print(f"Loaded {len(concepts)} concepts successfully.")
    print("First few concepts:")
    for idx, c in enumerate(concepts[:5]):
        print(f"  - {c}")

    # 3. Load BGE-M3 and Generate Embeddings
    print(f"\n[2/5] Loading BGE-M3 model from cache: {model_dir}")
    if not os.path.exists(model_dir):
        print(f"Error: Model directory not found at {model_dir}")
        sys.exit(1)
        
    try:
        from sentence_transformers import SentenceTransformer
        # Load local model
        model = SentenceTransformer(model_dir)
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Failed to load model from local path: {e}")
        print("Attempting to load BAAI/bge-m3 from HuggingFace directly...")
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("BAAI/bge-m3")
            print("Model loaded successfully from HF.")
        except Exception as e2:
            print(f"Failed to load model: {e2}")
            sys.exit(1)

    print("\nGenerating embeddings for concepts...")
    # BGE-M3 supports dense embeddings (normalized by default when passing normalize_embeddings=True)
    embeddings = model.encode(concepts, show_progress_bar=True, normalize_embeddings=True)
    print(f"Embeddings generated with shape: {embeddings.shape}")
    
    # Save raw embeddings
    np.save(output_embeddings, embeddings)
    print(f"Saved raw embeddings to: {output_embeddings}")

    # 4. Agglomerative Clustering (Ward Cosine Equivalent)
    print("\n[3/5] Performing Agglomerative Clustering...")
    print("Configuring: linkage='ward', metric='euclidean' (L2 normalized cosine equivalent), n_clusters=17")
    
    from sklearn.cluster import AgglomerativeClustering
    
    # We partition into 17 clusters to achieve finer curriculum categorization
    agg_model = AgglomerativeClustering(
        n_clusters=17,
        metric='euclidean',
        linkage='ward'
    )
    cluster_labels = agg_model.fit_predict(embeddings)
    unique_clusters = set(cluster_labels)
    print(f"Clustering complete! Grouped all {len(concepts)} concepts into {len(unique_clusters)} balanced clusters.")

    # Create primary assignment DataFrame
    results_df = pd.DataFrame({
        "Concept": concepts,
        "Cluster_ID": cluster_labels
    })
    results_df.to_csv(output_csv, index=False)
    print(f"  - Saved primary assignments to: {output_csv}")

    # Create Row-Sorted CSV
    df_sorted = results_df.sort_values(by=["Cluster_ID", "Concept"])
    df_sorted.to_csv(output_sorted_csv, index=False)
    print(f"  - Saved row-sorted CSV to: {output_sorted_csv}")

    # Create Column-Grouped CSV
    cluster_groups = {}
    max_len = 0
    for cid in sorted(unique_clusters):
        concepts_in_cluster = results_df[results_df["Cluster_ID"] == cid]["Concept"].sort_values().tolist()
        col_name = f"Cluster_{cid}"
        cluster_groups[col_name] = concepts_in_cluster
        max_len = max(max_len, len(concepts_in_cluster))
        
    padded_groups = {}
    for col_name, concepts_list in cluster_groups.items():
        padded_groups[col_name] = concepts_list + [""] * (max_len - len(concepts_list))
        
    df_columns = pd.DataFrame(padded_groups)
    df_columns.to_csv(output_grouped_csv, index=False)
    df_columns.to_csv(output_simple_csv, index=False)
    print(f"  - Saved column-grouped CSV to: {output_grouped_csv}")
    print(f"  - Saved simple grouped CSV duplicate to: {output_simple_csv}")

    # 5. Dimension Reduction using t-SNE
    print("\n[4/5] Running t-SNE for 2D visualization...")
    from sklearn.manifold import TSNE
    
    # Use Cosine metric for t-SNE to match our L2 normalized cosine distance space
    tsne = TSNE(
        n_components=2, 
        perplexity=min(20, len(concepts) - 1), 
        random_state=42, 
        metric='cosine'
    )
    embeddings_2d = tsne.fit_transform(embeddings)
    print(f"t-SNE projection completed.")

    # 6. Premium Data Visualization
    print("\n[5/5] Creating premium visual chart...")
    fig, ax = plt.subplots(figsize=(15, 11), dpi=300)
    
    # Dark Slate Premium Theme Styling
    ax.set_facecolor('#0f111a')
    fig.patch.set_facecolor('#0f111a')
    
    # Generate soft harmonized color palette for clusters
    colors = sns.color_palette("husl", len(unique_clusters))

    # Map labels to colors
    cluster_color_map = {cluster_id: colors[i] for i, cluster_id in enumerate(sorted(unique_clusters))}

    # Plot points
    for cid in sorted(unique_clusters):
        mask = (cluster_labels == cid)
        xs = embeddings_2d[mask, 0]
        ys = embeddings_2d[mask, 1]
        
        # Subtle gradient glow using overlapping scatters with alpha
        ax.scatter(xs, ys, color=cluster_color_map[cid], s=120, alpha=0.15, edgecolors='none')
        ax.scatter(xs, ys, color=cluster_color_map[cid], label=f'Cluster {cid}', s=75, alpha=0.85, edgecolors='w', linewidths=0.5)

    # Annotate representative concepts
    # We find the central concept for each cluster to label
    for cid in sorted(unique_clusters):
        cluster_mask = (cluster_labels == cid)
        cluster_coords = embeddings_2d[cluster_mask]
        cluster_indices = np.where(cluster_mask)[0]
        
        # Calculate cluster centroid
        centroid = np.mean(cluster_coords, axis=0)
        
        # Find point closest to centroid
        distances = np.linalg.norm(cluster_coords - centroid, axis=1)
        closest_local_idx = np.argmin(distances)
        closest_global_idx = cluster_indices[closest_local_idx]
        
        rep_concept = concepts[closest_global_idx]
        rep_x, rep_y = embeddings_2d[closest_global_idx]
        
        # Draw elegant annotation box
        ax.annotate(
            rep_concept,
            xy=(rep_x, rep_y),
            xytext=(rep_x + 0.5, rep_y + 0.5),
            textcoords='data',
            bbox=dict(boxstyle="round,pad=0.3", fc="#1c1f30", ec=cluster_color_map[cid], lw=1.5, alpha=0.85),
            color='white',
            fontsize=8,
            fontweight='bold',
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.1", color='white', alpha=0.5, lw=0.8)
        )

    # Add titles & descriptions
    plt.title("All Concepts Clusters Map (Agglomerative - Cosine Ward)", fontsize=18, color='white', fontweight='bold', pad=15)
    ax.text(
        0.5, -0.05, 
        f"Algorithm: Agglomerative (Ward Cosine Equivalent) | Model: BGE-M3 (1024D) | Projection: t-SNE | Concepts: {len(concepts)} | Clusters: {len(unique_clusters)}", 
        size=10, color='#888da8', ha="center", transform=ax.transAxes
    )
    
    # Hide grid and ticks for pure spatial look
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)

    # Format Legend
    legend = ax.legend(
        loc='upper right', 
        frameon=True, 
        facecolor='#1c1f30', 
        edgecolor='#2e344e',
        fontsize=8, 
        labelcolor='white',
        title="Clusters",
        title_fontsize=9
    )
    plt.setp(legend.get_title(), color='white')

    plt.tight_layout()
    plt.savefig(output_plot, dpi=300, facecolor='#0f111a')
    plt.close()
    
    print(f"Beautiful All Concepts cluster visualization saved to: {output_plot}")
    print("\n" + "=" * 60)
    print("PIPELINE EXECUTED SUCCESSFULLY")
    print("=" * 60)

    # Display cluster breakdown in console
    print("\nCluster Breakdown Summary:")
    for cid in sorted(unique_clusters):
        cluster_concepts = results_df[results_df['Cluster_ID'] == cid]['Concept'].tolist()
        print(f"\nCluster {cid} ({len(cluster_concepts)} concepts):")
        print(", ".join(cluster_concepts[:6]) + (", ..." if len(cluster_concepts) > 6 else ""))

if __name__ == "__main__":
    main()
