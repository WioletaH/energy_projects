import json
import math

GEOGRAPHIC_CRS = "EPSG:4326"


def create_map(plants_gdf, substations_gdf, output_file="outputs/map.html"):
    """
    Create interactive Leaflet map with plants and substations.
    """

    plants_4326 = plants_gdf.to_crs(GEOGRAPHIC_CRS).copy()
    subs_4326 = substations_gdf.to_crs(GEOGRAPHIC_CRS).copy()

    def _clean(v):
        s = str(v) if v is not None else ""
        return "" if s.lower() in ("nan", "none", "") else s

    def clean_plants_geojson(gdf):
        data = json.loads(gdf.to_json())

        for f in data["features"]:
            p = f["properties"]
            p["plant_name"] = (
                _clean(p.get("plant_name"))
                or _clean(p.get("plant_id"))
                or "Unknown"
            )
            p["substation_name"] = _clean(p.get("substation_name")) or "–"

        return json.dumps(data)

    def clean_subs_geojson(gdf):
        data = json.loads(gdf.to_json())

        for f in data["features"]:
            p = f["properties"]
            p["substation_name"] = (
                _clean(p.get("substation_name"))
                or "Unnamed substation"
            )

            cap = p.get("total_capacity_mw") or 0

            if cap > 0:
                p["radius"] = round(
                    3 + 4 * math.log1p(cap) / math.log1p(350),
                    2
                )
            else:
                p["radius"] = 3

        return json.dumps(data)

    plants_json = clean_plants_geojson(plants_4326)
    subs_json = clean_subs_geojson(subs_4326)

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
var subsData = {subs_json};

var map = L.map('map', {{center:[52.4,13.6],zoom:8}});

L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{
  attribution:'&copy; OpenStreetMap &copy; CARTO',
  maxZoom:19
}}).addTo(map);

var subsLayer = L.geoJSON(subsData,{{
  pointToLayer: function(f,ll){{
    var p = f.properties;
    var has = p.total_capacity_mw > 0;

    return L.circleMarker(ll,{{
      radius: has ? p.radius : 3,
      color: has ? '#c0392b' : '#aaa',
      weight: 1,
      fillColor: has ? '#e74c3c' : '#ccc',
      fillOpacity: has ? 0.75 : 0.4
    }});
  }},
  onEachFeature: function(f,layer){{
    var p = f.properties;

    layer.bindPopup(
      '<b>' + p.substation_name + '</b><br>' +
      'Plants: ' + (p.n_plants || '–') + '<br>' +
      'Capacity: ' + (p.total_capacity_mw ? (+p.total_capacity_mw).toFixed(1) + ' MW' : '–') + '<br>' +
      'Energy: ' + (p.total_energy_mwh_annual ? (+p.total_energy_mwh_annual).toLocaleString() + ' MWh/yr' : '–') + '<br>' +
      'Avg dist: ' + (p.avg_distance_m ? (p.avg_distance_m / 1000).toFixed(1) + ' km' : '–'),
      {{maxWidth:240}}
    );
  }}
}}).addTo(map);

var windLayer = L.geoJSON(plantsData,{{
  filter: f => f.properties.technology === 'Wind',
  pointToLayer: (_,ll) => L.circleMarker(ll,{{
    radius:4,
    color:'#2980b9',
    weight:0.5,
    fillColor:'#2980b9',
    fillOpacity:0.7
  }}),
  onEachFeature: function(f,layer){{
    var p = f.properties;

    layer.bindPopup(
      '<b>' + p.plant_name + '</b><br>Wind<br>' +
      'Capacity: ' + (+p.capacity_mw).toFixed(3) + ' MW<br>' +
      'Energy: ' + (+p.energy_mwh_annual || +p.energy_mwh || 0).toFixed(0) + ' MWh/yr<br>' +
      'Substation: ' + p.substation_name,
      {{maxWidth:240}}
    );
  }}
}}).addTo(map);

var solarLayer = L.geoJSON(plantsData,{{
  filter: f => f.properties.technology === 'Solare Strahlungsenergie',
  pointToLayer: (_,ll) => L.circleMarker(ll,{{
    radius:4,
    color:'#f39c12',
    weight:0.5,
    fillColor:'#f39c12',
    fillOpacity:0.7
  }}),
  onEachFeature: function(f,layer){{
    var p = f.properties;

    layer.bindPopup(
      '<b>' + p.plant_name + '</b><br>Solar<br>' +
      'Capacity: ' + (+p.capacity_mw).toFixed(3) + ' MW<br>' +
      'Energy: ' + (+p.energy_mwh_annual || +p.energy_mwh || 0).toFixed(0) + ' MWh/yr<br>' +
      'Substation: ' + p.substation_name,
      {{maxWidth:240}}
    );
  }}
}}).addTo(map);

L.control.layers(null,{{
  '<span style="color:#e74c3c">&#9679;</span> Substations': subsLayer,
  '<span style="color:#2980b9">&#9679;</span> Wind plants': windLayer,
  '<span style="color:#f39c12">&#9679;</span> Solar plants': solarLayer
}},{{collapsed:false}}).addTo(map);

var legend = L.control({{position:'bottomleft'}});

legend.onAdd = function(){{
  var d = L.DomUtil.create('div','legend');

  d.innerHTML =
    '<h4>Brandenburg Energy</h4>' +
    '<span class="dot" style="background:#e74c3c"></span>Substation (size=capacity)<br>' +
    '<span class="dot" style="background:#ccc;border:1px solid #aaa"></span>Substation (no data)<br>' +
    '<span class="dot" style="background:#2980b9"></span>Wind plant<br>' +
    '<span class="dot" style="background:#f39c12"></span>Solar plant';

  return d;
}};

legend.addTo(map);

var stats = L.control({{position:'topright'}});

stats.onAdd = function(){{
  var nW = plantsData.features.filter(f => f.properties.technology === 'Wind').length;
  var nS = plantsData.features.filter(f => f.properties.technology === 'Solare Strahlungsenergie').length;

  var cap = plantsData.features.reduce((s,f) => s + (+f.properties.capacity_mw || 0), 0);
  var ener = plantsData.features.reduce((s,f) => s + (+f.properties.energy_mwh_annual || +f.properties.energy_mwh || 0), 0);
  var nSubs = subsData.features.filter(f => f.properties.total_capacity_mw > 0).length;

  var d = L.DomUtil.create('div','info-panel');

  d.innerHTML =
    '<h4>Brandenburg Summary</h4>' +
    'Wind plants: <b>' + nW.toLocaleString() + '</b><br>' +
    'Solar plants: <b>' + nS.toLocaleString() + '</b><br>' +
    'Total capacity: <b>' + cap.toFixed(0) + ' MW</b><br>' +
    'Est. energy: <b>' + (ener / 1e6).toFixed(2) + ' TWh/yr</b><br>' +
    'Active substations: <b>' + nSubs + '</b>';

  return d;
}};

stats.addTo(map);
</script>
</body>
</html>"""

    with open(output_file, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"Saved map: {output_file}")