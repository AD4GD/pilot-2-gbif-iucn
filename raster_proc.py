# reprojection.py
# includes a few methods to optimise transformations between raster files (minimum and maximum coordinates of raster dataset (bounding box) into WGS84, according to the config.yaml file))
# should be imported as a class

from osgeo import gdal, osr
import pyproj
import warnings

class RasterTransform:
    def __init__(self, raster_path):
        self.raster_path = raster_path
        self.epsg_code = None
        self.x_min_before = None
        self.y_min_before = None
        self.x_max_before = None
        self.y_max_before = None

    def get_raster_info(self):

        raster = gdal.Open(self.raster_path)
        if raster is None:
            raise FileNotFoundError("Input raster is missing.")
        
        geo_transform = raster.GetGeoTransform() # gdal.GetGeoTransform is a method and should be called as (). So, it should be defined as a variable
        if not geo_transform:
            raise RuntimeError("Geotransform is not available in the raster.")
        
        # fetch max/min coordinates to use them later
        # TODO - to check again!
        self.x_min_before = geo_transform[0]  # Top-left x
        self.y_max_before = geo_transform[3]  # Top-left y
        self.x_max_before = self.x_min_before + geo_transform[1] * raster.RasterXSize
        self.y_min_before = self.y_max_before + geo_transform[5] * raster.RasterYSize  

        # fetch spatial resolution
        xres = geo_transform[1]
        yres = geo_transform[5]
        cell_size = abs(xres)

        # extract projection system of input raster file
        info = gdal.Info(raster, format='json')
        print (f"Input raster dataset {self.raster_path} was opened successfully.")
        if 'coordinateSystem' in info and 'wkt' in info['coordinateSystem']:
            srs = osr.SpatialReference(wkt=info['coordinateSystem']['wkt'])
            if srs.IsProjected():
                self.epsg_code = srs.GetAttrValue("AUTHORITY", 1)
                print (f"Coordinate reference system of the input raster dataset is EPSG:{self.epsg_code}")
            else:
                raise ValueError("Input raster does not have a projected coordinate system.")
        else:
            raise ValueError("No projection information found in the input raster.")

        # close the raster to keep memory empty
        raster = None

        return self.x_min_before, self.x_max_before, self.y_min_before, self.y_max_before, cell_size
    
    def check_cart_crs(self):
        """
        This function checks if the CRS of the input raster dataset is projected (Cartesian)
        and returns the EPSG code if available.

        Returns:
        - is_cartesian: A boolean indicating if the CRS is projected (True) or not (False).
        - epsg_code: The EPSG code of the CRS, or None if it couldn't be determined.
        """
        dataset = gdal.Open(self.raster_path)
        is_cartesian = False
        epsg_code = None

        if dataset:
            try:
                # get the projection information
                projection = dataset.GetProjection()
                srs = osr.SpatialReference()
                srs.ImportFromWkt(projection)

                # check if the CRS is projected (Cartesian)
                is_cartesian = srs.IsProjected()

                # get EPSG code
                epsg_code = srs.GetAttrValue("AUTHORITY", 1)

            except Exception as e:
                warning_message_2 = f"An error occurred while processing the raster dataset: {e}"
                print("-" * 40)
                warnings.warn(warning_message_2, Warning)

            finally:
                dataset = None  # close the dataset to free resources

        else:
            warning_message_2 = "Failed to open the raster dataset. Please check the path and format of the input raster."
            warnings.warn(warning_message_2, Warning)
            print("-" * 40)

        # display a warning if the CRS is not Cartesian
        if not is_cartesian:
            warning_message_3 = f"The CRS is not the Cartesian (projected) one (EPSG code - {epsg_code})."
            warnings.warn(warning_message_3, Warning)
            print("-" * 40)
        else:
            print(f"The CRS of your input raster dataset is Cartesian (projected). EPSG code is {epsg_code}.")
            print("-" * 40)

        return is_cartesian, epsg_code

        # Example usage:
        # is_cart, epsg = check_cart_crs(self)

    def check_res (self):
        raster = gdal.Open(self.raster_path)
        if raster is None:
            raise FileNotFoundError("Input raster is missing.")
            print("-" * 40)
        
        geo_transform = raster.GetGeoTransform() # gdal.GetGeoTransform is a method and should be called as (). So, it should be defined as a variable
        if not geo_transform:
            raise RuntimeError("Geotransform is not available in the raster.")
            print("-" * 40)
        
        xres = geo_transform[1]
        yres = geo_transform[5]

        # compare absolute values, because the y value might be represented in negative coordinates
        if abs(xres) != abs(yres):
            print ("x:",xres,"y:",yres)
            warning_message = f"Spatial resolution (x and y values) of input raster is inconsistent."
            warnings.warn(warning_message, Warning)
            print("-" * 40)
        else:
            print (f"Good news! The spatial resolution of your raster data is consistent between X ({xres}) and Y ({yres}).")
            print("-" * 40)

        return xres, yres

    def transform_coordinates(self):
        if self.epsg_code is None:
            raise ValueError("EPSG code is not set. Did you call get_raster_info?")

        # to transform coordinates into WGS 84
        transform_cart_to_geog = pyproj.Transformer.from_crs(
            pyproj.CRS(f'EPSG:{self.epsg_code}'),
            pyproj.CRS('EPSG:4326'),
            always_xy=True # to ensure that coordinates are always treated as (x, y).
        )
        

        x_min_after, y_min_after = transform_cart_to_geog.transform(self.x_min_before, self.y_min_before)
        x_max_after, y_max_after = transform_cart_to_geog.transform(self.x_max_before, self.y_max_before)

        return x_min_after, y_min_after, x_max_after, y_max_after

    # run transformation of coordinates
    def transform_and_print(self):

        """
        Transforms coordinates and prints spatial resolution and bounding box details.
        """
        # fetch raster information
        _, _, _, _, cell_size = self.get_raster_info()
        x_min_after, y_min_after, x_max_after, y_max_after = self.transform_coordinates()

        print (f"Spatial resolution (pixel size) is {cell_size} meters")

        # print the coordinates before transformation
        print("Before reprojection:")
        print("x_min:", self.x_min_before)
        print("x_max:", self.x_max_before)
        print("y_min:", self.y_min_before)
        print("y_max:", self.y_max_before)

        # print the coordinates after transformation
        print("After reprojection:")
        print("x_min:", x_min_after)
        print("x_max:", x_max_after)
        print("y_min:", y_min_after)
        print("y_max:", y_max_after)

        bbox = f"{x_min_after},{y_min_after},{x_max_after},{y_max_after}"
        print("Bounding box:", bbox)

    def bbox_to_WGS84(self):
        """
        This method calculates the bounding box coordinates of the raster in WGS84.

        Returns:
        - cell_size: The spatial resolution of the raster.
        - x_min_after, y_min_after, x_max_after, y_max_after: Transformed coordinates in WGS84.
        """

        self.transform_and_print()  # transform coordinates and print transformed values
        x_min_after, y_min_after, x_max_after, y_max_after = self.transform_coordinates()
        return x_min_after, y_min_after, x_max_after, y_max_after
    
# Example usage
# raster_file = os.path.join(input_dir,'lulc.tif')
# raster_transform = RasterTransform(raster_file)
# x_min, y_min, x_max, y_max = raster_transform.bbox_to_WGS84()
# or
# x_min, y_min, x_max, y_max = RasterTransform(raster_file).bbox_to_WGS84()
