"""
Purpose: this block counts the number of GBIF species occurrences in pixels of the input raster dataset for the defined species or classes.

INPUT
- Raster dataset in any coordinate reference system (GeoTIFF). It can represent any natural or social characteristics of area, for example, vegetation classes or land use.
Format: GeoTIFF
Mandatory: yes

- GBIF occurrence datacube with unique records pre-extracted through GBIF occurrence data cube: https://techdocs.gbif.org/en/data-use/data-cubes.
Format: CSV (dataset) and JSON (metadata)
Mandatory: yes

OUTPUT
- Regridded GBIF occurrence datacube inheriting the specifications of the input raster dataset, which has one band with the calculated occurrence count.
Format: GeoTIFF
Mandatory: yes

ISSUES
- GBIF backbone taxonomy does not define Reptilia as a separate class (class with id=358 dedicated to Reptilia database). For the purposes of the case study, two Reptilia classes (Testudines, taxon key 11418114) and (Squamata, taxon key, 11592253) have been used.
- For largest datasets (Aves class) the following issue faced (17739293 records): 
"numpy.core._exceptions._ArrayMemoryError: Unable to allocate 812. MiB for an array with shape (6, 17739293) and data type object".
It is solved by chunking and filtering out records outside of the bounding box.

"""

import pandas as pd
import numpy as np
from osgeo import gdal, ogr, osr, gdalconst
from pyproj import Transformer
import os
import re
import yaml
import warnings
import math

# REDUNDANT - replaced with configuration file
"""
# paths to input and output files
input_dir = 'input/'
output_dir = 'output/'
input_ds = 'ict_2022.tif'
"""

# load configuration from YAML file
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

# load paths from config file
input_dir = config.get('input_dir')
output_dir = config.get('output_dir')
output_dir_gbif = config.get('output_dir_gbif')

# load filenames from config file
input_ds = config.get('input_ds')
gbif_datacube_csv = config.get('gbif_datacube_csv')
""" # REDUNDANT
# gbif_output_datacube = config.get('gbif_datacube_csv') # the same
"""

# load current taxon key(s) 
taxon_key = config.get('gbif_taxon_key')

# path to input raster dataset
raster_path = os.path.join(input_dir, input_ds)
raster_path = os.path.normpath(raster_path)

# path to input GBIF datacube
csv_path = os.path.join(output_dir_gbif, gbif_datacube_csv)
csv_path = os.path.normpath(csv_path)

# path to transformed datacube
output_csv_path = os.path.join(output_dir, gbif_datacube_csv)
output_csv_path = os.path.normpath(output_csv_path) 

# create output directory if doesn't exist
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# for exporting GBIF datacube to a new GeoTIFF file - output filename is the same as input dataset
gbif_datacube_tif = gbif_datacube_csv.replace('.csv', '.tif') # replace the extension
output_raster_path = os.path.join(output_dir, gbif_datacube_tif)

# for exporting GBIF datacube to a new band of input dataset - name from the base_name and extension
"""
# extract the base name (without extension) and the file extension
input_raster_base, extension = os.path.splitext(os.path.basename(input_ds))

# apply the renaming pattern from the config file
output_raster_pattern = config['output_raster']
output_raster = output_raster_pattern.format(input_raster_base=input_raster_base, extension=extension.lstrip('.'))
"""

# debug: print the paths
print(f"Input raster: {raster_path}")
print(f"Input GBIF datacube: {csv_path}")
print(f"Output raster: {output_raster_path}")
print(f"Current GBIF taxon key(s):{taxon_key}")
print("-" * 40)

# TODO - to loop over a list of classes and create a separate geotiff for each of them

"""
issue with classKey=212:
with numpy.core._exceptions._ArrayMemoryError: Unable to allocate 406. MiB for an array with shape (3, 17739293) and data type int64)
"""
# REDUNDANT - for exporting output raster as a band 2 (while keeping the original raster)
"""
# extract the base name of the input raster file and define the name of final raster output
input_filename = os.path.basename(raster_path)
match = re.search(r'(\d{4})', input_filename) # find 4 numbers in a row (year) through regular expression pattern
year_pos = match.start()
output_filename = input_filename[:year_pos] + 'gbif_' + input_filename[year_pos:] # slicing filename before the year position, inserts 'gbif_' and attach the year position with the following text
new_raster_path = os.path.join(output_dir, output_filename)  # output raster
"""

# function to calculate pixel indices
def calculate_pixel_indices(x_cart, y_cart):
    # calculate pixel indices
    pixel_col = int((x_cart - raster_geo[0]) / raster_geo[1])  # column index
    pixel_row = int((y_cart - raster_geo[3]) / raster_geo[5])  # row index
    return pixel_row, pixel_col

# function to check if point is within raster extent
def point_within_raster_extent(x_cart, y_cart):
    return (minx <= x_cart <= maxx) and (miny <= y_cart <= maxy)

## RASTER AND COORDINATES PREPARATION

# import the RasterTransform class from the reprojection module
from raster_proc import RasterTransform  # this imports RasterTransform class

# check the cartesian/projected CRS
print("Checking the coordinate reference system of input raster dataset...")
is_cart, epsg_code = RasterTransform(raster_path).check_cart_crs()

# check the resolution
print("Checking the spatial resolution of input raster dataset...")
xres, yres = RasterTransform(raster_path).check_res()

# define EPSG codes for WGS84 and UTM zone 31N (EPSG:25831)
csv_crs = 'EPSG:4326' # default, because GBIF occurrence datacube always has this EPSG
raster_crs = epsg_code

# function to transform coordinates (in case of Catalonia from EPSG:4326 to EPSG:25831)
def transform_coordinates(lat_array, lon_array):
    transformer = Transformer.from_crs(csv_crs, raster_crs, always_xy=True)
    x, y = transformer.transform(lon_array, lat_array)
    return x, y

# open raster to get its extent
raster_ds = gdal.Open(raster_path)
raster_geo = raster_ds.GetGeoTransform()
raster_band = raster_ds.GetRasterBand(1)
nodata_value = raster_band.GetNoDataValue()  # extract nodata value
    
# calculate raster extent
minx, miny, maxx, maxy = (
    raster_geo[0],  # minx
    raster_geo[3] + raster_geo[5] * raster_ds.RasterYSize,  # miny
    raster_geo[0] + raster_geo[1] * raster_ds.RasterXSize,  # maxx
    raster_geo[3]  # maxy
)
    
# print raster extent for debugging
print("The spatial extent of the input raster dataset:", (minx, miny, maxx, maxy))

# transform coordinates if the EPSG code is not 4326 (doesn't match to CRS of GBIF datacube)
if epsg_code != 4326:
    print(f"The input raster dataset has EPSG code:{epsg_code}, which is different from the projection of GBIF occurrence datacube.")
    
    # previous version to define dataframe without chunks
    """
    # read CSV file with the correct delimiter for SQL TSV ZIP
    df = pd.read_csv(csv_path, delimiter='\t')
    print(f"Processing the following dataset: \n{df.head()}")
    """

    # debug
    """
    # count total records
    df = pd.read_csv(csv_path, delimiter='\t')
    total_records_1 = len(df)
    print (f"Total records: {total_records_1}")
    """

    # to create empty dataframe to store the processed results
    processed_df = pd.DataFrame()
    # to create empty dataframe to store pixel counts
    pixel_counts_df = pd.DataFrame()

    # to read dataframe in chunks
    # chunk the dataframe
    n = 2000000 # chunk row size
    df_chunks = pd.read_csv(csv_path, delimiter='\t', chunksize=n)

    # find out the total number of rows in the CSV file
    total_rows = sum(1 for _ in open(csv_path)) - 1  # subtract 1 for header
    total_chunks = math.ceil(total_rows / n) # round up to the largest whole number

    # initialise a counter of 'False' values in 'bbox' column
    false_count = 0 

    # initialize total number of records in dataframe
    total_records = 0

    ## process each chunk
    # initialise chunk number
    chunk_num = 1
    for chunk in df_chunks:
        # print progress
        print(f"Processing chunk {chunk_num} out of {total_chunks}...")
    
        """
        print(chunk.head())  # debug: printing chunk
        """

        # count records in chunk
        chunk_records = len(chunk)
        # update the total number of records (increment)
        total_records += chunk_records

        # apply the function to each row in the dataframe to get transformed coordinates
        print("Proceeding with coordinate transformation...")
        chunk['x_cart'], chunk['y_cart'] = transform_coordinates(chunk['lat'].values, chunk['lon'].values)
        print("Coordinates have been converted")
        """print(f"Converted coordinates saved to {output_csv_path}.")"""

        """
        # debug:
        print(df[['x_cart', 'y_cart']].head())
        """
    
        # initialize the 'bbox' boolean column with False
        chunk['bbox'] = False
    
        # iterate through each row and update the 'bbox' column
        for index, row in chunk.iterrows():
            chunk.at[index, 'bbox'] = point_within_raster_extent(row['x_cart'], row['y_cart'])
            if chunk.at[index, 'bbox'] == False:
                false_count += 1
                warnings.warn("Occurrence record(s) found outside of the bounding box of input raster dataset!")

        # filter rows where bbox is True
        bbox_true_df = chunk[chunk['bbox']]

        # initialize 'pixel_row' and 'pixel_col' columns
        bbox_true_df.loc[:, 'pixel_row'] = None # use .loc to set values to avoid the SettingWithCopyWarning (unpredictable behaviour)
        bbox_true_df.loc[:, 'pixel_col'] = None

        # assign pixel indices based on transformed coordinates for rows where bbox is True
        for index, row in bbox_true_df.iterrows(): # or ['bbox' = 'True']
            pixel_row, pixel_col = calculate_pixel_indices(row['x_cart'], row['y_cart'])
            bbox_true_df.at[index, 'pixel_row'] = pixel_row
            bbox_true_df.at[index, 'pixel_col'] = pixel_col

        # update the chunk with the pixel row and column values
        chunk.update(bbox_true_df)

        # append the processed chunk to the results DataFrame
        processed_df = pd.concat([processed_df, chunk], ignore_index=True)

        # calculate pixel counts for the current chunk 
        pixel_counts_chunk = bbox_true_df.groupby(['pixel_row', 'pixel_col']).size()
        # update the overall counts of rows in each pixel
        pixel_counts_df = pd.concat([pixel_counts_df, pixel_counts_chunk], axis=0, sort=False)

        # increment chunk number
        chunk_num += 1

    # calculate the share of records outside of the bounding box (for Catalonia bbox it is okay - we are fetching the datacube from Spain)
    false_share = false_count/total_records
    print(f"The share of records outside of the bounding box is {false_share:.2%}.")
    print("-"*40)

    # debug: check the reprojected coordinates
    """
    print(df[['x_cart', 'y_cart', 'bbox']].head())
    """

else:
    print("The input raster dataset has EPSG:4326. No need to transform coordinates of GBIF occurrences.")

# debug: print headers
"""
print (f"Headers of the intermediate dataframe are: {list(df.columns)}")
"""

# debug: to save reprojected and filtered dataframe to separate csv
"""
df.to_csv(os.path.join(output_dir,'filtered_datacube.csv'), index=False)
"""

"""
# debug: save updated dataframe to new csv
df.to_csv(output_csv_path, index=False)
print(f"Indexed data saved to {output_csv_path}.")
"""

# REDUNDANT - previous version for non-chunked dataframe
"""
# calculate pixel counts
pixel_counts = df[df['bbox']].groupby(['pixel_row', 'pixel_col']).size()
"""

# create output GeoTIFF dataset for writing with a single band (for pixel counts)
driver = gdal.GetDriverByName('GTiff')
output_raster = driver.Create(output_raster_path, raster_ds.RasterXSize, raster_ds.RasterYSize, 1, gdal.GDT_Int16)  # create new raster with 1 band

# check if the output raster was created successfully
if output_raster_path is None:
    raise Exception(f"Failed to create output raster file: {output_raster_path}")

# set the projection to the CRS of the input raster dataset
srs = osr.SpatialReference()
srs.ImportFromEPSG(int(epsg_code)) # explicitly cast epsg code to integer, otherwise might cause issue
output_raster.SetProjection(srs.ExportToWkt())

# set the GeoTransform to match the original raster
output_raster.SetGeoTransform(raster_geo)

# get the array with counts (only one band needed now)
counts_array = np.zeros((raster_ds.RasterYSize, raster_ds.RasterXSize), dtype=np.int32)

# debug: to print for understanding the type of output dataframe (should be tuple)
"""
print(type(pixel_counts_df))
print(pixel_counts_df.head())
"""

# populate counts_array with pixel counts
for (row, col), count in pixel_counts_df.itertuples():
    # ensure row and col are integers
    row = int(row)
    col = int(col)
    # assign count to counts_array
    counts_array[row, col] = count


# to exclude occurrences beyond input raster: apply nodata values mask from original raster band to count array
nodata_value = raster_band.GetNoDataValue()  # getnodata value from the original raster
original_band_data = raster_band.ReadAsArray()  # read original band data to get nodata mask
counts_array[original_band_data == nodata_value] = nodata_value  # apply nodata mask

# write counts_array to the first and only band of the output raster
output_band = output_raster.GetRasterBand(1)
output_band.WriteArray(counts_array)
output_band.SetNoDataValue(nodata_value)  # set the same nodata values

print(f"Output raster dataset has been written to {output_raster_path}.")

# save and close the output raster
output_band.FlushCache()
output_raster.FlushCache()
output_raster = None  # close dataset

# Alternative block - to write the GBIF datacube into a new band while keeping the input data in band 1
"""
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

# TODO - fix - decimal values are not saved in band 1 (all casted to integer)

# write counts_array to band 2 of the new raster
new_band = new_raster.GetRasterBand(2)
new_band.WriteArray(counts_array)
new_band.SetNoDataValue(nodata_value) # set no data value from band 1

# save and close the new raster
new_band.FlushCache()
new_raster.FlushCache()
new_raster = None  # close dataset

print(f"Number of rows in each pixel written to {new_raster_path}.")
"""