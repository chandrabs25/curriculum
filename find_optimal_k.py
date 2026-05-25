# /// script
# dependencies = [
#   "scikit-learn",
#   "numpy",
#   "pandas",
#   "matplotlib",
#   "seaborn",
# ]
# ///

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score

# Set styles for premium aesthetics
plt.style.use('dark_background')
sns.set_theme(style="dark", palette="muted")

def main():
    print("=" * 60)
    print("MATHEMATICAL SEARCH FOR OPTIMAL CLUSTER COUNT (K)")
    print("=" * 60)

    # 1. Define Paths
    base_dir = "/Users/srichandrasamanapalli/Documents/curriculum/concept csv"
    embeddings_file = os.path.join(base_dir, "all_concepts_embeddings.npy")
    output_plot = os.path.join(base_dir, "optimal_k_analysis.png")

    if not os.path.exists(embeddings_file):
        print(f"Error: Pre-generated embeddings not found at {embeddings_file}")
        return

    # Load embeddings
    embeddings = np.load(embeddings_file)
    print(f"Loaded embeddings with shape: {embeddings.shape}")

    # 2. Iterate K from 2 to 30 and record metrics
    k_values = list(range(2, 30))
    silhouette_scores = []
    linkage_distances = []  # Variance increase indicator (sum of squared distances within clusters)

    for k in k_values:
        # Fit Agglomerative Clustering
        agg = AgglomerativeClustering(n_clusters=k, metric='euclidean', linkage='ward')
        labels = agg.fit_predict(embeddings)
        
        # Calculate Silhouette Score (Gold Standard)
        score = silhouette_score(embeddings, labels, metric='euclidean')
        silhouette_scores.append(score)
        
        # Calculate within-cluster variance proxy (sum of distances to cluster centroids)
        centroids = np.zeros((k, embeddings.shape[1]))
        variance = 0
        for i in range(k):
            cluster_points = embeddings[labels == i]
            if len(cluster_points) > 0:
                centroid = np.mean(cluster_points, axis=0)
                variance += np.sum(np.linalg.norm(cluster_points - centroid, axis=1)**2)
        linkage_distances.append(variance)

    # Find the mathematically optimal K (peak of silhouette score)
    optimal_k_silhouette = k_values[np.argmax(silhouette_scores)]
    print(f"\nMathematical Analysis Results:")
    print(f"  - Peak Silhouette Score: {max(silhouette_scores):.4f} at K = {optimal_k_silhouette}")
    
    # 3. Create a Premium Dual-Axis Plot
    fig, ax1 = plt.subplots(figsize=(12, 6), dpi=300)
    ax1.set_facecolor('#0f111a')
    fig.patch.set_facecolor('#0f111a')

    # Color definitions
    color_sil = '#00e5ff'
    color_elb = '#ff007f'

    # Plot Silhouette Scores (Higher is better)
    ax1.plot(k_values, silhouette_scores, color=color_sil, marker='o', linewidth=2, label='Silhouette Score')
    ax1.set_xlabel('Number of Clusters (K)', color='white', fontsize=12)
    ax1.set_ylabel('Silhouette Score (Quality)', color=color_sil, fontsize=12)
    ax1.tick_params(axis='y', labelcolor=color_sil)
    ax1.grid(True, color='#282a36', linestyle='--', alpha=0.5)

    # Plot Elbow Variance (Lower is better)
    ax2 = ax1.twinx()
    ax2.plot(k_values, linkage_distances, color=color_elb, marker='s', linewidth=2, linestyle='--', label='Within-Cluster Variance')
    ax2.set_ylabel('Within-Cluster Variance (Elbow Metric)', color=color_elb, fontsize=12)
    ax2.tick_params(axis='y', labelcolor=color_elb)
    ax2.spines['right'].set_color(color_elb)
    ax2.spines['left'].set_color(color_sil)

    # Highlight our K=12 choice and the mathematical peak
    ax1.axvline(x=12, color='#50fa7b', linestyle=':', linewidth=2, label='Our Curriculum Choice (K=12)')
    if optimal_k_silhouette != 12:
        ax1.axvline(x=optimal_k_silhouette, color='#ffb86c', linestyle='-.', linewidth=1.5, label=f'Math Optimal Peak (K={optimal_k_silhouette})')

    plt.title('Determining Optimal Number of Clusters (K)', fontsize=16, color='white', fontweight='bold', pad=15)
    
    # Unified Legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right', facecolor='#1c1f30', edgecolor='#2e344e', labelcolor='white')

    plt.tight_layout()
    plt.savefig(output_plot, facecolor='#0f111a')
    plt.close()

    print(f"\nAnalysis plot saved successfully to: {output_plot}")
    print("=" * 60)

if __name__ == "__main__":
    main()
