#!/usr/bin/env python

"""darndata.py: utility module to fetch fitacf<v> level data."""

__author__ = "Chakraborty, S."
__copyright__ = ""
__credits__ = []
__license__ = "MIT"
__version__ = "1.0."
__maintainer__ = "Chakraborty, S."
__email__ = "shibaji7@vt.edu"
__status__ = "Research"

import bz2
import datetime as dt
import glob
import os

import numpy as np
import pandas as pd
import pydarn
from tqdm import tqdm
from loguru import logger


class Beam(object):
    """Class to hold one beam object"""

    def __init__(self):
        """initialize the instance"""
        return

    def set(
        self,
        time,
        d,
        s_params=["bmnum", "noise.sky", "tfreq", "scan", "nrang"],
        v_params=["v", "w_l", "gflg", "p_l", "slist", "v_e"],
        k=None,
    ):
        """
        Set all parameters
        time: datetime of beam
        d: data dict for other parameters
        s_param: other scalar params
        v_params: other list params
        """
        for p in s_params:
            if p in d.keys():
                if p == "scan" and d[p] != 0:
                    setattr(self, p, 1)
                else:
                    setattr(self, p, d[p]) if k is None else setattr(self, p, d[p][k])
            else:
                setattr(self, p, None)
        for p in v_params:
            if p in d.keys():
                setattr(self, p, d[p])
            else:
                setattr(self, p, [])
        self.time = time
        return

    def copy(self, bm):
        """Copy all parameters"""
        for p in bm.__dict__.keys():
            setattr(self, p, getattr(bm, p))
        return


class Scan(object):
    """Class to hold one scan (multiple beams)"""

    def __init__(self, stime=None, etime=None, s_mode="normal"):
        """
        initialize the parameters which will be stored
        stime: start time of scan
        etime: end time of scan
        s_mode: scan type
        """
        self.stime = stime
        self.etime = etime
        self.s_mode = s_mode
        self.beams = []
        return

    def update_time(self):
        """
        Update stime and etime of the scan.
        up: Update average parameters if True
        """
        self.stime = min([b.time for b in self.beams])
        self.etime = max([b.time for b in self.beams])
        self.scan_time = (self.etime - self.stime).total_seconds()
        return


class FetchData(object):
    """Class to fetch data from fitacf files for one radar for atleast a day"""

    def __init__(
        self,
        rad,
        date_range,
        ftype="fitacf",
        files=None,
        verbose=True,
        regex="/sd-data/{year}/{ftype}/{rad}/{date}.*{ftype}*.bz2",
    ):
        """
        initialize the vars
        rad = radar code
        date_range = [ start_date, end_date ]
        files = List of files to load the data from
        e.x :   rad = "sas"
                date_range = [
                    datetime.datetime(2017,3,17),
                    datetime.datetime(2017,3,18),
                ]
        """
        self.rad = rad
        self.date_range = date_range
        self.files = files
        self.verbose = verbose
        self.regex = regex
        self.ftype = ftype
        if (rad is not None) and (date_range is not None) and (len(date_range) == 2):
            self._create_files()
        self.s_params = [
            "bmnum",
            "noise.sky",
            "tfreq",
            "scan",
            "nrang",
            "intt.sc",
            "intt.us",
            "mppul",
            "rsep",
            "cp",
            "frang",
            "smsep",
            "lagfr",
            "channel",
            "mplgs",
            "nave",
            "noise.search",
            "mplgexs",
            "xcf",
            "noise.mean",
            "ifmode",
            "bmazm",
            "rxrise",
            "mpinc",
        ]
        self.v_params = ["v", "w_l", "gflg", "p_l", "slist"]
        self.hdw_data = pydarn.read_hdw_file(self.rad)
        self.lats, self.lons = pydarn.Coords.GEOGRAPHIC(self.hdw_data.stid)
        return

    def _create_files(self):
        """
        Create file names from date and radar code
        """
        if self.files is None:
            self.files = []
        reg_ex = self.regex
        days = (self.date_range[1] - self.date_range[0]).days + 2
        ent = -1
        for d in range(-1, days):
            e = self.date_range[0] + dt.timedelta(days=d)
            fnames = sorted(
                glob.glob(
                    reg_ex.format(
                        year=e.year,
                        rad=self.rad,
                        ftype=self.ftype,
                        date=e.strftime("%Y%m%d"),
                    )
                )
            )
            for fname in fnames:
                tm = fname.split(".")[1]
                sc = fname.split(".")[2]
                dus = dt.datetime.strptime(
                    fname.split(".")[0].split("/")[-1] + tm + sc, "%Y%m%d%H%M%S"
                )
                due = dus + dt.timedelta(hours=2)
                if (ent == -1) and (dus <= self.date_range[0] <= due):
                    ent = 0
                if ent == 0:
                    self.files.append(fname)
                if (ent == 0) and (dus <= self.date_range[1] <= due):
                    ent = -1
        return

    def _parse_data(self, data, s_params, v_params, by, scan_prop):
        """
        Parse data by data type
        data: list of data dict
        params: parameter list to fetch
        by: sort data by beam or scan
        scan_prop: provide scan properties if by='scan'
                        {"s_mode": type of scan, "s_time": duration in min}
        """
        _b, _s = [], []
        if self.verbose:
            logger.info("Started converting to beam data.")
        for d in data:
            time = dt.datetime(
                d["time.yr"],
                d["time.mo"],
                d["time.dy"],
                d["time.hr"],
                d["time.mt"],
                d["time.sc"],
                d["time.us"],
            )
            if time >= self.date_range[0] and time <= self.date_range[1]:
                bm = Beam()
                bm.set(time, d, s_params, v_params)
                _b.append(bm)
        if self.verbose:
            logger.info("Converted to beam data.")
        if by == "scan":
            if self.verbose:
                logger.info("Started converting to scan data.")
            scan, sc = 0, Scan(None, None, scan_prop["s_mode"])
            sc.beams.append(_b[0])
            for _ix, d in enumerate(_b[1:]):
                if d.scan == 1 and d.time != _b[_ix].time:
                    sc.update_time()
                    _s.append(sc)
                    sc = Scan(None, None, scan_prop["s_mode"])
                    sc.beams.append(d)
                else:
                    sc.beams.append(d)
            _s.append(sc)
            if self.verbose:
                logger.info("Converted to scan data.")
        return _b, _s, True

    def convert_to_pandas(
        self,
        beams,
    ):
        """
        Convert the beam data into dataframe
        """
        if "time" not in self.s_params:
            self.s_params.append("time")
        _o = dict(
            zip(
                self.s_params + self.v_params,
                ([] for _ in self.s_params + self.v_params),
            )
        )
        for b in beams:
            l = len(getattr(b, "slist"))
            for p in self.v_params:
                _o[p].extend(getattr(b, p))
            for p in self.s_params:
                _o[p].extend([getattr(b, p)] * l)
        L = len(_o["slist"])
        for p in self.s_params + self.v_params:
            if len(_o[p]) < L:
                l = len(_o[p])
                _o[p].extend([np.nan] * (L - l))
        return pd.DataFrame.from_records(_o)

    def scans_to_pandas(
        self,
        scans,
        start_scnum=0,
    ):
        """
        Convert the scan data into dataframe
        """
        if "time" not in self.s_params:
            self.s_params.append("time")
        _o = dict(
            zip(
                self.s_params + self.v_params + ["scnum"],
                ([] for _ in self.s_params + self.v_params + ["scnum"]),
            )
        )
        echoes = []
        for idn, s in enumerate(scans):
            for b in s.beams:
                l = len(getattr(b, "slist"))
                for p in self.v_params:
                    _o[p].extend(getattr(b, p))
                for p in self.s_params:
                    _o[p].extend([getattr(b, p)] * l)
                _o["scnum"].extend([idn + start_scnum] * l)
                eRec = {
                    "time": getattr(b, "time"),
                    "bmnum": getattr(b, "bmnum"),
                    "eCount": len(getattr(b, "slist"))
                    if hasattr(b, "slist")
                    else 0,
                }
                echoes.append(eRec)
            L = len(_o["slist"])
            for p in self.s_params + self.v_params:
                if len(_o[p]) < L:
                    l = len(_o[p])
                    _o[p].extend([np.nan] * (L - l))
        return pd.DataFrame.from_records(_o), pd.DataFrame.from_records(echoes)

    def __get_location__(self, row):
        """
        Get locations
        """
        lat, lon, dtime = (
            self.lats[row["slist"], row["bmnum"]],
            self.lons[row["slist"], row["bmnum"]],
            row["time"],
        )
        row["glat"], row["glon"] = lat, lon
        return row

    def pandas_to_beams(
        self,
        df,
    ):
        if "time" not in self.s_params:
            self.s_params.append("time")
        """
        Convert the dataframe to beam
        """
        beams = []
        for bm in np.unique(df.bmnum):
            o = df[df.bmnum == bm]
            d = o.to_dict(orient="list")
            for p in self.s_params:
                d[p] = d[p][0]
            b = Beam()
            b.set(o.time.tolist()[0], d, self.s_params, self.v_params)
            beams.append(b)
        return beams

    def pandas_to_scans(
        self,
        df,
        smode="normal",
    ):
        """
        Convert the dataframe to scans
        """
        if "time" not in self.s_params:
            self.s_params.append("time")
        scans = []
        for sn in np.unique(df.scnum):
            o = df[df.scnum == sn]
            beams = self.pandas_to_beams(o)
            sc = Scan(None, None, smode)
            sc.beams.extend(beams)
            sc.update_time()
            scans.append(sc)
        return scans

    def fetch_data(
        self,
        by="beam",
        scan_prop={"s_time": 1, "s_mode": "normal"},
    ):
        """
        Fetch data from file list and return the dataset
        params: parameter list to fetch
        by: sort data by beam or scan
        scan_prop: provide scan properties if by='scan'
                   {"s_mode": type of scan, "s_time": duration in min}
        """
        data = []
        for f in self.files:
            with bz2.open(f) as fp:
                fs = fp.read()
            if self.verbose:
                logger.info(f"File:{f}")
            reader = pydarn.SuperDARNRead(fs, True)
            records = reader.read_fitacf()
            data += records
        if (by is not None) and (len(data) > 0):
            data = self._parse_data(data, self.s_params, self.v_params, by, scan_prop)
            return data
        else:
            return (None, None, False)

    @staticmethod
    def fetch(base, rads, date_range, ftype="fitacf", files=None, verbose=True):
        """
        Static method to fetch datasets
        """
        tqdm.pandas()
        os.makedirs(base, exist_ok=True)
        fds = {}
        for rad in rads:
            file, efile = os.path.join(f"{base}{rad}.csv"), os.path.join(
                f"{base}e{rad}.csv"
            )
            logger.info(f"Load file: {file}")
            fd = FetchData(rad, date_range, ftype, files, verbose)
            if os.path.exists(file):
                fd.records = pd.read_csv(file, parse_dates=["time"])
                fd.echoRecords = pd.read_csv(efile, parse_dates=["time"])
                logger.info(f"Data length {rad}: {len(fd.records)}")
            else:
                _, scans, data_exists = fd.fetch_data(by="scan")
                if data_exists:
                    scan_time = scans[0].scan_time
                    fd.records, fd.echoRecords = fd.scans_to_pandas(scans)
                    logger.info(f"Data length {rad}: {len(fd.records)}")
                    if len(fd.records) > 0:
                        fd.records["srange"] = fd.records.frang + (
                            fd.records.slist * fd.records.rsep
                        )
                        fd.records["intt"] = (
                            fd.records["intt.sc"] + 1.0e-6 * fd.records["intt.us"]
                        )
                        fd.records = fd.records.progress_apply(
                            fd.__get_location__, axis=1
                        )
                        fd.records["scan_time"] = scan_time
                        fd.records.to_csv(file, index=False, header=True)
                        fd.echoRecords.to_csv(efile, index=False, header=True)
                else:
                    logger.info(f"Data does not exists: {rad}!")
            fds[rad] = fd
        return fds
