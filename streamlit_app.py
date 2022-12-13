import pandas as pd
import netCDF4

import xarray as xr
import requests
import json
import numpy as np
import pandas as pd
import io
import matplotlib.pyplot as plt
#import seaborn as sns
import geopy
from geopy.geocoders import Nominatim
import streamlit as st
import altair
import subprocess



#pagelayout
st.set_page_config(layout="wide")

#title
st.title("Streamlit Climate App")
st.write("Powered by the [Pharos API](https://pharossoftware.com/).")

# Create instance of Nominatim
geolocator = Nominatim(user_agent="pharost_test1")

# Use Streamlit to ask the user to input city name
with st.sidebar:
  city_name = st.text_input(
    "City Name:",
    "Toronto",
    key="placeholder",
  )

# Check if the user entered a city name
if city_name:
  # Use geopy to get the latitude and longitude of the city
  location = geolocator.geocode(city_name)

  # Check if location was found
  if location:
    # Print out the coordinates
    with st.sidebar:
      st.write("Coordinates (lat,lon): ", location.latitude,
               location.longitude)
  else:
    # Print a message indicating that the city was not found
    st.write("Sorry, the city was not found.")

#api headers
YOUR_API_KEY = "6040d78298fe401d959c1884d5e3d7bd"  # Replace the API_KEY_STRING with your API Key in quotes!!
api_header = {'X-API-Key': YOUR_API_KEY}

#pharos request
datareq = {  # construct your query
  "variable":
  ["temperature/era5", "total_precipitation/era5", "solar_radiation/era5"],
  "space": [[location.latitude, location.longitude]],
  "time": {
    "start": "2010-01-01",
    "end": "2020-12-31",
    "unit": "day"
  },
  "format":
  "netcdf"
}
# make the request
response = requests.post('https://api.pharosdata.io/query',
                         json=datareq,
                         headers=api_header)
# open the output in pandas or any other library of choice
data = xr.open_dataset(response.content).to_dataframe()

#reset index and set to time
df = data.reset_index()
df = df.set_index('time')

#change units
new_values = {
  'temperature/era5': df['temperature/era5'] - 273.15,
  'total_precipitation/era5': df['total_precipitation/era5'] * 1000,
  'solar_radiation/era5': df['solar_radiation/era5'] / 3600
}
df.update(new_values)

#calculate rolling temp
df = df.assign(temp_rolling=df['temperature/era5'].rolling(30).mean())
df = df.assign(sunshine_rolling=df['solar_radiation/era5'].rolling(30).mean())

# store the original index in a new variable
original_index = df.index

# convert the timestamps to floating point numbers
timestamps = original_index.values.astype(float)

# add polynomial fit
coefficients = np.polyfit(timestamps, df['temperature/era5'], 1)

# calculate the trendline values
trendline = coefficients[0] * timestamps + coefficients[1]

# add the trendline values as a new column in the dataframe
df = df.set_index(original_index).assign(trendline=trendline)

#calculate change

first_trendline_value = trendline[0]
last_trendline_value = trendline[-1]

# calculate the total change
total_change = last_trendline_value - first_trendline_value

# calculate the total change
total_change = last_trendline_value - first_trendline_value

#calculate volatility
volatility = df.groupby(df.index.year).std()

st.header("Summary Stats")
st.table(
  df[['temperature/era5', 'total_precipitation/era5',
      'solar_radiation/era5']].describe())

#daily time-series
st.header("Temperature")

#col1, col2 = st.columns(2)

st.subheader("Temperature (°C) - Daily Time-Series")
st.line_chart(df[['temperature/era5', 'temp_rolling', 'trendline']])

# day of year temp
st.subheader('Temperature (°C) Across Year')
climate = df.copy()
climate['day'] = climate.index.dayofyear
c = altair.Chart(climate).mark_circle().encode(x=altair.X(
  'day', scale=altair.Scale(domain=[0, 365])),
                                               y='temperature/era5')
st.altair_chart(c, use_container_width=True)

# frost
st.subheader('Frost Days (< 0°C)')
frost = climate[climate['temperature/era5'] < 0]
frost['year'] = frost.index.year
c = altair.Chart(frost).mark_circle().encode(
  x=altair.X('year', scale=altair.Scale(domain=[2010, 2020])),
  y=altair.Y('day', scale=altair.Scale(domain=[0, 365])))
# NOTE: change the domain argument above if you're quering a different time range
st.altair_chart(c, use_container_width=True)

#gdd
st.subheader('Growing Degree Days (GDD) Above 10°C')
gdd_10 = df['temperature/era5'].clip(lower=10,
                                     upper=None).groupby(df.index.year).sum()
st.bar_chart(gdd_10)

st.header("Precipitation")

st.subheader("Precipitation (mm) - Daily Time-Series")
st.bar_chart(df['total_precipitation/era5'])

# annual max precip
st.subheader('Annual Maximum 1-Day Precipitation (mm) ')
max_precip = df['total_precipitation/era5'].groupby(df.index.year).max()
st.bar_chart(max_precip)

# monthly precip
st.subheader('Monthly Precipitation (mm)')
st.bar_chart(df['total_precipitation/era5'].groupby(df.index.month).mean())

# drought runs
bin_pr = df['total_precipitation/era5'] < 0.2
bin_pr = bin_pr.groupby(bin_pr.index.year).sum()
st.subheader('Days without Precipitation (mm  < 0.2mm) ')
st.bar_chart(bin_pr)

st.header("Sunshine")

st.subheader("Solar Radiation (W/m$^{2}$) - Daily Time-Series")
st.line_chart(df[['solar_radiation/era5', 'sunshine_rolling']])

# sunshine
st.subheader('Solar Radiation (W/m$^{2}$) Across Year')
c = altair.Chart(climate).mark_circle().encode(x=altair.X(
  'day', scale=altair.Scale(domain=[0, 365])),
                                               y='solar_radiation/era5')
st.altair_chart(c, use_container_width=True)

with st.sidebar:
  st.map(df)


#download data
@st.experimental_memo
def convert_df(df):
  return df.to_csv(index=False).encode('utf-8')


csv = convert_df(df)

st.download_button("Download Data as CSV",
                   csv,
                   "pharos_data.csv",
                   "text/csv",
                   key='download-csv')
