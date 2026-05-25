# /// script
# dependencies = [
#   "sentence-transformers",
#   "scikit-learn",
#   "pandas",
#   "numpy",
#   "matplotlib",
#   "seaborn",
#   "hdbscan",
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
    print("PHYSICS CONCEPT EMBEDDING & HDBSCAN CLUSTERING PIPELINE")
    print("=" * 60)

    # 1. Define Paths
    concepts_file = "/Users/srichandrasamanapalli/Downloads/physics_concept_names.csv"
    model_dir = "/Users/srichandrasamanapalli/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181"
    
    output_embeddings = "/Users/srichandrasamanapalli/Downloads/physics_concept_embeddings.npy"
    output_csv = "/Users/srichandrasamanapalli/Downloads/physics_concepts_clustered.csv"
    output_plot = "/Users/srichandrasamanapalli/Downloads/physics_clusters_visualization.png"

    # 2. Load Concepts
    print(f"\n[1/5] Loading physics concepts from: {concepts_file}")
    if not os.path.exists(concepts_file):
        print(f"Error: Concepts file not found at {concepts_file}")
        sys.exit(1)
        
    with open(concepts_file, 'r', encoding='utf-8') as f:
        concepts = [line.strip() for line in f if line.strip()]
    
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
    # BGE-M3 supports dense embeddings (and sparse/colbert, but we need dense for HDBSCAN clustering)
    embeddings = model.encode(concepts, show_progress_bar=True, normalize_embeddings=True)
    print(f"Embeddings generated with shape: {embeddings.shape}")
    
    # Save raw embeddings
    np.save(output_embeddings, embeddings)
    print(f"Saved raw embeddings to: {output_embeddings}")

    # 4. HDBSCAN Clustering
    print("\n[3/5] Performing HDBSCAN Clustering...")
    
    # Try importing hdbscan, fallback to sklearn's HDBSCAN if needed
    hdbscan_model = None
    cluster_labels = None
    probabilities = None
    outlier_scores = None

    try:
        import hdbscan
        print("Using standalone hdbscan package...")
        # Since 160 elements is quite small, let's use min_cluster_size=3, min_samples=2
        hdbscan_model = hdbscan.HDBSCAN(
            min_cluster_size=3,
            min_samples=2,
            metric='euclidean',
            cluster_selection_method='eom',
            prediction_data=True
        )
        hdbscan_model.fit(embeddings)
        cluster_labels = hdbscan_model.labels_
        probabilities = hdbscan_model.probabilities_
        outlier_scores = hdbscan_model.outlier_scores_
    except Exception as e:
        print(f"Standalone hdbscan failed or not available ({e}). Falling back to sklearn.cluster.HDBSCAN...")
        try:
            from sklearn.cluster import HDBSCAN as SklearnHDBSCAN
            hdbscan_model = SklearnHDBSCAN(
                min_cluster_size=3,
                min_samples=2,
                metric='euclidean',
                cluster_selection_method='eom'
            )
            hdbscan_model.fit(embeddings)
            cluster_labels = hdbscan_model.labels_
            probabilities = hdbscan_model.probabilities_
            # sklearn HDBSCAN doesn't compute outlier_scores directly in the same way, but it calculates outlier_scores_ if available
            outlier_scores = getattr(hdbscan_model, 'outlier_scores_', np.zeros_like(cluster_labels, dtype=float))
        except Exception as e2:
            print(f"Sklearn HDBSCAN also failed: {e2}")
            sys.exit(1)

    unique_clusters = set(cluster_labels) - {-1}
    noise_count = list(cluster_labels).count(-1)
    print(f"Clustering complete!")
    print(f"Found {len(unique_clusters)} clusters (labelled 0 to {len(unique_clusters)-1})")
    print(f"Identified {noise_count} noise points / outliers (labelled -1)")

    # Create Results DataFrame
    results_df = pd.DataFrame({
        "Concept": concepts,
        "Cluster_ID": cluster_labels,
        "Probability": probabilities if probabilities is not None else 1.0,
        "Outlier_Score": outlier_scores if outlier_scores is not None else 0.0
    })

    # Save to CSV
    results_df.to_csv(output_csv, index=False)
    print(f"Saved clustered results to: {output_csv}")

    # 5. Dimension Reduction using t-SNE
    print("\n[4/5] Running t-SNE for 2D visualization...")
    from sklearn.manifold import TSNE
    
    # We use a moderate perplexity since dataset is small (160 items)
    # Perplexity must be less than n_samples
    tsne = TSNE(n_components=2, perplexity=min(15, len(concepts) - 1), random_state=42, metric='cosine')
    embeddings_2d = tsne.fit_transform(embeddings)
    print(f"t-SNE projection completed.")

    # 6. Premium Data Visualization
    print("\n[5/5] Creating premium visual chart...")
    fig, ax = plt.subplots(figsize=(14, 10), dpi=300)
    
    # Dark Slate Premium Theme Styling
    ax.set_facecolor('#0f111a')
    fig.patch.set_facecolor('#0f111a')
    
    # Generate soft harmonized color palette for clusters
    num_colors = len(unique_clusters)
    if num_colors > 0:
        colors = sns.color_palette("husl", num_colors)
    else:
        colors = []

    # Map labels to colors
    cluster_color_map = {cluster_id: colors[i] for i, cluster_id in enumerate(sorted(unique_clusters))}
    cluster_color_map[-1] = (0.5, 0.5, 0.5, 0.25) # Outliers in semi-transparent soft gray

    # Plot points
    for cid in sorted(list(unique_clusters) + ([-1] if -1 in cluster_labels else [])):
        mask = (cluster_labels == cid)
        xs = embeddings_2d[mask, 0]
        ys = embeddings_2d[mask, 1]
        
        if cid == -1:
            ax.scatter(xs, ys, c=[cluster_color_map[-1]], label='Outliers/Noise', s=45, alpha=0.30, edgecolors='none', marker='o')
        else:
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
            fontsize=9,
            fontweight='bold',
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.1", color='white', alpha=0.5, lw=0.8)
        )

    # Add titles & descriptions
    plt.title("Physics Concepts Clusters Map", fontsize=20, color='white', fontweight='bold', pad=15)
    ax.text(
        0.5, -0.05, 
        f"Algorithm: HDBSCAN | Model: BGE-M3 (1024D) | Projection: t-SNE | Concepts: {len(concepts)} | Clusters: {len(unique_clusters)}", 
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
        fontsize=9, 
        labelcolor='white',
        title="Clusters",
        title_fontsize=10
    )
    plt.setp(legend.get_title(), color='white')

    plt.tight_layout()
    plt.savefig(output_plot, dpi=300, facecolor='#0f111a')
    plt.close()
    
    print(f"Beautiful cluster visualization saved to: {output_plot}")
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
