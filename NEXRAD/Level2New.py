"""
©2025 JesseLikesWeather.
"""

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import patheffects
from matplotlib.patches import Polygon as MplPolygon
import pyart
from datetime import datetime, timedelta
import requests
from io import BytesIO
import bz2
import tempfile
import os
import numpy as np


# Configuration. Make sure files are in _V06 Format.
aws_nexrad_url = "https://unidata-nexrad-level2.s3.amazonaws.com/2025/06/19/KMOB/KMOB20250619_220753_V06"
filename_date = "20250619"
filename_time = "220753"
RADAR_ID = "KMOB"
RADAR_LOCATION = "MOBILE, AL"
MIN_POPULATION = 1000
# --- End Configuration ---

print("Downloading NEXRAD V06 data from AWS...")
try:
    response = requests.get(aws_nexrad_url, timeout=30)
    response.raise_for_status()
    print(f"Downloaded {len(response.content)} bytes")
except requests.exceptions.RequestException as e:
    print(f"Error downloading data: {e}")
    exit()

print("Processing V06 data...")
try:
    try:
        decompressed_data = bz2.decompress(response.content)
        print("Successfully decompressed bz2 data")
    except:
        # If bz2 fails, the file might already be uncompressed
        decompressed_data = response.content
        print("Using uncompressed data")
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.nexrad')
    temp_file.write(decompressed_data)
    temp_file.close()
    print(f"Wrote {len(decompressed_data)} bytes to temporary file")
    
except Exception as e:
    print(f"Error processing compressed data: {e}")
    exit()

try:
    print("Reading V06 radar data...")
    radar = pyart.io.read_nexrad_archive(
        temp_file.name, 
        station=RADAR_ID,
        delay_field_loading=False
    )
    print(f"Successfully read radar data: {len(radar.fields)} fields available")
    print(f"Available fields: {list(radar.fields.keys())}")
except Exception as e:
    os.unlink(temp_file.name)
    print(f"Error reading NEXRAD V06 file: {e}")
    import traceback
    traceback.print_exc()
    exit()

radar_lat = radar.latitude["data"][0]
radar_lon = radar.longitude["data"][0]
print(f"Radar location: {radar_lat:.4f}°N, {radar_lon:.4f}°W")

# Calculate map extent based on radar center
lat_buffer = 1.7
lon_buffer = 4.3
min_lat = radar_lat - lat_buffer
max_lat = radar_lat + lat_buffer
min_lon = radar_lon - lon_buffer
max_lon = radar_lon + lon_buffer

radar_time = datetime.strptime(f"{filename_date}{filename_time}", "%Y%m%d%H%M%S")
print(f"Radar scan time: {radar_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")

display = pyart.graph.RadarMapDisplay(radar)

projection = ccrs.Mercator()

fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor='#1a1a1a')

ax = plt.axes([0, 0, 1, 0.89], projection=projection)

ax.set_extent([min_lon, max_lon, min_lat, max_lat], crs=ccrs.PlateCarree())

ax.patch.set_facecolor('#1a1a1a')

# --- Base Map Features ---
ax.add_feature(cfeature.OCEAN.with_scale('10m'), facecolor="#203666", zorder=1, edgecolor='none')
ax.add_feature(cfeature.LAND.with_scale('10m'), facecolor="#5c7265", zorder=1, edgecolor='none')

ax.add_feature(cfeature.LAKES.with_scale('10m'), facecolor="#1a3d5c", zorder=2, edgecolor='none', alpha=0.8)
ax.add_feature(cfeature.RIVERS.with_scale('10m'), edgecolor="#1a3d5c", linewidth=0.5, zorder=2, facecolor='none')

# Plot the radar data - V06 typically uses 'reflectivity' or 'REF'
print("Plotting radar reflectivity...")
try:
    # Try different field names that might be present in V06 files
    field_name = None
    for possible_field in ['reflectivity', 'REF', 'DBZ', 'reflectivity_horizontal']:
        if possible_field in radar.fields:
            field_name = possible_field
            break
    
    if field_name is None:
        print(f"Warning: No reflectivity field found. Available: {list(radar.fields.keys())}")
        field_name = list(radar.fields.keys())[0]
    
    print(f"Using field: {field_name}")
    
    display.plot_ppi_map(
        field_name,
        0,
        vmin=-20,
        vmax=70,
        cmap="NWSRef",
        projection=projection,
        ax=ax,
        colorbar_flag=False,
        title_flag=False,
        alpha=0.85,
    )
    
    # Apply bilinear interpolation for smoother appearance
    ax_children = ax.get_children()
    for child in ax_children:
        if hasattr(child, 'set_interpolation'):
            child.set_interpolation('bilinear')
    
except Exception as e:
    print(f"Error plotting radar data: {e}")
    import traceback
    traceback.print_exc()

# --- Geographic Boundaries ---
states = cfeature.NaturalEarthFeature(
    category="cultural",
    name="admin_1_states_provinces_lines",
    scale="50m",
    facecolor="none",
)
ax.add_feature(states, edgecolor='white', linewidth=2, zorder=10, alpha=0.9)

countries = cfeature.NaturalEarthFeature(
    category="cultural",
    name="admin_0_boundary_lines_land",
    scale="50m",
    facecolor="none",
)
ax.add_feature(countries, edgecolor='white', linewidth=2.5, zorder=10)

# --- Add Counties ---
try:
    counties = cfeature.NaturalEarthFeature(
        category="cultural",
        name="admin_2_counties",
        scale="10m",
        facecolor="none",
    )
    ax.add_feature(counties, edgecolor='#888888', linewidth=2, zorder=9, alpha=1)
    print("Counties added successfully")
except Exception as e:
    print(f"Warning: Could not add counties: {e}")

# --- Add Major Highways/Roads ---
roads = cfeature.NaturalEarthFeature(
    category="cultural",
    name="roads",
    scale="10m",
    facecolor="none",
)
ax.add_feature(
    roads, 
    edgecolor='#ffff00',
    linewidth=1.0, 
    linestyle='-', 
    zorder=11, 
    alpha=0.8
)

# --- Storm-Based Warning Polygons ---
print("Fetching storm-based warnings...")

WARNING_TYPES = {
    'TO': {'color': '#FF0000', 'name': 'Tornado Warning'},
    'SV': {'color': '#FFA500', 'name': 'Severe Thunderstorm'},
    'FF': {'color': '#00FF00', 'name': 'Flash Flood Warning'},
    'MA': {'color': '#FF00FF', 'name': 'Marine Warning'},
}

SIGNIFICANCE_FILTER = ['W', 'Y', 'A']

try:
    start_time = radar_time - timedelta(hours=0)
    end_time = radar_time + timedelta(hours=0)
    
    sts = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    ets = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    warnings_url = f"https://mesonet.agron.iastate.edu/geojson/sbw.geojson?sts={sts}&ets={ets}"
    print(f"Requesting warnings from {sts} to {ets}")
    
    warnings_response = requests.get(warnings_url, timeout=10)
    warnings_response.raise_for_status()
    warnings_data = warnings_response.json()
    
    print(f"Total warnings received: {len(warnings_data.get('features', []))}")
    
    warnings_plotted = 0
    
    for feature in warnings_data.get('features', []):
        props = feature.get('properties', {})
        geom = feature.get('geometry', {})
        
        phenomena = props.get('phenomena', '')
        significance = props.get('significance', '')
        
        if phenomena not in WARNING_TYPES and significance not in SIGNIFICANCE_FILTER:
            continue
        
        if phenomena in WARNING_TYPES:
            warning_info = WARNING_TYPES[phenomena].copy()
        else:
            warning_info = {'color': '#FFFF00', 'name': 'Weather Warning'}
        
        # Check for special tornado warning types
        if phenomena == 'TO':
            is_emergency = props.get('is_emergency', False)
            is_pds = props.get('is_pds', False)
            
            if is_emergency:
                warning_info['color'] = '#8B008B'
                warning_info['name'] = 'TORNADO EMERGENCY'
            elif is_pds:
                warning_info['color'] = '#8B0000'
                warning_info['name'] = 'PDS TORNADO WARNING'
        
        # Extract polygon coordinates
        if geom.get('type') == 'MultiPolygon':
            polygons = geom.get('coordinates', [])
        elif geom.get('type') == 'Polygon':
            polygons = [geom.get('coordinates', [])]
        else:
            continue
        
        if not polygons:
            continue
        
        for polygon in polygons:
            if not polygon:
                continue
            
            exterior = polygon[0] if polygon else []
            if not exterior or len(exterior) < 3:
                continue
            
            lons = [coord[0] for coord in exterior]
            lats = [coord[1] for coord in exterior]
            
            if (max(lons) < min_lon or min(lons) > max_lon or
                max(lats) < min_lat or min(lats) > max_lat):
                continue
            
            poly_patch = MplPolygon(
                exterior,
                closed=True,
                transform=ccrs.PlateCarree(),
                facecolor='none',
                edgecolor=warning_info['color'],
                alpha=1.0,
                linewidth=5,
                zorder=12,
                linestyle='-'
            )
            ax.add_patch(poly_patch)
            warnings_plotted += 1
    
    print(f"Total warnings plotted: {warnings_plotted}")
    
except requests.exceptions.RequestException as e:
    print(f"Warning: Could not fetch storm warnings: {e}")
except Exception as e:
    print(f"Warning: Error processing storm warnings: {e}")

# --- Dynamic City Labeling ---
try:
    cities_shp = shpreader.natural_earth(
        resolution='10m',
        category='cultural',
        name='populated_places'
    )
    
    reader = shpreader.Reader(cities_shp)
    cities_plotted_count = 0

    for city_record in reader.records():
        try:
            if hasattr(city_record.geometry, 'x') and hasattr(city_record.geometry, 'y'):
                lon = city_record.geometry.x
                lat = city_record.geometry.y
            else:
                lon, lat = city_record.geometry.coords[0]
        except (AttributeError, IndexError, TypeError):
            continue

        city_name = city_record.attributes.get('NAME')
        pop_max = city_record.attributes.get('POP_MAX')
        
        try:
            pop_max = float(pop_max) if pop_max is not None else 0
        except (ValueError, TypeError):
            pop_max = 0
        
        if city_name is None or not city_name.strip():
            continue
            
        if (min_lon < lon < max_lon and 
            min_lat < lat < max_lat and
            pop_max >= MIN_POPULATION):

            print(f"PLOTTING: {city_name} (Pop: {int(pop_max)}) at ({lon:.2f}, {lat:.2f})")
            cities_plotted_count += 1
            
            txt = ax.text(
                lon,
                lat,
                city_name,
                transform=ccrs.PlateCarree(),
                fontsize=12,
                fontfamily="Roboto",
                fontweight='bold',
                color="white",
                ha="center",
                va="bottom",
                zorder=15,
            )
            txt.set_path_effects([
                patheffects.withStroke(linewidth=3, foreground="black", alpha=0.8),
                patheffects.Normal()
            ])
    
    print(f"\nTotal cities plotted: {cities_plotted_count}")

except Exception as e:
    print(f"Warning: Failed to load city data: {e}")

# Remove axis spines and ticks
ax.spines['geo'].set_visible(False)
ax.set_xticks([])
ax.set_yticks([])

# --- Professional Banner at Top ---
banner_ax = fig.add_axes([0, 0.89, 1, 0.11])
banner_ax.set_xlim(0, 1)
banner_ax.set_ylim(0, 1)
banner_ax.axis("off")

banner_bg = mpatches.Rectangle(
    (0, 0), 1, 1, 
    transform=banner_ax.transAxes, 
    color='#0a0a0a', 
    zorder=0
)
banner_ax.add_patch(banner_bg)

banner_border = mpatches.Rectangle(
    (0, 0), 1, 0.02,
    transform=banner_ax.transAxes,
    color='#00ff00',
    alpha=0.3,
    zorder=1
)
banner_ax.add_patch(banner_border)

info_text = f"NEXRAD SITE: {RADAR_ID} ({RADAR_LOCATION})"
time_text = f"{radar_time.strftime('%B %d, %Y  %H:%M:%S')} UTC"

banner_ax.text(
    0.02,
    0.65,
    info_text,
    transform=banner_ax.transAxes,
    fontsize=16,
    fontfamily="Rubik",
    color="white",
    va="center",
    weight="bold",
    zorder=2
)

banner_ax.text(
    0.02,
    0.30,
    time_text,
    transform=banner_ax.transAxes,
    fontsize=14,
    fontfamily="Rubik",
    color="#aaaaaa",
    va="center",
    zorder=2
)

# --- Colorbar Legend ---
cbar_ax = fig.add_axes([0.40, 0.02, 0.58, 0.04])
norm = plt.Normalize(vmin=-20, vmax=70)
cmap = plt.cm.get_cmap("NWSRef")

cb = plt.colorbar(
    plt.cm.ScalarMappable(norm=norm, cmap=cmap),
    cax=cbar_ax,
    orientation="horizontal",
)

cb.set_label(
    "REFLECTIVITY (dBZ)", 
    fontsize=12, 
    fontfamily="Rubik", 
    color="white",
    weight='bold',
    labelpad=8
)
cb.ax.tick_params(
    labelsize=10, 
    colors="white",
    length=6,
    width=1.5,
    pad=5
)
cb.set_ticks([-20, -10, 0, 10, 20, 30, 40, 50, 60, 70])

for spine in cb.ax.spines.values():
    spine.set_edgecolor('white')
    spine.set_linewidth(1.5)

current_year = datetime.now().year
ax.text(
    0.98,
    0.02,
    f"©{current_year} JesseLikesWeather",
    transform=ax.transAxes,
    fontsize=13,
    fontfamily="Rubik",
    color="white",
    va="bottom",
    ha="left",
    zorder=20,
    weight='bold'
)

os.unlink(temp_file.name)

output_filename = f"{RADAR_ID}_{filename_date}_{filename_time}.png"
plt.savefig(output_filename, dpi=100, facecolor='#1a1a1a', edgecolor='none')
print(f"\nVisualization saved as {output_filename}")
plt.show()
