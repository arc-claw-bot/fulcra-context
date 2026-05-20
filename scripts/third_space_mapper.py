#!/usr/bin/env python3
"""
Third Space Mapper (POC)

Reads analyzed Third Space data and generates a high-resolution,
stylized map visualizing locations and their corresponding average Heart Rate.
"""

import argparse
import sys
import matplotlib.pyplot as plt
from matplotlib.offsetbox import TextArea, VPacker, AnnotationBbox
import matplotlib.colors as mcolors
import pandas as pd

try:
    import contextily as cx
    import geopandas as gpd
except ImportError:
    print("Please install required mapping libraries: pip install geopandas contextily pandas matplotlib")
    sys.exit(1)

def generate_map(data, output_path):
    df = pd.DataFrame(data)

    if df.empty:
        print("No data provided to map.")
        return

    # Create GeoDataFrame and reproject to Web Mercator for Contextily
    gdf = gpd.GeoDataFrame(
        df, 
        geometry=gpd.points_from_xy(df.lon, df.lat), 
        crs="EPSG:4326"
    ).to_crs(epsg=3857)

    fig, ax = plt.subplots(figsize=(12, 8), dpi=400)

    # Custom tasteful diverging colormap (Teal -> Coral)
    colors = ["#2A9D8F", "#E9C46A", "#F4A261", "#E76F51"] 
    custom_cmap = mcolors.LinearSegmentedColormap.from_list("tasteful_diverging", colors)

    scatter = ax.scatter(gdf.geometry.x, gdf.geometry.y, 
                         c=gdf['hr'], cmap=custom_cmap, s=500, edgecolor='white', linewidth=2, zorder=5, alpha=0.95)

    for i, row in gdf.iterrows():
        t1 = TextArea(row['name'], textprops=dict(color='#222222', fontweight='bold', fontsize=11, fontfamily='sans-serif'))
        t2 = TextArea(f"{row['hr']:.1f} bpm", textprops=dict(color='#666666', fontweight='normal', fontsize=9.5, fontfamily='sans-serif'))
        
        vbox = VPacker(children=[t1, t2], align="left", pad=0, sep=3)
        
        ab = AnnotationBbox(
            vbox,
            (row.geometry.x, row.geometry.y),
            xybox=(15, 15),
            xycoords='data',
            boxcoords="offset points",
            pad=0.5,
            bboxprops=dict(boxstyle="round,pad=0.5,rounding_size=0.2", facecolor="white", edgecolor="#d0d0d0", linewidth=1.5, alpha=0.95),
            zorder=6
        )
        ax.add_artist(ab)

    # Padding
    x_margin = max((gdf.geometry.x.max() - gdf.geometry.x.min()) * 0.2, 2000)
    y_margin = max((gdf.geometry.y.max() - gdf.geometry.y.min()) * 0.2, 2000)
    ax.set_xlim(gdf.geometry.x.min() - x_margin, gdf.geometry.x.max() + x_margin)
    ax.set_ylim(gdf.geometry.y.min() - y_margin, gdf.geometry.y.max() + y_margin)

    # Modern basemap layer
    cx.add_basemap(ax, source=cx.providers.CartoDB.Voyager, zoom=14)

    # Colorbar
    cbar = plt.colorbar(scatter, ax=ax, fraction=0.03, pad=0.04)
    cbar.set_label('Average Heart Rate (bpm)', fontsize=12, fontfamily='sans-serif', fontweight='bold', color='#444444')
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(labelsize=10, colors='#444444', length=0)

    plt.title("Weekend Third Spaces: Physiological Map", fontsize=18, pad=20, fontfamily='sans-serif', fontweight='bold', color='#222222', loc='left')
    ax.set_axis_off()

    plt.tight_layout()
    plt.savefig(output_path, dpi=400, bbox_inches='tight')
    print(f"Map successfully generated at: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a map from hardcoded POC data.")
    parser.add_argument("--out", type=str, default="/tmp/third_space_map.png", help="Output path for the PNG map.")
    args = parser.parse_args()

    # Synthetic POC data 
    data = [
        {"name": "Location Alpha", "lat": 42.500, "lon": -83.300, "hr": 82.6},
        {"name": "Location Beta", "lat": 42.450, "lon": -83.100, "hr": 87.9},
        {"name": "Location Gamma", "lat": 42.490, "lon": -83.150, "hr": 91.1},
        {"name": "Location Delta", "lat": 42.470, "lon": -83.170, "hr": 105.0}
    ]
    
    generate_map(data, args.out)
