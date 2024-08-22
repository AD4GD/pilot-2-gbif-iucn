# This script is using the pre-downloaded GBIF occurrence data cube: https://techdocs.gbif.org/en/data-use/data-cubes

import pandas as pd
import numpy as np
from osgeo import gdal, ogr, osr, gdalconst
from pyproj import Transformer
import os
import re
import yaml

# paths to input and output files
input_dir = 'input/'
output_dir = 'output/'
input_ds = 'ict_2022.tif'
raster_path = os.path.join(input_dir, input_ds)
csv_path = os.path.join(input_dir, 'datacube_iucn_record.csv')
output_csv_path = os.path.join(output_dir, 'datacube_indexed.csv')

# create output directory if doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

## TODO - implement base of filename and extension from the config file (revise variables)
"""
# load configuration from YAML file
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

# extract the input raster file path from the configuration
input_raster = config['input_raster']

# extract the base name (without extension) and the file extension
input_raster_base, extension = os.path.splitext(os.path.basename(input_raster))

# apply the renaming pattern from the config file
output_raster_pattern = config['output_raster']
output_raster = output_raster_pattern.format(input_raster_base=input_raster_base, extension=extension.lstrip('.'))

# print the new raster path
print(f"Output raster: {output_raster}")
"""

# extract the base name of the input raster file and define the name of final raster output
input_filename = os.path.basename(raster_path)
match = re.search(r'(\d{4})', input_filename) # find 4 numbers in a row (year) through regular expression pattern
year_pos = match.start()
output_filename = input_filename[:year_pos] + 'gbif_' + input_filename[year_pos:] # slicing filename before the year position, inserts 'gbif_' and attach the year position with the following text
new_raster_path = os.path.join(output_dir, output_filename)  # new raster with additional band

# define EPSG codes for WGS84 and UTM zone 31N (EPSG:25831)
input_crs = 'EPSG:4326'
output_crs = 'EPSG:25831'
# TODO - to implement custom WGS based on user choice (argparse?)

# function to transform coordinates from EPSG:4326 to EPSG:25831
def transform_coordinates(lat_array, lon_array):
    transformer = Transformer.from_crs(input_crs, output_crs, always_xy=True)
    x, y = transformer.transform(lon_array, lat_array)
    return x, y

# read CSV file with the correct delimiter for SQL TSV ZIP
df = pd.read_csv(csv_path, delimiter = '\t')
print (df.head)

# apply the function to each row in dataframe to get transformed coordinates
df['x_cart'], df['y_cart'] = transform_coordinates(df['lat'].values, df['lon'].values)

print(f"Converted coordinates saved to {output_csv_path}.")

# open raster to get its extent
raster_ds = gdal.Open(raster_path)
raster_geo = raster_ds.GetGeoTransform()
raster_band = raster_ds.GetRasterBand(1)
nodata_value= raster_band.GetNoDataValue() #extract nodata value

# calculate raster extent
minx, miny, maxx, maxy = (
    raster_geo[0],  # minx
    raster_geo[3] + raster_geo[5] * raster_ds.RasterYSize,  # miny
    raster_geo[0] + raster_geo[1] * raster_ds.RasterXSize,  # maxx
    raster_geo[3]  # maxy
)

# print raster extent for debugging
print("Raster extent:", (minx, miny, maxx, maxy))
print(df[['x_cart', 'y_cart']].head())

# function to check if point is within raster extent
def point_within_raster_extent(x_cart, y_cart):
    return (minx <= x_cart <= maxx) and (miny <= y_cart <= maxy)

# initialize the 'bbox' boolean column with False
df['bbox'] = False

# iterate through each row and update the 'bbox' column
for index, row in df.iterrows():
    df.at[index, 'bbox'] = point_within_raster_extent(row['x_cart'], row['y_cart'])

# check the results for debugging
print(df[['x_cart', 'y_cart', 'bbox']].head())

print (df.head)
df.to_csv(os.path.join(output_dir,'filtered_datacube.csv'), index=False)

# function to calculate pixel indices
def calculate_pixel_indices(x_cart, y_cart):
    # Calculate pixel indices
    pixel_col = int((x_cart - raster_geo[0]) / raster_geo[1])  # Column index
    pixel_row = int((y_cart - raster_geo[3]) / raster_geo[5])  # Row index
    return pixel_row, pixel_col

# initialize pixel indices columns
df['pixel_row'] = np.nan
df['pixel_col'] = np.nan

# assign pixel indices based on transformed coordinates for rows where bbox is True
for index, row in df[df['bbox']].iterrows(): # or ['bbox' = 'True']
    pixel_row, pixel_col = calculate_pixel_indices(row['x_cart'], row['y_cart'])
    df.at[index, 'pixel_row'] = pixel_row
    df.at[index, 'pixel_col'] = pixel_col

# save updated dataframe to new csv
df.to_csv(output_csv_path, index=False)

print(f"Indexed data saved to {output_csv_path}.")

# calculate pixel counts
pixel_counts = df[df['bbox']].groupby(['pixel_row', 'pixel_col']).size()

# create new GeoTIFF dataset for writing
driver = gdal.GetDriverByName('GTiff')
new_raster = driver.Create(new_raster_path, raster_ds.RasterXSize, raster_ds.RasterYSize, 2, gdal.GDT_Int16)  # Create new raster with 2 bands

# check if the new raster was created successfully
if new_raster is None:
    raise Exception(f"Failed to create new raster file: {new_raster_path}")

# set the projection to EPSG:25831
srs = osr.SpatialReference()
srs.ImportFromEPSG(25831)
new_raster.SetProjection(srs.ExportToWkt())

# set the GeoTransform to match the original raster
original_band_data = raster_band.ReadAsArray()
new_raster.SetGeoTransform(raster_geo)

# write original band data to the new raster
new_raster.GetRasterBand(1).WriteArray(raster_band.ReadAsArray())

# to set no data value in band 1 of new raster
new_raster.GetRasterBand(1).SetNoDataValue(nodata_value)

# get the array with counts (band 2)
counts_array = np.zeros((raster_ds.RasterYSize, raster_ds.RasterXSize), dtype=np.float32)

# populate counts_array with pixel counts
for (row, col), count in pixel_counts.items():
    # ensure row and col are integers
    row = int(row)
    col = int(col)
    # assign count to counts_array
    counts_array[row, col] = count

# to exclude occurrences beyond input raster: apply nodata values mask from band 1 to band 2
counts_array[original_band_data == nodata_value] = nodata_value

# write counts_array to band 2 of the new raster
new_band = new_raster.GetRasterBand(2)
new_band.WriteArray(counts_array)
new_band.SetNoDataValue(nodata_value) # set no data value from band 1

# save and close the new raster
new_band.FlushCache()
new_raster.FlushCache()
new_raster = None  # close dataset

print(f"Number of rows in each pixel written to {new_raster_path}.")