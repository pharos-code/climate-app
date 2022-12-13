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


#title
st.title("Pharos Climate App")


    
# Create instance of Nominatim
geolocator = Nominatim(user_agent="pharost_test1")

# Use Streamlit to ask the user to input city name
with st.sidebar:
    city_name = st.text_input("Please enter a city name: ")

# Check if the user entered a city name
if city_name:
    # Use geopy to get the latitude and longitude of the city
    location = geolocator.geocode(city_name)

    # Check if location was found
    if location:
        # Print out the coordinates
        st.write("The coordinates of the city are: ", location.latitude, location.longitude)
    else:
        # Print a message indicating that the city was not found
        st.write("Sorry, the city was not found.")



#api headers
YOUR_API_KEY = "6040d78298fe401d959c1884d5e3d7bd" # Replace the API_KEY_STRING with your API Key in quotes!!
api_header = {'X-API-Key': YOUR_API_KEY}


#pharos request
datareq = { # construct your query
    "variable": [
        "temperature/era5",
        "total_precipitation/era5",
        "solar_radiation/era5"


        
    ],
    "space": [[location.latitude, location.longitude]]
    
    ,
    "time": {
        "start":"2010-01-01",
        "end":"2020-12-31",
        "unit": "day"

    },
    "format": "netcdf"
}
# make the request
response = requests.post('https://api.pharosdata.io/query', 
                     json=datareq,
                     headers=api_header)
# open the output in pandas or any other library of choice
data = xr.open_dataset(response.content).to_dataframe()

# GDD DONE
# density plot binned by 5 year intervals
# precipitation boxplot monthly over historical
# annual scatterplot of temperature DONE
# annual max precip trend DONE
# humidity vs. precip FAIL
# precip vs temp (with ToY) 
# drought runs (longest run below some rain?) DONE
# frost-stuff season length DONE
# heatwave stuff (trend) DATA NO GOOD



#reset index and set to time
df = data.reset_index()
df = df.set_index('time')


#change units
new_values = {'temperature/era5': df['temperature/era5'] - 273.15,
              'total_precipitation/era5': df['total_precipitation/era5'] * 1000,
              'solar_radiation/era5': df['solar_radiation/era5'] - 273.15}
df.update(new_values)

st.subheader('GDD Above 10C')
gdd_10 = df['temperature/era5'].clip(lower=10, upper=None).groupby(df.index.year).sum()
st.bar_chart(gdd_10)

#add rolling temp
df = df.assign(temp_rolling=df['temperature/era5'].rolling(30).mean())
df = df.assign(sunshine_rolling=df['solar_radiation/era5'].rolling(30).mean())

# day of year temp
st.subheader('Temperature across Year')
climate = df.copy()
climate['day'] = climate.index.dayofyear
c = altair.Chart(climate).mark_circle().encode(
    x=altair.X('day', scale=altair.Scale(domain=[0,365])), y='temperature/era5')
st.altair_chart(c, use_container_width=True)

# annual max precip
st.subheader('Annual Maximum 1-Day Precipitation')
max_precip = df['total_precipitation/era5'].groupby(df.index.year).max()
st.bar_chart(max_precip)

# humidity vs precip
# st.subheader('Humidity vs Precip.')
# precip_adjust = df.copy()
# precip_adjust[precip_adjust['total_precipitation/era5'] >= 0.1]
# c = altair.Chart(precip_adjust).mark_circle().encode(
#     x=altair.X('dew_point_temperature/era5'), 
#     y=altair.Y('total_precipitation/era5' ))
# st.altair_chart(c, use_container_width=True)

# monthly precip
st.subheader('Monthly Precipitation')
st.bar_chart(df['total_precipitation/era5'].groupby(df.index.month).mean())

# drought runs
bin_pr = df['total_precipitation/era5'] < 0.2
bin_pr = bin_pr.groupby(bin_pr.index.year).sum()
st.subheader('Days without Precipitation')
st.bar_chart(bin_pr)

# frost
st.subheader('Frost Days')
frost = climate[climate['temperature/era5'] < 0]
frost['year'] = frost.index.year
c = altair.Chart(frost).mark_circle().encode(
    x=altair.X('year', scale=altair.Scale(domain=[2010, 2020])), 
    y=altair.Y('day', scale=altair.Scale(domain=[0,365])))
# NOTE: change the domain argument above if you're quering a different time range
st.altair_chart(c, use_container_width=True)

# sunshine
st.subheader('Sunshine across Year')
c = altair.Chart(climate).mark_circle().encode(
    x=altair.X('day', scale=altair.Scale(domain=[0,365])), y='solar_radiation/era5')
st.altair_chart(c, use_container_width=True)

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
st.table(df[['temperature/era5','total_precipitation/era5','solar_radiation/era5']].describe())



st.header("Temperature")

st.subheader("Daily Time-series")
st.line_chart(df[['temperature/era5','temp_rolling','trendline']])
st.write(total_change)

st.header("Volatility")
st.line_chart(volatility[['temperature/era5', 'total_precipitation/era5']])

st.subheader("Daily Time-series")
st.bar_chart(df['total_precipitation/era5'])


st.header("Sunshine")

st.subheader("Daily Time-series")
st.line_chart(df[['solar_radiation/era5','sunshine_rolling']])
   
with st.sidebar:
    st.map(df)



#download data
@st.experimental_memo
def convert_df(df):
   return df.to_csv(index=False).encode('utf-8')


csv = convert_df(df)

st.download_button(
   "Download Data as CSV",
   csv,
   "pharos_data.csv",
   "text/csv",
   key='download-csv'
)