#!/usr/bin/env python

"""analysis.py: module is dedicated to fetch, filter, and save data for post_processing."""

__author__ = "Chakraborty, S."
__copyright__ = ""
__credits__ = []
__license__ = "MIT"
__version__ = "1.0."
__maintainer__ = "Chakraborty, S."
__email__ = "shibaji7@vt.edu"
__status__ = "Research"

import datetime as dt
import os
import sys

import numpy as np
import pandas as pd
from loguru import logger
from scipy.io import savemat

sys.path.extend(["py/", "py/fetch/", "py/geo/"])

from plotFoV import Fan
from plotRTI import RTI, GOESPlot, HamSciParamTS, HamSciTS


class Hopper(object):
    """
    This class is responsible for following
    operations for each flare event.
        i) Fetching HamSci, SD, SM, GOES dataset using .fetch module.
        ii) Summary plots for the dataset.
        iii) Store the data for post-processing.
    """

    def __init__(
        self,
        base,
        dates,
        rads,
        event,
        event_start,
        event_end,
        uid="shibaji7",
        mag_stations=None,
        stg=True,
    ):
        """
        Populate all data tables from GOES, FISM2, SuperDARN, and SuperMAG.
        """

        from darn import FetchData
        from flare import FlareTS
        from hamsci import HamSci
        from smag import SuperMAG

        self.base = base
        self.dates = dates
        self.rads = rads
        self.event = event
        self.event_start = event_start
        self.event_end = event_end
        self.uid = uid
        self.mag_stations = mag_stations

        if not os.path.exists(base):
            os.makedirs(base)
        self.flareTS = FlareTS(self.dates)
        self.GOESplot()
        self.darns = FetchData.fetch(base, self.rads, self.dates)
        self.magObs = SuperMAG(self.base, self.dates, stations=mag_stations)
        self.hamSci = HamSci(self.base, self.dates, None)
        self.GrepMultiplot()
        if stg:
            # self.GenerateRadarFoVPlots()
            # self.GenerateRadarRTIPlots()
            self.stage_analysis()
        return

    def CompileSMJSummaryPlots(
        self, id_scanx, fname_tag="SM-SD.%04d.png", plot_sm=True
    ):
        """
        Create SM/J plots overlaied SD data
        """
        return

    def GOESplot(self):
        """
        Create GOES plots
        """
        base = self.base + "figures/"
        os.makedirs(base, exist_ok=True)
        fname = f"{base}GOES.png"
        time = self.flareTS.dfs["goes"].time.tolist()
        xs, xl = (self.flareTS.dfs["goes"].xrsa, self.flareTS.dfs["goes"].xrsb)
        vlines, colors = (
            [self.event, self.event_start, self.event_end],
            ["k", "r", "r"],
        )
        GOESPlot(time, xl, xs, fname, vlines, colors, drange=self.dates)
        return

    def GrepMultiplot(self):
        """
        Create Latitude longitude dependent plots in Grape
        """
        vlines, colors = (
            [self.event, self.event_start, self.event_end],
            ["k", "r", "r"],
        )
        base = self.base + "figures/"
        os.makedirs(base, exist_ok=True)
        fname = f"{base}hamsci.png"
        self.hamSci.setup_plotting()
        HamSciTS(self.hamSci.gds, fname, drange=self.dates)
        flare_timings = pd.Series(
            [
                self.event_start,
                self.event,
                self.event_end,
            ]
        )
        flare_timings = flare_timings.dt.tz_localize("UTC")
        self.hamSci.extract_parameters(flare_timings)
        for i in range(len(self.hamSci.gds)):
            fname = f"{base}hamsci_{i}.png"
            HamSciParamTS(
                self.hamSci.gds,
                fname,
                flare_timings,
                drange=self.dates,
                index=i,
                vlines=vlines,
                colors=colors,
            )
        return

    def GenerateRadarRTIPlots(self):
        """
        Generate RTI summary plots.
        """
        base = self.base + "figures/rti/"
        os.makedirs(base, exist_ok=True)
        for rad in self.rads:
            if hasattr(self.darns[rad], "records") > 0:
                ffd = self.darns[rad].records
                for b in ffd.bmnum.unique():
                    rti = RTI(
                        100,
                        self.dates,
                        fig_title=f"{rad.upper()} / {self.dates[0].strftime('%Y-%m-%d')} / {b}",
                    )
                    ax = rti.addParamPlot(ffd, b, "", cbar=True)
                    rti.add_vlines(ax, [self.event, self.event_start], ["k", "r"])
                    rti.save(base + f"{rad}-{'%02d'%b}.png")
                    rti.close()
        return

    def GenerateRadarFoVPlots(self):
        """
        Generate FoV summary plots.
        """
        base = self.base + "figures/fan/"
        os.makedirs(base, exist_ok=True)
        for rad in self.rads:
            if hasattr(self.darns[rad], "records") > 0:
                dmin = np.rint(self.darns[rad].records.scan_time.iloc[0] / 60.0)
                dN = int(
                    np.rint((self.dates[1] - self.dates[0]).total_seconds() / 60.0)
                )
                dates = [
                    self.dates[0] + dt.timedelta(minutes=i * dmin) for i in range(dN)
                ]
                for d in dates:
                    fan = Fan([rad], d)
                    fan.generate_fov(self.darns)
                    fan.save(base + f"{rad}-{d.strftime('%H-%M')}.png")
                    fan.close()
        return

    def stage_analysis(self):
        """
        Stage dataset for next analysis
        """
        base = "data/stage/{Y}-{m}-{d}-{H}-{M}/".format(
            Y=self.event.year,
            m="%02d" % self.event.month,
            d="%02d" % self.event.day,
            H="%02d" % self.event.hour,
            M="%02d" % self.event.minute,
        )
        os.makedirs(base, exist_ok=True)
        self.stage = dict(darn=[], hamsci=None, flare=None)
        for rad in self.rads:
            self.stage["darn"].append(
                self.darns[rad].extract_stagging_data(self.event_start, self.event_end),
            )
        self.stage["hamsci"] = self.hamSci.extract_stagging_data()
        self.stage["flare"] = self.flareTS.extract_stagging_data()
        self.stage["flare"]["rise_time"] = (
            self.event - self.event_start
        ).total_seconds()
        self.stage["flare"]["fall_time"] = (self.event_end - self.event).total_seconds()
        logger.info(f"file: {base}stage0.mat")
        savemat(base + "stage0.mat", self.stage)
        return


def fork_event_based_mpi(file="config/events.csv"):
    """
    Load all the events from
    events list files and fork Hopper
    to pre-process and store the
    dataset.
    """
    o = pd.read_csv(file, parse_dates=["event", "start", "end", "s_time", "e_time"])
    for i, row in o.iterrows():
        ev = row["event"]
        base = "data/{Y}-{m}-{d}-{H}-{M}/".format(
            Y=ev.year,
            m="%02d" % ev.month,
            d="%02d" % ev.day,
            H="%02d" % ev.hour,
            M="%02d" % ev.minute,
        )
        dates = [row["s_time"], row["e_time"]]
        rads = row["rads"].split("-")
        Hopper(base, dates, rads, ev, row["start"], row["end"])
        break
    return


if __name__ == "__main__":
    fork_event_based_mpi()
