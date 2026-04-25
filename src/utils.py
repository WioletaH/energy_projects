import re
import pandas as pd


def clean_numeric(series):
    return pd.to_numeric(
        series.astype(str).str.replace(",", ".", regex=False),
        errors="coerce"
    )


def extract_max_voltage(voltage):
    """
    Extract maximum voltage in kV from OSM voltage strings.
    Examples:
      '110000'          -> 110.0
      '110000;220000'   -> 220.0
      '10 kV; 110 kV'  -> 110.0
    Returns pd.NA when voltage is missing or unparseable. pd.isna -> idicates whether values are missing
    """
    if pd.isna(voltage):
        return pd.NA

    text = str(voltage).lower().replace(",", ".")
    nums = re.findall(r"\d+(?:\.\d+)?", text)

    if not nums:
        return pd.NA

    values = [float(n) for n in nums]

    # OSM stores voltage in volts; convert values > 1000 to kV
    values_kv = [v / 1000 if v > 1000 else v for v in values]

    return max(values_kv)


def classify_voltage(voltage_kv):
    """
    Map a numeric kV value to a human-readable voltage class.
    Returns 'unknown' when voltage_kv is None / NA.
    """
    try:
        v = float(voltage_kv)
    except (TypeError, ValueError):
        return "unknown"

    if v >= 220:
        return "extra_high_voltage"
    if v >= 110:
        return "high_voltage"
    if v >= 30:
        return "medium_voltage"
    return "low_voltage"