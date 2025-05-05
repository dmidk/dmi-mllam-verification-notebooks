from typing import List, Union

import geopandas as gpd
import isodate
import numpy as np
import pandas as pd
import xarray as xr
from bidict import bidict
from loguru import logger

from . import parameter_metainfo, remote_api
from .time_utils import construct_time_interval, normalise_time_argument

DMIDC_OPENDATA_PARAM_MAP = bidict(
    observation_time="observed",
    creation_time="created",
    station_id="stationId",
    parameter="parameterId",
    bbox="bbox",
)


def convert_obs_df_to_dataset(df, multiple_stations=False):
    # xarray doesn't like timezones (https://github.com/pydata/xarray/issues/3291) so convert to UTC here
    def _remove_timezone(t):
        return t.dt.tz_localize(None)

    df["observation_time"] = _remove_timezone(df.observation_time)
    df["creation_time"] = _remove_timezone(df.creation_time)

    # Pivot so we get a variable in the dataset for each parameter
    if multiple_stations:
        index = ["station_id", "observation_time"]
    else:
        index = ["observation_time"]
    df_pivoted = df.pivot(index=index, columns="parameter", values="value")

    # Convert to xarray Dataset
    ds = xr.Dataset.from_dataframe(df_pivoted)

    # rename observation_time to time so that time coordinate is the same
    # across different data sources in dmidc
    ds = ds.rename(observation_time="time")

    for var_name in ds.data_vars:
        units = parameter_metainfo.PARAMETER_UNITS.get(var_name)
        if units is None:
            raise Exception(f"Unknown units for parameter: {var_name}")
        long_name = parameter_metainfo.PARAMETER_LONG_NAMES.get(var_name)
        if long_name is None:
            raise Exception(f"Unknown long name for parameter: {var_name}")

        ds[var_name].attrs["units"] = units
        ds[var_name].attrs["long_name"] = long_name

    return ds


def _dmidc_to_opendata_params(params):
    return {
        DMIDC_OPENDATA_PARAM_MAP.get(key, key): value for key, value in params.items()
    }


def _opendata_to_dmidc_params(params):
    return {
        DMIDC_OPENDATA_PARAM_MAP.inverse[key]: value for key, value in params.items()
    }


def _is_listlike(obj):
    return isinstance(obj, (list, tuple, set)) or (
        isinstance(obj, np.ndarray) and obj.ndim == 1
    )


def load(
    observation_time,
    parameter: Union[str, List[str]] = None,
    bbox=None,
    as_dataframe=False,
    station_id=None,
    **kwargs,
):
    """
    Load meteorological observation data from the Open Data API

    See https://confluence.govcloud.dk/display/FDAPI/Meteorological+Observation+API for more information.

    Parameters
    ----------
    observation_time : slice(datetime.datetime, datetime.datetime)
        Time range to load data for
    parameter : str or list of str or None
        Parameter(s) to load data for. Defaults to None, which loads all parameters
        as defined in `dmidc.metobs.dmi_opendata.parameter_metainfo.PARAMS_DF`
    bbox : tuple of float
        Bounding box to load data for given as [W, S, E, N]
    as_dataframe : bool
        If True, return a pandas DataFrame instead of an xarray Dataset
    station_id : str or int or None
        Station ID to load data for. If None, load data for all stations.

    Returns
    -------
    xarray.Dataset or pandas.DataFrame
        Dataset or DataFrame with data for the given time range and parameter(s)
    """
    observation_time = normalise_time_argument(observation_time, allow_date=True)
    api = remote_api.get_api_handle()

    if station_id is None:
        # with station_id = None, we want to load data for all stations
        # that can be handled by the API by setting station_id to an empty string
        pass
    elif _is_listlike(station_id):
        station_ids = station_id
        del station_id
        outputs = []
        for station_id in station_ids:
            output = load(
                observation_time=observation_time,
                parameter=parameter,
                bbox=bbox,
                as_dataframe=as_dataframe,
                station_id=station_id,
                **kwargs,
            )
            if not as_dataframe:
                output = output.expand_dims(station_id=[station_id])
            outputs.append(output)

        if as_dataframe:
            return pd.concat(outputs)
        else:
            return xr.concat(outputs, dim="station_id")
    elif isinstance(station_id, str):
        kwargs["station_id"] = station_id
    elif isinstance(station_id, int):
        kwargs["station_id"] = f"{station_id:05d}"
    else:
        raise ValueError(f"Invalid station_id type: {type(station_id)}")

    if bbox is not None:
        kwargs["bbox"] = bbox

    if isinstance(observation_time, slice):
        if observation_time.step is not None:
            raise ValueError("Step not supported")
        kwargs["datetime"] = construct_time_interval(
            observation_time.start, observation_time.stop
        )
    else:
        raise NotImplementedError("Only time ranges are supported")

    if isinstance(parameter, str):
        parameters = [parameter]
    elif isinstance(parameter, list):
        parameters = parameter
    elif parameter is None:
        parameters = parameter_metainfo.PARAMS_DF.name.to_list()
    else:
        raise ValueError(f"Invalid parameter type: {type(parameter)}")

    dfs = []
    for parameter in parameters:
        api_params = dict(parameter=parameter, **kwargs)
        result = api.collection_items(
            collection_id="observation", **_dmidc_to_opendata_params(api_params)
        )
        df = gpd.GeoDataFrame.from_features(result)
        if len(df) == 0:
            logger.warning(
                f"No data found for parameter {parameter} with query params: {kwargs}"
            )
        dfs.append(df)

    df = gpd.GeoDataFrame(pd.concat(dfs, ignore_index=True))

    # convert Open Data API parameter names to DMIDC parameter names
    df.columns = [DMIDC_OPENDATA_PARAM_MAP.inverse.get(col, col) for col in df.columns]

    if len(df) > 0:
        # timestamps are strings, convert to datetime
        df["observation_time"] = df.observation_time.apply(isodate.parse_datetime)
        df["creation_time"] = df.creation_time.apply(isodate.parse_datetime)

    if as_dataframe:
        return df
    else:
        if len(df) == 0:
            raise Exception("No data found")
        multiple_stations = station_id is None or _is_listlike(station_id)
        return convert_obs_df_to_dataset(df, multiple_stations=multiple_stations)
