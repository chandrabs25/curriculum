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
    print("PHYSICS CONCEPT AGGLOMERATIVE CLUSTERING (COSINE METRIC)")
    print("=" * 60)

    # 1. Define Paths
    concepts_file = "/Users/srichandrasamanapalli/Downloads/physics_concept_names.csv"
    embeddings_file = "/Users/srichandrasamanapalli/Downloads/physics_concept_embeddings.npy"
    model_dir = "/Users/srichandrasamanapalli/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181"
    
    output_csv = "/Users/srichandrasamanapalli/Downloads/physics_concepts_agglomerative.csv"
    output_plot = "/Users/srichandrasamanapalli/Downloads/physics_clusters_agglomerative.png"

    # 2. Load Concepts
    print(f"\n[1/5] Loading physics concepts from: {concepts_file}")
    if not os.path.exists(concepts_file):
        print(f"Error: Concepts file not found at {concepts_file}")
        sys.exit(1)
        
    with open(concepts_file, 'r', encoding='utf-8') as f:
        concepts = [line.strip() for line in f if line.strip()]
    print(f"Loaded {len(concepts)} concepts successfully.")

    # 3. Load or Generate Embeddings
    embeddings = None
    if os.path.exists(embeddings_file):
        print(f"\n[2/5] Loading pre-generated embeddings from: {embeddings_file}")
        embeddings = np.load(embeddings_file)
        print(f"Loaded embeddings with shape: {embeddings.shape}")
    else:
        print(f"\n[2/5] Embeddings not found at {embeddings_file}. Generating using local BGE-M3 model...")
        if not os.path.exists(model_dir):
            print(f"Error: Model directory not found at {model_dir}")
            sys.exit(1)
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(model_dir)
            embeddings = model.encode(concepts, show_progress_bar=True, normalize_embeddings=True)
            np.save(embeddings_file, embeddings)
            print(f"Saved generated embeddings to: {embeddings_file}")
        except Exception as e:
            print(f"Failed to generate embeddings: {e}")
            sys.exit(1)

    # 4. Agglomerative Clustering with Cosine Distance
    print("\n[3/5] Performing Agglomerative Clustering...")
    print("Configuring: linkage='ward', metric='euclidean' (L2 normalized cosine equivalent), n_clusters=10")
    
    from sklearn.cluster import AgglomerativeClustering
    
    # BGE-M3 embeddings are L2 normalized. Using Ward linkage (which minimizes
    # Euclidean variance) on L2-normalized vectors is mathematically equivalent 
    # to minimizing cosine variance. Ward linkage is famous for avoiding the
    # 'chaining' effect (which average/single linkage suffer from, creating one massive cluster).
    agg_model = AgglomerativeClustering(
        n_clusters=10,
        metric='euclidean',
        linkage='ward'
    )
    cluster_labels = agg_model.fit_predict(embeddings)
    
    unique_clusters = set(cluster_labels)
    print(f"Clustering complete! Grouped concepts into {len(unique_clusters)} clusters (labelled 0 to {len(unique_clusters)-1})")

    # Create Results DataFrame
    results_df = pd.DataFrame({
        "Concept": concepts,
        "Cluster_ID": cluster_labels
    })

    # Save to CSV
    results_df.to_csv(output_csv, index=False)
    print(f"Saved clustered results to: {output_csv}")

    # 5. Dimension Reduction using t-SNE
    print("\n[4/5] Running t-SNE for 2D visualization...")
    from sklearn.manifold import TSNE
    
    # Use Cosine metric for t-SNE to match our clustering metric
    tsne = TSNE(
        n_components=2, 
        perplexity=min(15, len(concepts) - 1), 
        random_state=42, 
        metric='cosine'
    )
    embeddings_2d = tsne.fit_transform(embeddings)
    print(f"t-SNE projection completed.")

    # 6. Premium Data Visualization
    print("\n[5/5] Creating premium visual chart...")
    fig, ax = plt.subplots(figsize=(14, 10), dpi=300)
    
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
            fontsize=9,
            fontweight='bold',
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.1", color='white', alpha=0.5, lw=0.8)
        )

    # Add titles & descriptions
    plt.title("Physics Concepts Clusters Map (Agglomerative - Cosine Ward Equivalent)", fontsize=18, color='white', fontweight='bold', pad=15)
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
        fontsize=9, 
        labelcolor='white',
        title="Clusters",
        title_fontsize=10
    )
    plt.setp(legend.get_title(), color='white')

    plt.tight_layout()
    plt.savefig(output_plot, dpi=300, facecolor='#0f111a')
    plt.close()
    
    print(f"Beautiful Agglomerative cluster visualization saved to: {output_plot}")
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
