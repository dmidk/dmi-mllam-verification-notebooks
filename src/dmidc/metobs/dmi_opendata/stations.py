import geopandas as gpd
import inflection
import isodate
import xarray as xr
from shapely.geometry import Point

from . import remote_api
from .time_utils import construct_time_interval, normalise_time_argument


def get_stations(observation_time=None, bbox=None, as_dataframe=False, **kwargs):
    """
    Get stations from the DMI Open Data API.

    Parameters
    ----------
    observation_time : slice(datetime.datetime, datetime.datetime), optional
        Time range to filter stations by. If None, all stations are returned.
    bbox : list of float, optional
        Bounding box to filter stations by. If None, all stations are returned.
        Format: [lon_min, lat_min, lon_max, lat_max]
    as_dataframe : bool, optional
        If True, return a pandas DataFrame instead of an xarray Dataset.
        Defaults to False.
    **kwargs : dict, optional
        Additional keyword arguments to pass to the API.
        See https://confluence.govcloud.dk/display/FDAPI/Meteorological+Observation+API
        for more information.
        
    Returns
    -------
    xarray.Dataset or pandas.DataFrame
        Dataset or DataFrame with station information.
    """
    if bbox is not None:
        kwargs["bbox"] = bbox

    if observation_time is not None:
        observation_time = normalise_time_argument(
            observation_time, allow_date=True
        )
        if isinstance(observation_time, slice):
            if observation_time.step is not None:
                raise ValueError("Step not supported")
            kwargs["datetime"] = construct_time_interval(
                observation_time.start, observation_time.stop
            )
        else:
            raise NotImplementedError("Only time ranges are supported")

    api = remote_api.get_api_handle()
    result = api.collection_items(collection_id="station", **kwargs)
    df = gpd.GeoDataFrame.from_features(result)

    # convert column names from camel case to snake case
    df.columns = [inflection.underscore(col) for col in df.columns]

    if as_dataframe:
        return df
    else:
        return convert_stations_df_to_dataset(df)


def get_nearest_station(pt: dict, observation_time=None, as_dataframe=False):
    """
    Return the nearest station to the given point `pt` given as a dict with
    keys 'lon' and 'lat'.

    Some locations have multiple stations entries on Frie Data with each having
    different periods of validity. By providing an observation time only stations providing
    data within that time range are returned.

    Parameters
    ----------
    pt : dict
        dict with keys 'lon' and 'lat' giving the longitude and latitude of the point

    observation_time : slice(datetime.datetime, datetime.datetime), optional
    """
    if not isinstance(pt, dict) or set(pt.keys()) != {"lon", "lat"}:
        raise ValueError("`pt` must be a dict with keys 'lon' and 'lat'")

    pt = Point(pt["lon"], pt["lat"])

    # we keep the result as a geopandas.GeoDataFrame to be able to use the
    # spatial index for finding the nearest station by lat/lon coordinate
    df_stations = get_stations(observation_time=observation_time, as_dataframe=True)
    locs = df_stations.geometry.sindex.nearest(pt)[1]

    df_nearest_station = df_stations.iloc[locs]
    if as_dataframe:
        return df_nearest_station
    else:
        return convert_stations_df_to_dataset(df_nearest_station)


def convert_stations_df_to_dataset(df):
    variables_to_keep = dict(
        name="station_name",
        lat="lat",
        lon="lon",
        station_height="station_height",
    )
    df = df.copy()
    df["lon"], df["lat"] = df.geometry.x, df.geometry.y

    df["valid_from"] = df.valid_from.apply(
        lambda v: v and isodate.parse_datetime or None
    )
    df["valid_to"] = df.valid_to.apply(lambda v: v and isodate.parse_datetime or None)

    df.set_index("station_id", inplace=True)
    # df = df_stations.pivot(index="station_id", values="geometry")
    ds_stations = xr.Dataset.from_dataframe(df[variables_to_keep.keys()]).rename(
        variables_to_keep
    )

    ds_stations["station_height"].attrs["units"] = "m"

    return ds_stations
