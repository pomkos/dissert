"""
A script created from the code in [0]_NIH_raw_files_process.ipynb.

USE:
    dfb = dfBike(save_table = False)
    df_bike = dfb.result
    
    dfd = dfDemos(df_bike, save_table = False)
    df_demos = dfd.result
    
    dfe = dfEntropy(save_table = False)
    df_entropy = dfe.result

REASON: 
    To review my code, add unit testing, because somewhere along the way a previously well performing R script is not cutting via segmented regression in the same spot for at least one participant anymore.

PURPOSE:
    * Will not include graphing functions
    * Combine the raw bike files into one dataset (stored in `nih.db` as `bike_data`)
    * Label participants as belonging to `dynamic` or `static` groups
    * Load and extract UPDRS information
    * Create effort dataset
    * Load demographic dataset
    * Merge `updrs` and `effort` datasets into the `demos` dataset
    * Load, clean, format, and save the `entropy` data
        * NOTE: `entropy` dataset was filtered to only include participants in the `dynamic` group
"""
import pandas as pd
import numpy as np
import datetime as dt
import dynbike_functions.helpers as h
import dynbike_functions.checkers as c


class dfBike:
    """
    Processes files to create the df_bike dataframe
    """

    def __init__(self, use_this=None, save_table=False):
        """
        Coordinates the self.functions

        use_this:
            If None, will load file from raw_bike_files folder
            If a dataframe, will use that dataframe instead
        """
        if use_this is None:
            df = pd.read_excel("raw_bike_files/[combined_files].xlsx")
        else:
            df = use_this
        df = self.load_and_organize(df)
        df_bike = pd.DataFrame(
            columns=[
                "datetime",
                "date",
                "time",
                "elapsed_sec",
                "id_sess",
                "my_id",
                "day",
                "unknown",
                "hr",
                "power",
                "cadence",
            ]
        )

        # find the number of seconds per id_sess, trim the cadence
        for id_sess in df["id_sess"].unique():
            temp_df = df[df["id_sess"] == id_sess]
            # label each row as one second
            temp_df = temp_df.reset_index(drop=True).reset_index().rename({"index":"elapsed_sec"},axis=1)
            # trim the dataset when rolling 60 second diff is < 1
            temp_df = self.find_longest_zeroes(temp_df, col='cadence',num=0, roll=60)
            # remove extreme cadences
            temp_df = self.remove_extreme_cad(temp_df, id_sess)
            df_bike = df_bike.append(temp_df)

        if save_table:
            # save to db
            db = dbInfo()
            db.save_table(df_bike, "bike_data")
        # this is the final result
        self.result = df_bike.reset_index(drop=True)

    def load_and_organize(self, df):
        """
        Reads in combined_files excel sheet, processes it
        """
        # load
        df = df.drop("Millitm", axis=1)
        cols = [col.lower() for col in df.columns]
        df.columns = cols
        df["date"] = pd.to_datetime(df["date"])

        # organize
        df["my_id"] = df["id"].str.extract("(SMB_\d\d\d)")
        df["my_id"] = df["my_id"].str.replace("_", "")
        df["day"] = df["id"].str.extract("(day\d)")
        df["unknown"] = df["id"].str.extract("day\d_(\d\d)")
        df["unknown"] = df["unknown"].astype(int)
        df["id_sess"] = df["my_id"] + "_" + df["day"]
        df = df.drop("id", axis=1)

        df["date"] = df["date"].astype(str)
        df["datetime"] = df["date"] + " " + df["time"]
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df

    def find_elapsed_sec(self, dataframe):
        """
        Find the amount of time that elapsed_sec since first timestamp of that particular session
        Also extracts the exact second each row was captured

        input
        -----
        dataframe: pd.DataFrame
            Dataframe for just one participant and one session
        """
        init_time = dataframe.iloc[0, -1]
        dataframe["elapsed_sec"] = dataframe["datetime"].apply(
            lambda x: dt.timedelta.total_seconds(x - init_time)
        )
        return dataframe
    
    def find_longest_zeroes(self, dataframe, col='cadence', num=0, roll=60):
        '''
        A different method for finding trailing zeroes in dataset. 
        Does not find zeroes at beginning of dataset, only at the end.

        input
        -----
        dataframe: pd.DataFrame
        col: str
            Column that has data to be cut
        num: int or float
            After taking the rolling difference over 60 seconds, anything 
            less than or equal to this number is eligible to be thrown out
        '''
        cut_us = {}
        cut_df = pd.DataFrame()
        for id_sess in dataframe['id_sess'].unique():
            temp_df = dataframe[dataframe['id_sess'] == id_sess].reset_index(drop=True)
            # here we take the rolling diff, because sometimes there are long repeats of the same cadence 
            # that needs to be cut off
            temp_df[f"{col}_roll_diff"] = temp_df[col].diff(periods=roll)
            # the first couple are always nans, just assume those are zeroes. This is fine ... right ??
            temp_df[f"{col}_roll_diff"] = temp_df[f"{col}_roll_diff"].fillna(0)
            # round them to integers, because sometimes 0.0000432 is really just zero
            temp_df[f"{col}_rounded"] = temp_df[f"{col}_roll_diff"].apply(lambda x: int(round(x)))

            ### This is from stackoverflow: https://stackoverflow.com/a/67438717/9866659
            mask = temp_df[f"{col}_rounded"] == num # if the difference is num (0), thats bad.
            counts = temp_df[mask].groupby((~mask).cumsum()).transform('count')[col]
            idx = counts.idxmax() # returns first instance of longest sequence of <1s
            ### End stackoverflow

            # 2000 corresponds to 33 minutes
            # 
            # 250 corresponds to finding at least 250 sequential Trues

            if (idx > 2000) & (counts.loc[idx] > 150):
                cut_us[id_sess] = idx
                temp_df = temp_df.iloc[:idx,:]
            cut_df = cut_df.append(temp_df)
        return cut_df
    
    def remove_extreme_cad(self, dataframe, id_sess):
        '''
        Removes negative cadences and cadences > 150 rpm
        '''
        new_df = dataframe[(dataframe['cadence'] <= 150) & (dataframe['cadence'] >= 0)]
        if c.mylist(new_df['elapsed_sec']):
            return new_df
        else:
            print(f"WARNING: {id_sess} `elapsed_sec` is no longer sequential")
            return new_df


class dfDemos:
    """
    Extracts UPDRS, effort, and demographics data. Organizes, processes, and then merges them together.
    """

    def __init__(self, bike_df, save_table=False):
        """
        Coordinates the updrs, effort, demos functions. Then merges the three datasets
        """
        updrs = self.load_updrs()
        df_pow = self.create_effort(bike_df)
        mean_pow = df_pow.groupby("id").mean().reset_index()
        demographics = self.load_demos(df_pow)

        demos = self.merge_cats(updrs, mean_pow, demographics)

        if save_table:
            db = dbInfo()
            db.save_table(demos, "demos")

        self.result = demos

    def load_updrs(self):
        """
        Loads and processes UPDRS data from Smartbike_NIH_variabiliity_UPDRS excel sheet
        """

        updrs = pd.read_excel("data/Smartbike_NIH_variabiliity_UPDRS.xlsx")
        updrs = updrs.iloc[:, 0:4]
        updrs.columns = ["id", "group", "updrs_pre", "updrs_post"]
        # drop means and other irrelevant rows
        updrs = updrs.drop([0, 1, 24, 25, 26, 27, 53, 54, 55, 56]).reset_index(
            drop=True
        )

        updrs["id"] = updrs["id"].str.replace("_", "")
        # calculate change in UPDRS
        updrs["updrs_chg"] = updrs["updrs_post"] - updrs["updrs_pre"]

        return updrs

    def create_effort(self, dataframe, save_table=False):
        """
        Calculates and creates the effort column for each id_sess. Dataframe is the raw bike dataframe with an id_sess column
        """
        df_pow = h.perc_time_in_col(dataframe, "power")
        df_pow["day"] = df_pow["id_sess"].str.split("_", expand=True)[1]
        df_pow["id"] = df_pow["id_sess"].str.split("_day", expand=True)[0]
        df_pow["id"] = df_pow["id"].str.replace("_", "")
        df_pow = df_pow.reset_index(drop=True)

        if save_table:
            db = dbInfo()
            db.save_table(df_pow, "effort")

        return df_pow

    def load_demos(self, df_pow):
        """
        Merges updrs and effort datasets with the demographics dataset
        """
        demos = pd.read_excel("data/NIH_dynamic_demographics.xlsx", sheet_name=0)
        demos.columns = [
            "id",
            "group",
            "age",
            "gender_1_female",
            "hyarr",
            "height",
            "weight",
            "bmi",
            "months",
            "none",
            "ledd",
        ]
        demos = demos.drop(["none", "group"], axis=1)
        demos["id"] = demos["id"].str.replace("_", "")

        return demos

    def merge_cats(self, updrs, mean_pow, demos):
        """
        Merges the datasets, then formats the resulting dataframe.
        """
        cats = demos.merge(updrs, on="id")
        cats = cats.merge(mean_pow[["id", "perc_time_in_pos"]], on="id")

        cats = cats.rename({"perc_time_in_pos": "mean_effort"}, axis=1)
        cats = cats.astype(
            {"updrs_pre": float, "updrs_post": float, "updrs_chg": float}
        )
        cats["gender"] = cats["gender_1_female"].map({1: "female", 2: "male"})
        return cats


class dfEntropy:
    """
    Extracts entropy data from Smartbike_NIH_variabiliity_UPDRS and formats, restructures the dataset from wide to long form.
    """

    def __init__(self, save_table=False):
        """
        Coordinates the self.functions
        """
        raw_entropy = self.load_and_organize()
        entropy = self.restructure_entropy(raw_entropy)

        if save_table:
            db = dbInfo()
            db.save_table(entropy, "entropy")

        self.result = entropy

    def load_and_organize(self):
        # load the data
        df = pd.read_excel(
            "data/Smartbike_NIH_variabiliity_UPDRS.xlsx", sheet_name=0, header=2
        )
        df = df.drop(
            [22, 23, 24, 25, 51, 52, 53, 54], axis=0
        )  # drop Average rows and rows that separated dynamic from static data
        df = df.drop(
            ["Unnamed: 5", "Unnamed: 66", "Unnamed: 67"], axis=1
        )  # drop empties and last two columns that are duplicates of first columns 1,4
        df = df.iloc[
            :, :50
        ]  # drop last 15 columns, they are all averages of the sessions
        df = df.reset_index(drop=True)

        self.last_cols = []
        for s in range(1, 4):
            for var in range(1, 4):
                if var == 1:
                    my_var = "hr"
                    for stat in range(1, 6):
                        self.make_last_cols(s, my_var, stat)
                elif var == 2:
                    my_var = "cad"
                    for stat in range(1, 6):
                        self.make_last_cols(s, my_var, stat)
                elif var == 3:
                    my_var = "pow"
                    for stat in range(1, 6):
                        self.make_last_cols(s, my_var, stat)
        first_cols = ["subject", "group", "updrs_pre", "updrs_post", "updrs_chg"]
        cols = first_cols + self.last_cols

        # Make sure they are the same length
        if len(df.columns) == len(cols):
            df.columns = cols
            # Format all columns, except the first 2
            for col in df.columns[2:]:
                df[col] = pd.to_numeric(df[col])
            return df
        else:
            print("An error occurred in dfEntropy.load_and_organize()!")
            return

    def make_last_cols(self, s, my_var, my_stat):
        """
        Helper function: Makes a list of all sessions, variables, and statistic columns
        """
        if my_stat == 1:
            self.last_cols.append(f"sess{s}_{my_var}_mean")
        if my_stat == 2:
            self.last_cols.append(f"sess{s}_{my_var}_std")
        if my_stat == 3:
            self.last_cols.append(f"sess{s}_{my_var}_samen")
        if my_stat == 4:
            self.last_cols.append(f"sess{s}_{my_var}_apen")
        if my_stat == 5:
            self.last_cols.append(f"sess{s}_{my_var}_spen")

    def restructure_entropy(self, dataframe):
        """
        Restructures entropy dataframe from wide to long
        """

        # Select dfs
        df_sess1 = dataframe.iloc[:, :20]
        df_sess2 = dataframe.iloc[:, np.r_[0:5, 20:35]]
        df_sess3 = dataframe.iloc[:, np.r_[0:5, 35:50]]

        # Create list of var + stat columns
        sess_last_cols = []

        for var in ["hr", "cad", "pow"]:
            for stat in ["mean", "std", "samen", "apen", "spen"]:
                sess_last_cols.append(f"{var}_{stat}")

        # Combine first and last columns
        sess_first_cols = ["subject", "group", "updrs_pre", "updrs_post", "updrs_chg"]
        sess_cols = sess_first_cols + sess_last_cols

        # Rename all columns
        df_sess1.columns = sess_cols
        df_sess2.columns = sess_cols
        df_sess3.columns = sess_cols

        # Add session number column
        df_sess1.loc[:,"session"] = 1
        df_sess2.loc[:,"session"] = 2
        df_sess3.loc[:,"session"] = 3

        df2 = pd.concat([df_sess1, df_sess2, df_sess3], axis=0).reset_index(drop=True)
        df2["session"] = df2["session"].astype("category")

        # code which group each participant belonged to
        codes = {1: "static", 2: "dynamic"}  # Unnamed:1 col  # Unnamed:1 col
        df2["grp_coded"] = df2["group"].map(codes)
        # filter to just the dynamic group
        df2 = df2[df2["grp_coded"] == "dynamic"]
        df2.reset_index(drop=True, inplace=True)
        df2['subject'] = df2['subject'].str.replace('_','')
        return df2


class dbInfo:
    """
    Saves the newly processed dataframes into nih.db
    """

    def __init__(self):
        """
        Initializes db
        """
        import sqlalchemy as sq

        engine = sq.create_engine("sqlite:///nih_scripts.db")
        self.cnx = engine.connect()

    def save_table(self, dataframe, table_name):
        try:
            dataframe.to_sql(table_name, con=self.cnx, index=False, if_exists="replace")
            print("Saved!")
        except:
            print("Failed")
