import isodate
import xarray as xr

def load(analysis_time, data_kind="single_levels"):
    uri_dini = f"s3://harmonie-zarr/dini/control/{isodate.datetime_isoformat(analysis_time).replace(':', '')}/{data_kind}.zarr"
    print(f"Loading model data from {uri_dini}")
    
    return xr.open_zarr(uri_dini)