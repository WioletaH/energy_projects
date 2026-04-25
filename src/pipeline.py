import os
import pandas as pd
import geopandas as gpd
import folium
from osm import load_substations
from utils import clean_numeric

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HOURS_PER_YEAR = 8_760

# Capacity factors encode the core "weather/performance" assumption:
#   Wind  – ~30 % (typical onshore Brandenburg, P50 long-term yield)
#   Solar – ~12 % (typical northeast Germany horizontal irradiance)
CAPACITY_FACTORS = {
    "Wind":                    0.30,
    "Solare Strahlungsenergie": 0.12,
}

PROJECTED_CRS  = "EPSG:3035"
GEOGRAPHIC_CRS = "EPSG:4326"

PLANTS_FILE = "data/Stromerzeuger.csv"


# ---------------------------------------------------------------------------
# Plant loading
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

def create_map(plants_gdf: gpd.GeoDataFrame, substations_gdf: gpd.GeoDataFrame):
    """
    Build the map using Leaflet GeoJSON layers instead of per-marker Folium calls.
    The per-marker approach generates one JS block per plant (~4 500 plants),
    producing a >2 MB file that gets truncated mid-script and fails to render.
    Embedding two GeoJSON objects keeps the output complete and loads instantly.
    """
    import json, math, re

    plants_4326 = plants_gdf.to_crs(GEOGRAPHIC_CRS).copy()
    subs_4326   = substations_gdf.to_crs(GEOGRAPHIC_CRS).copy()

    # Clean NaN names and pre-compute substation circle radius
    def _clean(v):
        s = str(v) if v is not None else ""
        return "" if s.lower() in ("nan", "none", "") else s

    for feat in json.loads(plants_4326.to_json())["features"]:
        pass  # will re-serialise below after cleaning

    # Build clean dicts
    def clean_plants_geojson(gdf):
        data = json.loads(gdf.to_json())
        for f in data["features"]:
            p = f["properties"]
            p["plant_name"] = _clean(p.get("plant_name")) or _clean(p.get("plant_id")) or "Unknown"
            p["substation_name"] = _clean(p.get("substation_name")) or "–"
        return json.dumps(data)

    def clean_subs_geojson(gdf):
        data = json.loads(gdf.to_json())
        for f in data["features"]:
            p = f["properties"]
            p["substation_name"] = _clean(p.get("substation_name")) or "Unnamed substation"
            cap = p.get("total_capacity_mw") or 0
            p["radius"] = round(3 + 4 * math.log1p(cap) / math.log1p(350), 2) if cap > 0 else 3
        return json.dumps(data)

    plants_json = clean_plants_geojson(plants_4326)
    subs_json   = clean_subs_geojson(subs_4326)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Brandenburg Renewable Energy Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ margin:0;padding:0;box-sizing:border-box; }}
  html,body {{ height:100%;width:100%; }}
  #map {{ height:100%;width:100%; }}
  .legend,.info-panel {{
    background:white;padding:10px 14px;border-radius:6px;
    box-shadow:0 1px 5px rgba(0,0,0,.3);font:13px/1.8 Arial,sans-serif;
  }}
  .legend h4,.info-panel h4 {{ margin-bottom:4px;font-size:14px; }}
  .dot {{ display:inline-block;width:11px;height:11px;border-radius:50%;
          margin-right:5px;vertical-align:middle; }}
</style>
</head>
<body><div id="map"></div>
<script>
var plantsData = {plants_json};
var subsData   = {subs_json};

var map = L.map('map', {{center:[52.4,13.6],zoom:8}});
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{
  attribution:'&copy; OpenStreetMap &copy; CARTO',maxZoom:19
}}).addTo(map);

// Substations
var subsLayer = L.geoJSON(subsData,{{
  pointToLayer: function(f,ll){{
    var p=f.properties, has=p.total_capacity_mw>0;
    return L.circleMarker(ll,{{
      radius:has?p.radius:3, color:has?'#c0392b':'#aaa', weight:1,
      fillColor:has?'#e74c3c':'#ccc', fillOpacity:has?0.75:0.4
    }});
  }},
  onEachFeature: function(f,layer){{
    var p=f.properties;
    layer.bindPopup('<b>'+p.substation_name+'</b><br>'+
      'Plants: '+(p.n_plants||'–')+'<br>'+
      'Capacity: '+(p.total_capacity_mw?(+p.total_capacity_mw).toFixed(1)+' MW':'–')+'<br>'+
      'Energy: '+(p.total_energy_mwh_annual?(+p.total_energy_mwh_annual).toLocaleString()+' MWh/yr':'–')+'<br>'+
      'Avg dist: '+(p.avg_distance_m?(p.avg_distance_m/1000).toFixed(1)+' km':'–'),
      {{maxWidth:240}});
  }}
}}).addTo(map);

// Wind plants
var windLayer = L.geoJSON(plantsData,{{
  filter: f=>f.properties.technology==='Wind',
  pointToLayer:(_,ll)=>L.circleMarker(ll,{{radius:4,color:'#2980b9',weight:0.5,fillColor:'#2980b9',fillOpacity:0.7}}),
  onEachFeature: function(f,layer){{
    var p=f.properties;
    layer.bindPopup('<b>'+p.plant_name+'</b><br>Wind<br>'+
      'Capacity: '+(+p.capacity_mw).toFixed(3)+' MW<br>'+
      'Energy: '+(+p.energy_mwh_annual||+p.energy_mwh||0).toFixed(0)+' MWh/yr<br>'+
      'Substation: '+p.substation_name,{{maxWidth:240}});
  }}
}}).addTo(map);

// Solar plants
var solarLayer = L.geoJSON(plantsData,{{
  filter: f=>f.properties.technology==='Solare Strahlungsenergie',
  pointToLayer:(_,ll)=>L.circleMarker(ll,{{radius:4,color:'#f39c12',weight:0.5,fillColor:'#f39c12',fillOpacity:0.7}}),
  onEachFeature: function(f,layer){{
    var p=f.properties;
    layer.bindPopup('<b>'+p.plant_name+'</b><br>Solar<br>'+
      'Capacity: '+(+p.capacity_mw).toFixed(3)+' MW<br>'+
      'Energy: '+(+p.energy_mwh_annual||+p.energy_mwh||0).toFixed(0)+' MWh/yr<br>'+
      'Substation: '+p.substation_name,{{maxWidth:240}});
  }}
}}).addTo(map);

L.control.layers(null,{{
  '<span style="color:#e74c3c">&#9679;</span> Substations':subsLayer,
  '<span style="color:#2980b9">&#9679;</span> Wind plants':windLayer,
  '<span style="color:#f39c12">&#9679;</span> Solar plants':solarLayer
}},{{collapsed:false}}).addTo(map);

// Legend
var legend=L.control({{position:'bottomleft'}});
legend.onAdd=function(){{
  var d=L.DomUtil.create('div','legend');
  d.innerHTML='<h4>Brandenburg Energy</h4>'+
    '<span class="dot" style="background:#e74c3c"></span>Substation (size=capacity)<br>'+
    '<span class="dot" style="background:#ccc;border:1px solid #aaa"></span>Substation (no data)<br>'+
    '<span class="dot" style="background:#2980b9"></span>Wind plant<br>'+
    '<span class="dot" style="background:#f39c12"></span>Solar plant';
  return d;
}};
legend.addTo(map);

// Stats panel
var stats=L.control({{position:'topright'}});
stats.onAdd=function(){{
  var nW=plantsData.features.filter(f=>f.properties.technology==='Wind').length;
  var nS=plantsData.features.filter(f=>f.properties.technology==='Solare Strahlungsenergie').length;
  var cap=plantsData.features.reduce((s,f)=>s+(+f.properties.capacity_mw||0),0);
  var ener=plantsData.features.reduce((s,f)=>s+(+f.properties.energy_mwh_annual||+f.properties.energy_mwh||0),0);
  var nSubs=subsData.features.filter(f=>f.properties.total_capacity_mw>0).length;
  var d=L.DomUtil.create('div','info-panel');
  d.innerHTML='<h4>Brandenburg Summary</h4>'+
    'Wind plants: <b>'+nW.toLocaleString()+'</b><br>'+
    'Solar plants: <b>'+nS.toLocaleString()+'</b><br>'+
    'Total capacity: <b>'+cap.toFixed(0)+' MW</b><br>'+
    'Est. energy: <b>'+(ener/1e6).toFixed(2)+' TWh/yr</b><br>'+
    'Active substations: <b>'+nSubs+'</b>';
  return d;
}};
stats.addTo(map);
</script></body></html>"""

    with open("outputs/map.html", "w", encoding="utf-8") as fh:
        fh.write(html)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # OUTPUT 1 — Plant-level dataset
    # -----------------------------------------------------------------------
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

    # -----------------------------------------------------------------------
    # OUTPUT 2 — Substation-level dataset
    # -----------------------------------------------------------------------
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

    # -----------------------------------------------------------------------
    # OUTPUT 3 — Map
    # -----------------------------------------------------------------------
    create_map(plants_out, substations_out)

    # -----------------------------------------------------------------------
    # Summary print
    # -----------------------------------------------------------------------
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