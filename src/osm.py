import osmnx as ox
import geopandas as gpd
from utils import extract_max_voltage, classify_voltage


PROJECTED_CRS = "EPSG:3035"

def load_substations():
    subs = ox.features_from_place(
        "Brandenburg, Germany",
        tags={"power": "substation"}
    ).reset_index()

    subs = subs[subs.geometry.notna()].copy()

    candidate_cols = ["osmid", "name", "operator", "voltage", "substation", "geometry"]
    existing_cols = [c for c in candidate_cols if c in subs.columns]
    subs = subs[existing_cols].copy()

    if "osmid" not in subs.columns:
        subs["osmid"] = subs.index.astype(str)

    subs = subs.rename(columns={
        "osmid": "substation_id",
        "name": "substation_name",
        "operator": "substation_operator",
        "voltage": "substation_voltage",
        "substation": "substation_type"
    })

    subs = subs.to_crs(PROJECTED_CRS)
    subs["geometry"] = subs.geometry.centroid

    return subs