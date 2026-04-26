# Renewable Energy ETL Pipeline (Brandenburg)

This project builds a geospatial ETL pipeline to estimate renewable energy production (wind & solar) and assign it to electrical substations in Brandenburg, Germany.

---
For the purpose of that project, possible highest relability the search of the data took quite some time, which was caused by my lack of experience in that domain. The data used for this project was downloaded from https://www.marktstammdatenregister.de/MaStR/Einheit/Einheiten/OeffentlicheEinheitenuebersicht 
Initially I was also trying also to use the data of substations with their locations however it wasn't really clear for me which are the correct one, so in the end I went for OSM substation dataset. Downloaded the for plants was prefiltered on the mentioned source so I could safe some space capacity and time. The main criteria considered in that stage were: Status: In Betried, and Technology: Solar and Wind 
In the task description it wasnt specified if I should consider high voltages, so the low volatages are marked as grey to have an general overview 


##  What this project does

The pipeline:

1. Loads renewable energy plant data (CSV)
2. Cleans and processes capacity + coordinates
3. Estimates annual energy production (MWh)
4. Downloads substations from OpenStreetMap (OSM)
5. Assigns each plant to the nearest substation
6. Aggregates energy and capacity per substation
7. Exports results (CSV + GeoJSON)
8. Creates an interactive map (Leaflet)

---

## 🗂 Project Structure

run project python3 src/main.py

energyproj/
├── src/
│   ├── main.py          # main ETL pipeline
│   ├── map.py           # map generation (Leaflet)
│   ├── osm.py           # OSM substation loader 
│   └── utils.py         # helper functions
│
├── data/
│   ├── Stromerzeuger.csv
│   ├── StromerzeugerErweitert.csv 
│   ├── StromverbrauchErweitert.csv
│
├── outputs/
│   ├── map.html
│   ├── plants.csv
│   ├── substations.csv
│   ├── plants_with_substations.geojson
│   └── substations_energy_summary.geojson
│
├── venv/                # virtual environment (ignored in git)
├── requirements.txt
├── .gitignore

