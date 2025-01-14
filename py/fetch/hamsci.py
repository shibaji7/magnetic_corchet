#!/usr/bin/env python

"""hamsci.py: module is dedicated to fetch HamSci database."""

__author__ = "Chakraborty, S."
__copyright__ = ""
__credits__ = []
__license__ = "MIT"
__version__ = "1.0."
__maintainer__ = "Chakraborty, S."
__email__ = ""
__status__ = "Research"


import datetime as dt
import json
import os
from ftplib import FTP

import numpy as np
import pandas as pd
import pytz
from cryptography.fernet import Fernet
from hamsci_psws import grape1
from loguru import logger


class Conn2Remote(object):
    def __init__(self, host, user, password, port=22, passcode=None):
        self.host = host
        self.user = user
        self.password = password
        self.passcode = passcode
        self.port = port
        self.con = False
        if passcode:
            self.decrypt()
        self.conn()
        return

    def decrypt(self):
        passcode = bytes(self.passcode, encoding="utf8")
        cipher_suite = Fernet(passcode)
        self.user = cipher_suite.decrypt(bytes(self.user, encoding="utf8")).decode(
            "utf-8"
        )
        self.host = cipher_suite.decrypt(bytes(self.host, encoding="utf8")).decode(
            "utf-8"
        )
        self.password = cipher_suite.decrypt(
            bytes(self.password, encoding="utf8")
        ).decode("utf-8")
        return

    def conn(self):
        if not self.con:
            self.ftp = FTP(self.host, self.user, self.password)
            self.con = True
        return

    def close(self):
        if self.con:
            self.ftp.quit()
        return


def encrypt(host, user, password, filename="config/passcode.json"):
    passcode = Fernet.generate_key()
    cipher_suite = Fernet(passcode)
    host = cipher_suite.encrypt(bytes(host, encoding="utf8"))
    user = cipher_suite.encrypt(bytes(user, encoding="utf8"))
    password = cipher_suite.encrypt(bytes(password, encoding="utf8"))
    with open(filename, "w") as f:
        f.write(
            json.dumps(
                {
                    "user": user.decode("utf-8"),
                    "host": host.decode("utf-8"),
                    "password": password.decode("utf-8"),
                    "passcode": passcode.decode("utf-8"),
                },
                sort_keys=True,
                indent=4,
            )
        )
    return


def get_session(filename="config/passcode.json", isclose=False):
    with open(filename, "r") as f:
        obj = json.loads("".join(f.readlines()))
        conn = Conn2Remote(
            obj["host"],
            obj["user"],
            obj["password"],
            passcode=obj["passcode"],
        )
    if isclose:
        conn.close()
    return conn


class HamSci(object):
    """
    This class is help to extract the dataset from HamSci database and plot.
    """

    def __init__(self, base, dates, fList, close=True):
        """
        Parameters:
        -----------
        base: Base location
        fList: Frequency of operation in MHz (list)
        dates: Start and end dates
        close: Close FTP connection
        """
        self.fList = fList
        self.dates = self.parse_dates(dates)
        self.date_range = [
            dates[0].replace(tzinfo=pytz.utc),
            dates[1].replace(tzinfo=pytz.utc),
        ]
        self.base = base + "hamsci/"
        if not os.path.exists(self.base):
            os.makedirs(self.base)
        logger.info("Loging into remote FTP")
        self.conn = get_session()
        self.fetch_files()
        if close:
            logger.info("System logging out from remote.")
            self.conn.close()
        return

    def parse_dates(self, dates):
        """
        Parsing dates
        """
        da = [
            dates[0].replace(minute=0, hour=0, second=0),
            dates[1].replace(minute=0, hour=0, second=0),
        ]
        return da

    def fetch_files(self):
        """
        Fetch all the available files on the given date/time range and frequencies.
        Compile and store to one location under other files.
        """
        o = []
        now = dt.date.today()
        # if now.year > self.dates[0].year:
        # if self.dates[0].year <= 2021:
        #     self.conn.ftp.cwd(str(self.dates[0].year))
        ret = []
        self.conn.ftp.dir("",ret.append)
        ret = [x.split()[-1] for x in ret if x.startswith("d")]
        files = self.conn.ftp.nlst()
        for file in files:
            if (".csv" in file) and ("FRQ" in file) and ("T000000Z" in file):
                info = file.split("_")
                date = dt.datetime.strptime(info[0].split("T")[0], "%Y-%m-%d")
                node, frq = info[1], info[-1].replace(".csv", "").replace(
                    "WWV", ""
                ).replace("CHU", "")
                if "p" in frq:
                    frq = frq.replace("p", ".")
                if frq.isnumeric():
                    frq = float(frq)
                    o.append({"node": node, "frq": frq, "fname": file, "date": date})
        o = pd.DataFrame.from_records(o)
        o.date = o.date.apply(lambda x: x.to_pydatetime())
        logger.info(f"Number of files {len(o)}")
        if self.fList:
            o = o.query("frq in @self.fList")
        o = o[(o.date >= self.dates[0]) & (o.date <= self.dates[1])]
        logger.info(f"Number of files after {len(o)}")
        logger.info(f"Start retreiveing Bin")
        for fn in o.fname:
            if not os.path.exists(self.base + fn):
                with open(self.base + fn, "wb") as fp:
                    self.conn.ftp.retrbinary(f"RETR {fn}", fp.write)
        return

    def load_nodes(self, freq):
        """
        Load files using grape1 library
        """
        import glob
        files = glob.glob(f"{self.base}*.csv")
        if len(files) > 0:
            inv = grape1.DataInventory(data_path=self.base)
            inv.filter(
                freq=freq,
                sTime=self.date_range[0],
                eTime=self.date_range[1],
            )
            gn = grape1.GrapeNodes(
                fpath="config/nodelist.csv", logged_nodes=inv.logged_nodes
            )
            return inv, gn
        else:
            return None, None

    def setup_plotting(
        self,
        freq=10e6,
    ):
        """
        Plot dataset in multipoint plot
        """
        self.gds = []
        inv, gn = self.load_nodes(freq)
        if inv:
            node_nrs = inv.get_nodes()
            for node in node_nrs:
                try:
                    logger.info(f"Node number: {node}")
                    gd = grape1.Grape1Data(
                        node,
                        freq,
                        self.date_range[0],
                        self.date_range[1],
                        inventory=inv,
                        grape_nodes=gn,
                        data_path=self.base,
                    )
                    gd.process_data()
                    self.gds.append(gd)
                except:
                    import traceback
                    traceback.print_exc()
                    logger.error("Sorry, issue occured!")
                    #raise Exception("Sorry, issue occured!")
        return self.gds

    def extract_stagging_data(
        self,
    ):
        """
        Extract observations for only analysis
        """
        sci = []
        for gd in self.gds:
            gd.df_params = gd.df_params | gd.meta
            sci.append(gd.df_params)
        return sci

    def extract_parameters(self, flare_timings, gds=None):
        """
        Extract Doppler Flash parameters
        """
        fl_start, fl_peak, fl_end = (
            flare_timings[0],
            flare_timings[1],
            flare_timings[2],
        )
        gds = gds if gds else self.gds
        new_gds = []
        for gd in gds:
            params = dict()
            o = gd.data["filtered"]["df"]
            if len(o) > 10:
                del_t = (o.UTC[1] - o.UTC[0]).total_seconds()
                rise = o[(o.UTC >= fl_start) & (o.UTC <= fl_peak)]
                fall = o[(o.UTC >= fl_peak) & (o.UTC <= fl_end)]
                params["rise_area"] = np.trapz(rise.Freq, dx=del_t)
                params["fall_area"] = np.trapz(fall.Freq, dx=del_t)
                params["peak"] = rise.Freq.max()
                setattr(gd, "df_params", params)
                new_gds.append(gd)
        self.gds = new_gds
        return


if __name__ == "__main__":
    dates = [
        dt.datetime(2021, 10, 28),
        dt.datetime(2021, 10, 29),
    ]
    fList = [10, 5, 2.5]
    base = "data/2021-10-28/"
    HamSci(base, dates, fList)
    # conn = get_session(isclose=True)