from pathlib import Path

import pandas as pd

FP_PARAMS_DF = Path(__file__).parent / "opendata_metobs_parameters.csv"

PARAMS_DF = pd.read_csv(FP_PARAMS_DF)

PARAMETER_UNITS = dict(zip(PARAMS_DF["name"], PARAMS_DF["unit"]))
PARAMETER_LONG_NAMES = dict(zip(PARAMS_DF["name"], PARAMS_DF["description"]))
