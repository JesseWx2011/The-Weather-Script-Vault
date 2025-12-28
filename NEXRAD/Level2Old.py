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
import gzip
import tempfile
import os
import numpy as np
from PIL import Image

# --- Configuration ---
aws_nexrad_url = "https://unidata-nexrad-level2.s3.amazonaws.com/2013/05/31/KTLX/KTLX20130531_233259_V06.gz"
filename_date = "20130531"
filename_time = "233259"
RADAR_ID = "KTLX"
RADAR_LOCATION = "OKLAHOMA CITY, OK"
MIN_POPULATION = 1000
# --- End Configuration ---

print("Downloading NEXRAD data from AWS...")
try:
    response = requests.get(aws_nexrad_url)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    print(f"Error downloading data: {e}")
    exit()

print("Decompressing data...")
compressed_data = BytesIO(response.content)
decompressed_data = gzip.decompress(compressed_data.read())

temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.nexrad')
temp_file.write(decompressed_data)
temp_file.close()

try:
    print("Reading radar data...")
    radar = pyart.io.read_nexrad_archive(temp_file.name, station=RADAR_ID)
except Exception as e:
    os.unlink(temp_file.name)
    print(f"Error reading NEXRAD file: {e}")
    exit()

radar_lat = radar.latitude["data"][0]
radar_lon = radar.longitude["data"][0]

lat_buffer = 1.7
lon_buffer = 4.3
min_lat = radar_lat - lat_buffer
max_lat = radar_lat + lat_buffer
min_lon = radar_lon - lon_buffer
max_lon = radar_lon + lon_buffer

radar_time = datetime.strptime(f"{filename_date}{filename_time}", "%Y%m%d%H%M%S")

display = pyart.graph.RadarMapDisplay(radar)

projection = ccrs.Mercator()

fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor='#1a1a1a')

ax = plt.axes([0, 0, 1, 0.89], projection=projection)

ax.set_extent([min_lon, max_lon, min_lat, max_lat], crs=ccrs.PlateCarree())

ax.patch.set_facecolor('#1a1a1a')

ax.add_feature(cfeature.OCEAN.with_scale('50m'), facecolor="#203666", zorder=1, edgecolor='none')
ax.add_feature(cfeature.LAND.with_scale('50m'), facecolor="#5c7265", zorder=1, edgecolor='none')

ax.add_feature(cfeature.LAKES.with_scale('10m'), facecolor="#1a3d5c", zorder=2, edgecolor='none', alpha=0.8)
ax.add_feature(cfeature.RIVERS.with_scale('10m'), edgecolor="#1a3d5c", linewidth=0.5, zorder=2, facecolor='none')

display.plot_ppi_map(
    "reflectivity",
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

ax_children = ax.get_children()
for child in ax_children:
    if hasattr(child, 'set_interpolation'):
        child.set_interpolation('bilinear')  

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


print("Fetching storm-based warnings...")

# Define warning colors by phenomena type (not significance)
# We'll check the 'phenomena' field instead of 'significance'
WARNING_TYPES = {
    'TO': {'color': '#FF0000', 'name': 'Tornado Warning'},        # Red
    'SV': {'color': '#FFA500', 'name': 'Severe Thunderstorm'},    # Orange
    'FF': {'color': '#00FF00', 'name': 'Flash Flood Warning'},    # Green
    'MA': {'color': '#FF00FF', 'name': 'Marine Warning'},         # Magenta
}

# Also accept warnings by significance
SIGNIFICANCE_FILTER = ['W', 'Y', 'A']  # W=Warning, Y=Advisory, A=Watch

try:
    # Create time window around radar scan
    start_time = radar_time - timedelta(hours=0)
    end_time = radar_time + timedelta(hours=0)
    
    # Format times for API (ISO 8601)
    sts = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    ets = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    warnings_url = f"https://mesonet.agron.iastate.edu/geojson/sbw.geojson?sts={sts}&ets={ets}"
    print(f"Requesting warnings from {sts} to {ets}")
    print(f"Map extent: Lon [{min_lon:.2f}, {max_lon:.2f}], Lat [{min_lat:.2f}, {max_lat:.2f}]")
    
    warnings_response = requests.get(warnings_url, timeout=10)
    warnings_response.raise_for_status()
    warnings_data = warnings_response.json()
    
    print(f"Total warnings received: {len(warnings_data.get('features', []))}")
    
    # Debug: Check what warning types we're receiving
    sig_types = {}
    phenomena_types = {}
    for feature in warnings_data.get('features', []):
        sig = feature.get('properties', {}).get('significance', 'Unknown')
        phen = feature.get('properties', {}).get('phenomena', 'Unknown')
        sig_types[sig] = sig_types.get(sig, 0) + 1
        phenomena_types[phen] = phenomena_types.get(phen, 0) + 1
    print(f"Warning significance types found: {sig_types}")
    print(f"Warning phenomena types found: {phenomena_types}")
    
    warnings_plotted = 0
    warnings_outside_extent = 0
    warnings_filtered = 0
    warnings_no_geometry = 0
    warnings_bad_polygon = 0
    tornado_warnings = []  # Store tornado warning data for GIF creation
    
    for feature in warnings_data.get('features', []):
        props = feature.get('properties', {})
        geom = feature.get('geometry', {})
        
        phenomena = props.get('phenomena', '')
        significance = props.get('significance', '')
        
        if phenomena not in WARNING_TYPES and significance not in SIGNIFICANCE_FILTER:
            warnings_filtered += 1
            continue
        
        if phenomena in WARNING_TYPES:
            warning_info = WARNING_TYPES[phenomena].copy()
        else:
            warning_info = {'color': '#FFFF00', 'name': 'Weather Warning'}
        
        if phenomena == 'TO':
            is_emergency = props.get('is_emergency', False)
            is_pds = props.get('is_pds', False)
            
            if is_emergency:
                warning_info['color'] = '#8B008B' 
                warning_info['name'] = 'TORNADO EMERGENCY'
            elif is_pds:
                warning_info['color'] = '#8B0000'
                warning_info['name'] = 'PDS TORNADO WARNING'
        
        warning_name = props.get('ps', warning_info['name'])

        # Extract polygon coordinates
        if geom.get('type') == 'MultiPolygon':
            polygons = geom.get('coordinates', [])
        elif geom.get('type') == 'Polygon':
            polygons = [geom.get('coordinates', [])]
        else:
            warnings_no_geometry += 1
            continue
        
        if not polygons:
            warnings_no_geometry += 1
            continue
        
        # Plot each polygon
        for polygon in polygons:
            if not polygon:
                continue
            
            # Get exterior ring (first element)
            exterior = polygon[0] if polygon else []
            if not exterior or len(exterior) < 3:
                continue
            
            # Check if polygon intersects with map extent
            lons = [coord[0] for coord in exterior]
            lats = [coord[1] for coord in exterior]
            
            # Simple bounding box check
            if (max(lons) < min_lon or min(lons) > max_lon or
                max(lats) < min_lat or min(lats) > max_lat):
                warnings_outside_extent += 1
                continue
            
            poly_patch = MplPolygon(
                exterior,
                closed=True,
                transform=ccrs.PlateCarree(),
                facecolor='none',  # No fill
                edgecolor=warning_info['color'],
                alpha=1.0, 
                linewidth=5,
                zorder=12,
                linestyle='-'
            )
            ax.add_patch(poly_patch)
            warnings_plotted += 1
            
            print(f"PLOTTING WARNING: {warning_name} ({significance})")
    
    print(f"Total warnings plotted: {warnings_plotted}")
    print(f"Warnings outside map extent: {warnings_outside_extent}")
    print(f"Warnings filtered (not convective): {warnings_filtered}")
    
except requests.exceptions.RequestException as e:
    print(f"Warning: Could not fetch storm warnings: {e}")
except Exception as e:
    print(f"Warning: Error processing storm warnings: {e}")
    import traceback
    traceback.print_exc()


try:
    cities_shp = shpreader.natural_earth(
        resolution='10m',
        category='cultural',
        name='populated_places'
    )
    
    reader = shpreader.Reader(cities_shp)
    
    cities_plotted_count = 0

    for i, city_record in enumerate(reader.records()):
        
        # --- Extract Coordinates from Geometry ---
        try:
            # For Point geometries, access x and y attributes directly
            if hasattr(city_record.geometry, 'x') and hasattr(city_record.geometry, 'y'):
                lon = city_record.geometry.x
                lat = city_record.geometry.y
            else:
                # Fallback for other geometry types
                lon, lat = city_record.geometry.coords[0]
        except (AttributeError, IndexError, TypeError) as e:
            continue 

        city_name = city_record.attributes.get('NAME')
        pop_max = city_record.attributes.get('POP_MAX')
        
        try:
            pop_max = float(pop_max) if pop_max is not None else 0
        except (ValueError, TypeError):
            pop_max = 0
        
        if city_name is None or not city_name.strip():
            continue
            
        # Filter 1: Check if the city is within the current plot extent
        # Filter 2: Check if the city meets the minimum population threshold
        if (min_lon < lon < max_lon and 
            min_lat < lat < max_lat and
            pop_max >= MIN_POPULATION):

            # --- DEBUG: City confirmed to be plotted ---
            print(f"PLOTTING: {city_name} (Pop: {int(pop_max)}) at ({lon:.2f}, {lat:.2f})")
            cities_plotted_count += 1
            
            # Plot city label with subtle glow effect
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
    if cities_plotted_count == 0:
        print(f"NOTE: No cities found within extent [{min_lon:.2f}, {max_lon:.2f}, {min_lat:.2f}, {max_lat:.2f}]")
        print(f"      with population >= {MIN_POPULATION}")

except Exception as e:
    # Informative warning if the entire Natural Earth read process fails
    print(f"Warning: Failed to load or iterate Natural Earth populated places data. Details: {e}")
    import traceback
    traceback.print_exc()

# Remove axis spines and ticks for cleaner look
ax.spines['geo'].set_visible(False)
ax.set_xticks([])
ax.set_yticks([])

# --- Professional Banner at Top ---
banner_ax = fig.add_axes([0, 0.89, 1, 0.11])
banner_ax.set_xlim(0, 1)
banner_ax.set_ylim(0, 1)
banner_ax.axis("off")

# Add banner background
banner_bg = mpatches.Rectangle(
    (0, 0), 1, 1, 
    transform=banner_ax.transAxes, 
    color='#0a0a0a', 
    zorder=0
)
banner_ax.add_patch(banner_bg)

# Add subtle bottom border to banner
banner_border = mpatches.Rectangle(
    (0, 0), 1, 0.02,
    transform=banner_ax.transAxes,
    color='#00ff00',
    alpha=0.3,
    zorder=1
)
banner_ax.add_patch(banner_border)

# Add radar site and time information
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

# Style the colorbar
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

# Style colorbar outline
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

# Clean up temporary file
os.unlink(temp_file.name)

# Save with high quality
output_filename = f"{RADAR_ID}_{filename_date}_{filename_time}_enhanced.png"
plt.savefig(output_filename, dpi=100, facecolor='#1a1a1a', edgecolor='none')
print(f"Visualization saved as {output_filename}")
plt.show()
