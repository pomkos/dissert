import streamlit as st
import pandas as pd
import numpy as np
from piecewise import piecewise
from piecewise import piecewise_plot
import helper_functions.helpers as h

st.title("Graph Trimmer - a test")

original = st.empty()
new = st.empty()

class breakBreaker:
    def __init__(self, dataframe):
        '''
        Trims linear data in the time domain using piecewise regression and user feedback.
        Use case: bike cadence is recorded, but with breaks or warmups/cooldowns. We are only interested in getting the sample entropy of the main session.
        '''        
        cad_range = (dataframe['cadence'] > 150) | (dataframe['cadence'] < -150)
        if np.sum(cad_range) > 0:
            dataframe = dataframe[~cad_range]
            st.info("Dataframe was preprocessed as cadence was outside the rpm range (-150, +150)")
        
        time = dataframe['seconds']
        value = dataframe['cadence']
        
        model = piecewise(time,value)
        
        with original.beta_container():
            st.write('## SMB016 Day 2 - Original Data')
            st.pyplot(piecewise_plot(time,value, model=model)[0]) # 0 is fig, 1 is ax
            where = st.text_input("Which side would you like to cut? (left, right)")
        if not where:
            st.stop()
        self.where = where
        self.dataframe = dataframe
        
        # where results will be stored, to stop recursion
        # source: https://stackoverflow.com/questions/29863851/python-stop-recursion-once-solution-is-found
        self.results = False
        
    def piecewise_finder(self):
        '''
        Finds the piecewise line of best fit, then cuts the dataset after user indicates which line is of interest.
        
        input:
        -----
        dataframe: pd.DataFrame
            Dataframe of interest. Must have `seconds` and `cadence` columns, where `seconds` is sequential integers from row to row.
        where: str
            Either "start" or "end", indicating which side of the dataset should be cut
            
        output:
        -----
        self.results: list
            List where index 0 is the new dataframe, and index 1 is the piecewise linear regression model
        '''
        dataframe = self.dataframe
        where = self.where
        # reset so that dataframe.index can get the correct index position (because iloc is used later)
        dataframe = dataframe.reset_index(drop=True)
        time = dataframe['seconds']
        value = dataframe['cadence']

        model = piecewise(time,value)
        
        with new.beta_container():
            st.pyplot(piecewise_plot(time,value, model=model)[0], key = np.random.randint(0,10000))
            # required for now, needs to be automated
            num = st.text_input(f"Which of the {len(model.segments)} lines is of interest? (integer, stop, or all)", 
                                key = np.random.randint(0,10000))
        if not num:
            st.stop()
        if num == 'all':
            num = input(f"Enter all lines that are of interest ('1,2,3,...' or all)")
            if num != 'all':
                num = num.split(',')
                num = [int(x) for x in num]
        
        while True:
            if self.results:
                # if self.results contains something, return it
                return self.results
            if type(num) == list:
                ################################################
                # LOGIC: for each integer, select that model segment and pass it to self.multiple_dfs
                ################################################
                ''
            else:
                if num == 'stop':
                    # if user says to stop, let user know whether numbers are still sequential
                    # then store dataframe and the piecewise regression model self.results and return it
                    self.results = [dataframe, model]
                    self.sanity_check(dataframe['seconds'])
                    return self.results
                elif num == 'all':
                    # if all, then we need to return multiple datasets based on the segments
                    return self.multiple_dfs(model, dataframe)
                segment = model.segments[int(num)-1]

                if where == 'left':
                    start_t_sec = segment.start_t
                    start_t = dataframe[dataframe['seconds']==start_t_sec].index[0]
                    print(f"Cutting at iloc[{start_t}:-1]")
                    end_t = -1
                elif where == 'right':
                    end_t_sec = segment.end_t
                    end_t = dataframe[dataframe['seconds']==end_t_sec].index[0]
                    print(f"Cutting at iloc[0:{end_t}]")
                    start_t = 0
                else:
                    print(f"{where} is an unknown input!")
            
            self.dataframe = dataframe.iloc[int(round(start_t)):int(round(end_t)),:]
            self.results = self.piecewise_finder()
            
    def multiple_dfs(self, model, dataframe):
        '''
        Returns a list of dataframes, each of which fits a piecewise regression segment
        '''
        # Extract dataset limits
        dataframe = dataframe.reset_index(drop=True)
        all_segments = []
        for seg in model.segments:
            all_segments.append(seg)
        start_t = []
        end_t = []
        for segment in all_segments:
            start_t.append(segment.start_t)
            end_t.append(segment.end_t)
            
        # Find the index positions of those limits
        iloc_dict = {}
        for i in range(len(start_t)):
            start_second = start_t[i]
            end_second = end_t[i]
            
            start_loc = dataframe[dataframe['seconds'] == start_second].index[0]
            end_loc = dataframe[dataframe['seconds'] == end_second].index[0]
            iloc_dict[i] = (start_loc, end_loc) # tuple so it wont be changed accidentally
            
        # Extract dataframes using the obtained index positions, store in dictionary
        df_dict = {}
        for k, v in iloc_dict.items():
            new_df = dataframe.loc[v[0]:v[1],:]
            df_dict[k] = new_df
            
        return df_dict
            
        
    def sanity_check(self,my_series):
        '''
        Uses the mylist function from the helper_functions.checkers module to check that all numbers are sequential in the series.
        '''
        import helper_functions.checkers as c
        result = c.mylist(my_series)
        
        if result:
            print("The column is still sequential!")
        else:
            print("Something bad happened, the column is no longer sequential")

@st.cache
def load_db():
    db = h.dbConnect("sqlite:///nih.db")
    df = db.load_table("bike_data")

    cols = ['date', 'time', 'hr', 'cadence', 'power', 'id', 'session']

    short_df = df[['date','time','hr','cadence','power','my_id','day']]
    short_df.columns = cols
    clean = h.CleanOldDf(short_df)
    new_df = clean.datetime_maker(count_row=True).reset_index(drop = True)
    new_df = new_df.astype({"id":str,"session":str})
    new_df['id_sess'] = new_df['id'] + '_' + new_df['session']
    # new_df[new_df['id_sess'] == 'SMB033_day3'].to_csv("smb033_day3.csv")
    smb16d2 = new_df[new_df['id_sess'] == 'SMB016_day2']
    
    return smb16d2

smb16d2 = load_db()
bb = breakBreaker(smb16d2)
data = bb.piecewise_finder()
