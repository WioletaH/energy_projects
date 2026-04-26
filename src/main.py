"""
ETL pipeline: Brandenburg wind & solar energy potential
"""

import os
import pandas as pd
import geopandas as gpd
from osm import load_substations
from utils import clean_numeric
from map import create_map

# Quick and simple assumptions for capacity factor and annual energy estimation.

HOURS_PER_YEAR = 8_760

# Capacity factors encode the core "weather/performance" assumption:
#   Wind  – ~30 % (typical onshore Brandenburg, P50 long-term yield)
#   Solar – ~12 % (typical northeast Germany horizontal irradiance) - estimations based on Fraunhofer report 
CAPACITY_FACTORS = {
    "Wind":                    0.30,
    "Solare Strahlungsenergie": 0.12,
}

PROJECTED_CRS  = "EPSG:3035"
GEOGRAPHIC_CRS = "EPSG:4326"

PLANTS_FILE = "data/Stromerzeuger.csv"


# Plant data loading https://www.marktstammdatenregister.de/MaStR/Einheit/Einheiten/OeffentlicheEinheitenuebersicht

def load_plants() -> gpd.GeoDataFrame:
    df = pd.read_csv(PLANTS_FILE, sep=";", low_memory=False)
    df.columns = df.columns.str.strip()

    df = df[
        (df["Bundesland"] == "Brandenburg") &
        (df["Energieträger"].isin(CAPACITY_FACTORS.keys()))
    ].copy()

    df["capacity_kw"] = clean_numeric(df["Nettonennleistung der Einheit"])
    df["capacity_mw"] = df["capacity_kw"] / 1_000

    df["lat"] = clean_numeric(df["Koordinate: Breitengrad (WGS84)"])
    df["lon"] = clean_numeric(df["Koordinate: Längengrad (WGS84)"])

    df = df.dropna(subset=["capacity_mw", "lat", "lon"]).copy()

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs=GEOGRAPHIC_CRS,
    )

    gdf["capacity_factor"] = gdf["Energieträger"].map(CAPACITY_FACTORS)
    gdf["energy_mwh_annual"] = (
        gdf["capacity_mw"] * HOURS_PER_YEAR * gdf["capacity_factor"]
    )

    gdf = gdf.rename(columns={
        "MaStR-Nr. der Einheit":        "plant_id",
        "Anzeige-Name der Einheit":     "plant_name",
        "Energieträger":                "technology",
        "Ort":                          "plant_ort",
        "Gemeinde":                     "plant_municipality",
        "Inbetriebnahmedatum der Einheit": "commissioning_date",
        "Spannungsebene":               "grid_connection_level",
    })

    return gdf


# Main
def main():
    os.makedirs("outputs", exist_ok=True)

    # --- load ---
    plants      = load_plants()
    substations = load_substations()

    # --- spatial join: each plant → nearest substation ---
    plants_proj = plants.to_crs(PROJECTED_CRS)
    subs_proj   = substations.to_crs(PROJECTED_CRS)

    joined = gpd.sjoin_nearest(
        plants_proj,
        subs_proj,
        how="left",
        distance_col="distance_m",
    )

    # --- substation-level aggregation ---
    summary = (
        joined.dropna(subset=["substation_id"])
        .groupby(["substation_id", "substation_name"], dropna=False)
        .agg(
            total_capacity_mw         = ("capacity_mw",        "sum"),
            total_energy_mwh_annual   = ("energy_mwh_annual",  "sum"),
            n_plants                  = ("plant_id",            "count"),
            n_wind                    = ("technology",          lambda s: (s == "Wind").sum()),
            n_solar                   = ("technology",          lambda s: (s == "Solare Strahlungsenergie").sum()),
            avg_distance_m            = ("distance_m",          "mean"),
        )
        .reset_index()
    )

    # merge summary + voltage info back to substation geometry
    voltage_cols = ["substation_id", "substation_name", "voltage_kv", "voltage_class"]
    substations_summary = subs_proj.merge(
        summary, on=["substation_id", "substation_name"], how="left"
    )
    # keep voltage columns from the original subs_proj
    for col in ["voltage_kv", "voltage_class"]:
        if col not in substations_summary.columns and col in subs_proj.columns:
            substations_summary = substations_summary.merge(
                subs_proj[["substation_id", col]].drop_duplicates("substation_id"),
                on="substation_id", how="left"
            )

    # --- convert to WGS84 for outputs ---
    joined_out      = joined.to_crs(GEOGRAPHIC_CRS)
    substations_out = substations_summary.to_crs(GEOGRAPHIC_CRS)


    # Plant-level dataset
    plant_cols = [c for c in [
        "plant_id", "plant_name", "technology",
        "plant_municipality", "plant_ort",
        "commissioning_date", "grid_connection_level",
        "capacity_mw", "capacity_factor", "energy_mwh_annual",
        "substation_id", "substation_name",
        "voltage_kv", "voltage_class",
        "distance_m",
        "geometry",
    ] if c in joined_out.columns]

    plants_out = joined_out[plant_cols].copy()

    # flat CSV (no geometry)
    plants_out.drop(columns="geometry").to_csv(
        "outputs/plants.csv", index=False
    )
    # GeoJSON (with geometry)
    plants_out.to_file(
        "outputs/plants_with_substations.geojson", driver="GeoJSON"
    )

    # Substation-level dataset

    sub_cols = [c for c in [
        "substation_id", "substation_name",
        "voltage_kv", "voltage_class",
        "n_plants", "n_wind", "n_solar",
        "total_capacity_mw", "total_energy_mwh_annual",
        "avg_distance_m",
        "geometry",
    ] if c in substations_out.columns]

    substations_out = substations_out[sub_cols].copy()

    substations_out.drop(columns="geometry").to_csv(
        "outputs/substations.csv", index=False
    )
    substations_out.to_file(
        "outputs/substations_energy_summary.geojson", driver="GeoJSON"
    )

    # Create Map

    create_map(plants_out, substations_out)
   
   # --- summary printout ---
   
    n_wind  = (plants_out["technology"] == "Wind").sum()
    n_solar = (plants_out["technology"] == "Solare Strahlungsenergie").sum()
    total_cap   = plants_out["capacity_mw"].sum()
    total_energy = plants_out["energy_mwh_annual"].sum()

    print("=" * 55)
    print("Brandenburg Renewable Energy ETL — complete")
    print("=" * 55)
    print(f"  Wind plants  : {n_wind:>6,}")
    print(f"  Solar plants : {n_solar:>6,}")
    print(f"  Total capacity   : {total_cap:>10,.1f} MW")
    print(f"  Total energy/yr  : {total_energy:>10,.0f} MWh")
    print(f"  Substations      : {substations_out['substation_id'].notna().sum():>6,}")
    print("-" * 55)
    print("Saved:")
    print("  outputs/plants.csv")
    print("  outputs/substations.csv")
    print("  outputs/plants_with_substations.geojson")
    print("  outputs/substations_energy_summary.geojson")
    print("  outputs/map.html")


if __name__ == "__main__":
    main()