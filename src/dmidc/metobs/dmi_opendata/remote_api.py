from owslib.ogcapi.features import Features
import dotenv
import os

URL_API = "https://dmigw.govcloud.dk/v2/metObs"
API_KEY_ENV_VAR = "DMI_OPENDATA_API_KEY"


def fetch_api_key_from_dotenv():
    """
    Fetch the API key from the .env file.
    """
    try:
        dotenv.load_dotenv()
        if API_KEY_ENV_VAR not in os.environ:
            raise ValueError(f"{API_KEY_ENV_VAR} not found in .env file or environment variables.")
        return os.getenv(API_KEY_ENV_VAR)
    except ImportError:
        raise ImportError("Please install python-dotenv to use this function.")


def get_api_handle():
    api_key = fetch_api_key_from_dotenv()
    headers = {"X-Gravitee-Api-Key": api_key}
    api = Features(URL_API, headers=headers)
    api.conformance()
    return api
