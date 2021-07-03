"""
Unit test to compare new scripts with the results gotten from their equivalent notebooks.
"""
import pandas as pd
import pytest
import dynbike_helper_functions.helpers as h
import raw_processing as r

dba = h.dbConnect("sqlite:///nih_ntbk.db")


@pytest.fixture()
def ntbk_bike_sample_data():
    sample_data = {
        "Date": ["10/19/2012", "10/19/2012", "10/19/2012", "10/19/2012", "10/19/2012"],
        "Time": ["14:08:19", "14:08:20", "14:08:21", "14:08:22", "14:08:23"],
        "Millitm": [531, 531, 531, 531, 531],
        "HR": [69, 69, 69, 69, 68],
        "Cadence": [0.00241382, 0.00241382, 0.00182294, -7.543e-05, -6.286e-05],
        "Power": [0.0, 0.0, 0.0, 0.0, 0.0],
        "ID": [
            "SMB_024_day1_02",
            "SMB_024_day1_02",
            "SMB_024_day1_02",
            "SMB_024_day1_02",
            "SMB_024_day1_02",
        ],
    }
    return pd.DataFrame.from_dict(sample_data)


@pytest.fixture()
def ntbk_bike_sample_answ():
    """
    Loads bike_data from nih_ntbk.db
    """
    sample_dict = {
        "datetime": [
            pd.to_datetime("2012-10-19 14:08:19"),
            pd.to_datetime("2012-10-19 14:08:20"),
            pd.to_datetime("2012-10-19 14:08:21"),
            pd.to_datetime("2012-10-19 14:08:22"),
            pd.to_datetime("2012-10-19 14:08:23"),
        ],
        "date": ["2012-10-19", "2012-10-19", "2012-10-19", "2012-10-19", "2012-10-19"],
        "time": ["14:08:19", "14:08:20", "14:08:21", "14:08:22", "14:08:23"],
        "id_sess": [
            "SMB024_day1",
            "SMB024_day1",
            "SMB024_day1",
            "SMB024_day1",
            "SMB024_day1",
        ],
        "my_id": ["SMB024", "SMB024", "SMB024", "SMB024", "SMB024"],
        "day": ["day1", "day1", "day1", "day1", "day1"],
        "unknown": [2, 2, 2, 2, 2],
        "hr": [69, 69, 69, 69, 68],
        "power": [0.0, 0.0, 0.0, 0.0, 0.0],
        "cadence": [0.00241382, 0.00241382, 0.00182294, -7.543e-05, -6.286e-05],
        "elapsed_sec": [0.0, 1.0, 2.0, 3.0, 4.0],
    }
    sample_df = pd.DataFrame.from_dict(sample_dict)

    return sample_df


@pytest.fixture()
def ntbk_demos():
    """
    Loads demos from nih_ntbk.db
    """
    data = dba.load_table("demos")

    return data


@pytest.fixture()
def ntbk_effort():
    """
    Loads effort from nih_ntbk.db
    """
    data = dba.load_table("effort")

    return data


@pytest.fixture()
def ntbk_entropy():
    """
    Loads entropy from nih_ntbk.db
    """
    data = dba.load_table("entropy")

    return data


# ============================================== #


def test_dfBike(ntbk_bike_sample_data, ntbk_bike_sample_answ):

    s = r.dfBike(use_this=ntbk_bike_sample_data, save_table=False)
    calc_result = s.df_bike

    assert all(calc_result == ntbk_bike_sample_answ)


def test_dfDemos(ntbk_bike_sample_data, ntbk_demos):
    s = r.dfDemos(ntbk_bike_sample_data, save_table=False)
    calc_result = s.demos

    assert all(calc_result == ntbk_demos)


def test_dfEntropy(ntbk_entropy):
    s = r.dfEntropy(save_table=False)
    calc_result = s.entropy

    assert all(calc_result == ntbk_entropy)
