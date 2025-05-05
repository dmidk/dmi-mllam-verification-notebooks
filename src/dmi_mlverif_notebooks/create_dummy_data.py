import argparse
import random
import numpy as np
import xarray as xr
import fsspec

def apply_perturbations(ds, trends, error_magnitudes):
    """
    Apply random error and trends to the dataset.

    The trend is applied per timestep, i.e., the trend is multiplied by the time coordinate
    for each timestep, and random error is added based on the provided magnitudes.

    Parameters:
    - ds: xarray Dataset
    - trends: Dictionary with variable names and trends (e.g., {'cape_column': 0.1}). The trend is applied per timestep.
    - error_magnitudes: Dictionary with variable names and error magnitudes (e.g., {'cape_column': 0.05})
    
    Returns:
    - perturbed_ds: xarray Dataset with applied perturbations
    """
    perturbed_ds = ds.copy()

    for var in ds.data_vars:
        if var in trends:
            trend = trends[var]
            error_magnitude = error_magnitudes.get(var, 0)

            # Apply trend (e.g., linearly changing)
            perturbed_ds[var] = ds[var] + trend * ds['time']

            # Add random error based on a normal distribution
            perturbed_ds[var] += np.random.normal(0, error_magnitude, size=ds[var].shape)

    return perturbed_ds

def read_zarr_from_path(path):
    """Read a Zarr file from a path (including S3 URLs)."""
    return xr.open_zarr(path, consolidated=False)

def write_zarr_to_path(ds, output_path):
    """Write a Zarr dataset to a path (including S3 URLs)."""
    ds.to_zarr(output_path, mode='w')

def parse_trend_or_error(value):
    """Parse the trend or error argument (e.g., 'cape_column=0.1' -> ('cape_column', 0.1))"""
    var, val = value.split('=')
    return var, float(val)

def main():
    parser = argparse.ArgumentParser(description="Apply trends and random errors to a Zarr dataset.")
    parser.add_argument("input_path", help="Input path of the Zarr dataset (e.g., s3://path/to/dataset.zarr/)")
    parser.add_argument("output_path", help="Output path for the perturbed Zarr dataset (e.g., s3://path/to/output.zarr/)")
    
    # Example for trend and error magnitudes using '=' syntax
    parser.add_argument("--trend", nargs='+', type=parse_trend_or_error, 
                        help="Trend to apply (variable name=trend value). E.g., --trend cape_column=0.1 t2m=-0.05", required=True)
    parser.add_argument("--error", nargs='+', type=parse_trend_or_error, 
                        help="Random error magnitude (variable name=error magnitude). E.g., --error cape_column=0.03 t2m=0.01", required=True)

    args = parser.parse_args()

    # Parse trend arguments into a dictionary
    trends = dict(args.trend)
    
    # Parse error magnitude arguments into a dictionary
    error_magnitudes = dict(args.error)

    # Load the dataset
    ds = read_zarr_from_path(args.input_path)

    # Apply perturbations to the dataset
    perturbed_ds = apply_perturbations(ds, trends, error_magnitudes)

    # Write the perturbed dataset to the output path
    write_zarr_to_path(perturbed_ds, args.output_path)

    print(f"Perturbed dataset written to {args.output_path}")

if __name__ == "__main__":
    main()
