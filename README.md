# Renewable Energy ETL Pipeline (Brandenburg)

This project builds a geospatial ETL pipeline to estimate renewable energy production (wind & solar) and assign it to electrical substations in Brandenburg, Germany.

---

## Project Background

The goal of this project is to combine renewable energy plant data with electrical grid infrastructure to better understand how energy production is spatially distributed across substations.

The data collection phase required careful selection and validation due to the complexity of available datasets.

- Power plant data was obtained from the German Market Master Data Register (MaStR):  
  https://www.marktstammdatenregister.de  
  (*Stromerzeugungseinheiten dataset*)

- The dataset was prefiltered at the source to include:
  - Status: *In Betrieb* (in operation)
  - Technologies: *Wind* and *Solar*

- Substation data from official sources was unclear and difficult to interpret, so OpenStreetMap (OSM) was used as a reliable alternative.

- Since voltage filtering was not explicitly required, substations with missing or low-voltage information are displayed in grey to provide a complete overview.

---

## What this project does

The pipeline:

1. Loads renewable energy plant data (CSV)
2. Cleans and processes capacity and coordinates
3. Estimates annual energy production (MWh)
4. Downloads substations from OpenStreetMap (OSM)
5. Assigns each plant to the nearest substation
6. Aggregates energy and capacity per substation
7. Exports results (CSV + GeoJSON)
8. Creates an interactive map (Leaflet)

---

## Map overview

<p align="center">
  <img src="docs/map_screenshot.png" width="800"/>
</p>

<p align="center">
  <img src="docs/map_screenshot2.png" width="800"/>
</p>


---

##  How to run the project

### Run the pipeline

```bash
python3 src/main.py

Map --- 
python -m http.server 5000
http://localhost:5000/outputs/map.html



## Project extensions

This project could be extended in several directions:

1. **Add more energy technologies**  
   Include biomass, hydro, battery storage, combined heat and power (CHP), or other renewable and flexible energy assets.

2. **Improve energy estimation**  
   The current estimation is based on fixed capacity factors. A more advanced version could include weather data, wind speed, solar irradiance, seasonal capacity factors, or real production measurements.

3. **Improve plant-to-substation assignment**  
   In the current project, plants are assigned to the nearest substation. This could be improved by using real grid topology, voltage compatibility, distance thresholds, or official grid connection datasets.

4. **Add other regions for comparison**  
   The pipeline could be extended to Berlin, other German federal states, or Germany as a whole.

5. **Improve deployment and data infrastructure**  
   Possible improvements include Docker deployment, connecting the pipeline to a PostGIS database, and improving the interactive map output.

6. **Improve reproducibility and maintainability**  
   Add logging, tests, configuration files, and clearer pipeline documentation.

7. **Add a weather API for short-term energy prediction**  
   A strong extension would be to connect the pipeline with a weather forecast API and estimate short-term renewable energy production.

   Instead of using only fixed annual capacity factors, the model could use hourly weather forecasts to predict energy generation for the next hours or days.

   Possible weather inputs:

   - solar radiation / irradiance
   - cloud cover
   - temperature
   - wind speed
   - wind direction

   Possible APIs:

   - Open-Meteo API
   - Deutscher Wetterdienst (DWD) Open Data

8. **Deep Learning models for energy analysis**
    With historical data of wind speed, solar irradiance, temperature, cloud cover etc
    - LSTM / GRU for time-series forecasting
    - CNN-LSTM for spatial-temporal energy prediction
    - Transformer models for longer time-series forecasting