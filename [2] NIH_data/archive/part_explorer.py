# first attempt at using Streamlit to label graphs.
# Streamlit is not good at labeling as it always restarts the script

import streamlit as st
import sqlalchemy as sq
import pandas as pd
import numpy as np
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
import helper_functions.helpers as h

st.title("Check out your participant's characteristics")


db = h.dbConnect("sqlite:///nih.db")
df = db.load_table("bike_data")

participants = list(df['my_id'].unique())
participants.sort()
person = st.sidebar.radio("Select participant",participants)

newest = pd.DataFrame(columns=df.columns)
new_df = df[df['my_id']==person]
for day in new_df['day'].unique():
    temp = new_df[new_df['day']==day].reset_index(drop=True)
    temp = temp.reset_index()
    temp['min'] = temp['index']/60
    newest = newest.append(temp)

fig_cad, ax = plt.subplots()
ax = sns.lineplot(x='min',y='cadence',
                  data=newest,hue='day',
                  hue_order=['day1','day2','day3'])
ax.set_title(person + " Cadence")
ax.set_ylim(-20,100)

st.pyplot(fig_cad)

fig_pow, ax = plt.subplots()
ax = sns.lineplot(x='min',y='power',
                  data=newest,hue='day',
                  hue_order=['day1','day2','day3'])
ax.set_title(person + " Power")

st.pyplot(fig_pow)
