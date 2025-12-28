"©2025 JesseLikesWeather."

from goes2go import GOES
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import cartopy.feature as cfeature
import cartopy.crs as ccrs
from PIL import Image
import os

map_region = 'CONUS' # Check line 19 for options!

interpolation_type = 'bilinear' 

satellite = 19 # GOES-19. Satellites will vary depending on given time range.
product = 'ABI'

map_extents = {
    'Default': None, # The script will use the image's full bounds if None
    'CONUS': [-125, -65, 20, 50],
    'Southeast': [-95, -75, 25, 38],
    'Northeast': [-85, -65, 35, 50],
    'Northwest': [-130, -105, 38, 50],
    'Southwest': [-125, -100, 25, 40],
    'North Central': [-110, -85, 40, 50],
    'Central': [-105, -85, 30, 45],
    'South Central': [-110, -90, 25, 40],
    'Lower Mississippi': [-95, -85, 28, 40],
    'Central Mississippi': [-100, -85, 30, 45],
    'Upper Mississippi': [-100, -85, 40, 50],
    'Great Lakes': [-95, -75, 38, 50],
    'Alaska': [-180, -130, 50, 75] 
}
# ==============================================================================


cities = {
    'Des Moines': (41.5868, -93.6250),
    'Dubuque': (42.5006, -90.6646),
    'Nashville': (36.1627, -86.7816),
    'Memphis': (35.1495, -90.0490),
    'Tyler': (32.3513, -95.3011),
    'LaFayette': (40.4173, -86.8756),
    'Evansville': (37.9716, -87.5714),
    'San Angelo': (31.4638577, -100.4371246),
    'Oklahoma City': (35.4676, -97.5164),
    'Pensacola': (30.4213, -87.2169),
    'Atlanta': (33.7490, -84.3880),
    'Lansing': (42.7325, -84.5555),
    'Topeka': (39.0489, -95.6780),
    'Grand Island': (40.9254, -98.3420),
    'Guymon': (36.6822, -101.4715),
    'Denver': (39.7392, -104.9903),
    'Miami': (25.7617526,-80.1918927),
    'Raleigh': (35.7795428,-78.638397),
    'Washington, DC': (38.9072951,-77.0365428),
    'Boston': (42.3554245,-71.0567769),
    'Buffalo': (42.8869941,-78.8787977),
    'Tuscon': (32.2539746,-110.9739495),
    'Salt Lake City': (40.7605382,-111.8881457),
    'Sacramento': (38.5775151,-121.4949946),
    'Seattle': (47.6061026,-122.3327523),
    'Bismarck': (46.8042451,-100.7878722),
    'Helena': (46.5891452,-112.0391074),
    'International Falls': (48.6009953,-93.4032997),
    'Hamilton': (32.2950673,-64.7842878),
    'San Juan': (18.4153045,-66.0593645),
    'Cancún': (21.1619013,-86.8516573),
    'Halifax': (44.6508439,-63.5922432),
    'Havana': (23.1338081,-82.3583889),
    'George Town': (23.502425980984587,-75.77004984566923),
    'Mexico City': (19.4328091,-99.1332262),
    'Monterrey': (25.6864203,-100.3168008),
    'Houston': (29.7601852,-95.3719349),
    'Elko': (40.8435794,-115.7527039),
    'Salem': (44.9362053,-123.0405318),
    'Twin Falls': (42.5558403,-114.4701733),
    'Bar Harbor': (44.3875484,-68.2042762),
    'Santa Fe': (35.6894456,-105.9381952)
    }

# Create GOES object
print(f"Setting up GOES-{satellite} data retrieval...")
G = GOES(satellite=satellite, product=product)

start_time = datetime(2025, 12, 1, 12, 00) # 12/01/2025 12 UTC
end_time = datetime(2025, 12, 2, 12, 30) # 12/02/2025 12:30 UTC
interval_minutes = 60 # 60 Minute Image Intervals.

# Generate list of times
time_list = []
current_time = start_time
while current_time <= end_time:
    time_list.append(current_time)
    current_time += timedelta(minutes=interval_minutes)

print(f"Downloading data at {interval_minutes}-minute intervals...")
print(f"Total frames to create: {len(time_list)}")

os.makedirs('temp_frames', exist_ok=True)

plot_extent = None

frame_files = []
for idx, target_time in enumerate(time_list):
    print(f"Processing frame {idx + 1}/{len(time_list)}: {target_time}")
    
    try:
        # Load the dataset nearest to the target time
        ds = G.nearesttime(target_time)
        
        # Get the actual timestamp from the data
        actual_time = datetime.strptime(str(ds.time_coverage_start.values), '%Y-%m-%dT%H:%M:%S.%fZ')
        
        # Format the timestamp in GOES style
        day_of_year = actual_time.timetuple().tm_yday
        year_day = f"{actual_time.year}{day_of_year:03d}"
        timestamp_str = f"GOES-{satellite}  BAND=2 (0.64 UM) (VIS)  {actual_time.strftime('%d-%b-%Y').upper()} ({year_day})"
        time_only = actual_time.strftime('%H:%M UTC')
        
        # Create figure and axis with proper projection
        fig = plt.figure(figsize=(12, 9))
        ax = plt.subplot(projection=ds.rgb.crs)
        
        # ----------------------------------------------------------------------
        # ➡️ Interpolation and TypeError Fix
        # Remove the default 'interpolation' key to avoid the TypeError
        ds.rgb.imshow_kwargs.pop('interpolation', None)
        # Plot with the specified interpolation_type
        ax.imshow(ds.rgb.TrueColor(), **ds.rgb.imshow_kwargs, interpolation=interpolation_type)
        # ----------------------------------------------------------------------
        
        # ----------------------------------------------------------------------
        # ➡️ Dynamic Map Extent Setting
        custom_extent = map_extents.get(map_region)
        
        if custom_extent is not None:
            # Use the custom preset bounds with PlateCarree CRS
            ax.set_extent(custom_extent, crs=ccrs.PlateCarree())
            if idx == 0:
                print(f"Plot extent set to: {map_region} {custom_extent}")
        else:
            # If 'Default' is used, set the extent based on the full image bounds
            if plot_extent is None:
                plot_extent = ds.rgb.imshow_kwargs['extent']
                if idx == 0:
                    print("Plot extent set to: Default (Full Image Bounds)")
            ax.set_extent(plot_extent, crs=ds.rgb.crs)
        # ----------------------------------------------------------------------

        # Add map features
        ax.coastlines(resolution='50m', color='cyan', linewidth=0.5)
        ax.add_feature(cfeature.BORDERS, linewidth=0.5, edgecolor='cyan')
        ax.add_feature(cfeature.STATES, linewidth=0.3, edgecolor='cyan')
        
        # ----------------------------------------------------------------------
        # ➡️ NEW: Filter Cities to Plot ONLY those within the current map extent
        # ----------------------------------------------------------------------
        visible_cities = {}
        
        # Use the custom extent if set, otherwise the default plot extent
        if custom_extent is not None:
            lon_min, lon_max, lat_min, lat_max = custom_extent
            
            for city, (lat, lon) in cities.items():
                # Check if city coordinates are within the defined bounds
                if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                    visible_cities[city] = (lat, lon)
        else:
            # If default view, plot all cities
            visible_cities = cities

        # Plot city markers (red dots)
        lats = [coords[0] for coords in visible_cities.values()]
        lons = [coords[1] for coords in visible_cities.values()]
        ax.plot(lons, lats, 'ro', markersize=4, transform=ccrs.PlateCarree())
        
        # Plot city labels
        for city, (lat, lon) in visible_cities.items():
            ax.text(lon + 0.1, lat, city,
                    transform=ccrs.PlateCarree(),
                    fontsize=9,
                    color='white',
                    weight='bold',
                    ha='left',
                    va='center',
                    fontname='Courier New',
                    bbox=dict(boxstyle='round,pad=0.1', facecolor='black', alpha=0.4, edgecolor='none'))
        
        ax.text(0.5, 0.02, f"{timestamp_str}  {time_only}",
                transform=ax.transAxes,
                fontsize=12,
                fontname='Courier New',
                horizontalalignment='center',
                verticalalignment='bottom',
                color='white',
                weight='bold',
                bbox=dict(boxstyle='square,pad=0.3', facecolor='black', alpha=0.9, edgecolor='white', linewidth=1))
        
        # Add watermark
        ax.text(0.01, 0.02, '©2025 JesseLikesWeather',
                transform=ax.transAxes,
                fontsize=10,
                color='white',
                alpha=0.6,
                va='bottom',
                ha='left')
        
        frame_file = f'temp_frames/frame_{idx:03d}.png'
        plt.savefig(frame_file, dpi=150, bbox_inches='tight', facecolor='black')
        plt.close(fig)
        frame_files.append(frame_file)
        
    except Exception as e:
        print(f"Error processing frame {idx + 1}: {e}")
        continue

if frame_files:
    print(f"\nCreating GIF from {len(frame_files)} frames...")
    
    frames = [Image.open(frame) for frame in frame_files]
    
    output_file = 'Hurricane_Dorian_2019.gif' # <- File Name.
    frames[0].save(
        output_file,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0
    )
    
    print(f"GIF saved as: {output_file}")
    
    # Clean up temporary frames
    print("Cleaning up temporary files...")
    for frame_file in frame_files:
        os.remove(frame_file)
    os.rmdir('temp_frames')
    
    print("Done!")
else:
    print("No frames were created. Check your data range and try again.")
