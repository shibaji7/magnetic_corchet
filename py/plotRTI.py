#!/usr/bin/env python

"""plot.py: module is dedicated RTI plotting tools, summary plots."""

__author__ = "Chakraborty, S."
__copyright__ = ""
__credits__ = []
__license__ = "MIT"
__version__ = "1.0."
__maintainer__ = "Chakraborty, S."
__email__ = "shibaji7@vt.edu"
__status__ = "Research"

import datetime as dt

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import utils
from pysolar.solar import get_altitude_fast


class RTI(object):
    """
    Create plots for velocity, width, power, elevation angle, etc.
    """

    def __init__(
        self,
        nGates,
        drange,
        fig_title=None,
        num_subplots=1,
        angle_th=100.0,
        science=True,
    ):
        if science:
            plt.style.use(["science", "ieee"])
            plt.rcParams.update(
                {
                    "figure.figsize": np.array([8, 6]),
                    "text.usetex": True,
                    "font.family": "sans-serif",
                    "font.sans-serif": [
                        "Tahoma",
                        "DejaVu Sans",
                        "Lucida Grande",
                        "Verdana",
                    ],
                    "font.size": 10,
                }
            )
        else:
            mpl.rcParams["font.size"] = 16
            mpl.rcParams["font.weight"] = "bold"
            mpl.rcParams["axes.labelweight"] = "bold"
            mpl.rcParams["axes.titleweight"] = "bold"
            mpl.rcParams["axes.grid"] = True
            mpl.rcParams["grid.linestyle"] = ":"
            mpl.rcParams["figure.figsize"] = np.array([15, 8])
            mpl.rcParams["axes.xmargin"] = 0

        self.nGates = nGates
        self.drange = drange
        self.num_subplots = num_subplots
        self._num_subplots_created = 0
        self.fig = plt.figure(figsize=(6, 3 * num_subplots), dpi=180)
        if fig_title:
            plt.suptitle(
                fig_title, x=0.075, y=0.99, ha="left", fontweight="bold", fontsize=12
            )
        self.angle_th = angle_th
        return

    def addParamPlot(
        self,
        df,
        beam,
        title,
        p_max=100,
        p_min=-100,
        xlabel="Time [UT]",
        zparam="v",
        label="Velocity [m/s]",
        yscale="srange",
        cmap=plt.cm.jet_r,
        cbar=False,
        fov=None,
    ):
        if yscale == "srange":
            yrange, ylab = (
                self.nGates * df.rsep.tolist()[0] + df.frang.tolist()[0],
                "Slant Range [km]",
            )
        else:
            yrange, ylab = (self.nGates, "Range Gates")
        ax = self._add_axis()
        df = df[df.bmnum == beam]
        X, Y, Z = utils.get_gridded_parameters(
            df, xparam="time", yparam=yscale, zparam=zparam, rounding=False
        )
        ax.xaxis.set_major_formatter(mdates.DateFormatter("$%H^{%M}$"))
        if (self.drange[1] - self.drange[0]).total_seconds() / 3600 <= 1.0:
            major_locator = mdates.MinuteLocator(byminute=range(0, 60, 10))
        elif (self.drange[1] - self.drange[0]).total_seconds() / 3600 <= 4.0:
            major_locator = mdates.MinuteLocator(byminute=range(0, 60, 30))
        else:
            major_locator = mdates.HourLocator(byhour=range(0, 24, 4))
        ax.xaxis.set_major_locator(major_locator)
        ax.set_xlabel(xlabel, fontdict={"size": 11, "fontweight": "bold"})
        ax.set_xlim([mdates.date2num(self.drange[0]), mdates.date2num(self.drange[1])])
        ax.set_ylim(0, yrange)
        ax.set_ylabel(ylab, fontdict={"size": 11, "fontweight": "bold"})
        im = ax.pcolormesh(
            X,
            Y,
            Z.T,
            lw=0.01,
            edgecolors="None",
            cmap=cmap,
            snap=True,
            vmax=p_max,
            vmin=p_min,
            shading="auto",
        )
        if cbar:
            self._add_colorbar(self.fig, ax, im, label=label)
        if title:
            ax.set_title(title, loc="left", fontdict={"fontweight": "bold"})
        if fov:
            self.overlay_sza(
                fov,
                ax,
                df.time.unique(),
                beam,
                [0, self.nGates],
                df.rsep.iloc[0],
                df.frang.iloc[0],
                yscale,
            )
        return ax

    def add_vlines(self, ax, vlines, colors):
        """
        Adding vertical lines
        """
        for vline, color in zip(vlines, colors):
            ax.axvline(vline, color=color, ls="--", lw=0.6)
        return

    def overlay_sza(self, fov, ax, times, beam, gate_range, rsep, frang, yscale):
        """
        Add terminator to the radar
        """
        R = 6378.1
        gates = np.arange(gate_range[0], gate_range[1])
        dn_grid = np.zeros((len(times), len(gates)))
        for i, d in enumerate(times):
            d = dt.datetime.utcfromtimestamp(d.astype(dt.datetime) * 1e-9).replace(
                tzinfo=dt.timezone.utc
            )
            for j, g in enumerate(gates):
                gdlat, glong = fov[0][g, beam], fov[1][g, beam]
                angle = 90.0 - get_altitude_fast(gdlat, glong, d)
                dn_grid[i, j] = angle
        terminator = np.zeros_like(dn_grid)
        terminator[dn_grid > self.angle_th] = 1.0
        terminator[dn_grid <= self.angle_th] = 0.0
        if yscale == "srange":
            gates = frang + (rsep * gates)
        elif yscale == "virtual_height":
            mvh.standard_vhm(self.nGates * df.rsep.tolist()[0] + df.frang.tolist()[0])
        else:
            # TODO
            pass
        times, gates = np.meshgrid(times, gates)
        ax.pcolormesh(
            times.T,
            gates.T,
            terminator,
            lw=0.01,
            edgecolors="None",
            cmap="gray_r",
            vmax=2,
            vmin=0,
            shading="nearest",
            alpha=0.3,
        )
        return

    def _add_axis(self):
        self._num_subplots_created += 1
        ax = self.fig.add_subplot(self.num_subplots, 1, self._num_subplots_created)
        return ax

    def _add_colorbar(self, fig, ax, im, label=""):
        """
        Add a colorbar to the right of an axis.
        """
        cpos = [1.04, 0.1, 0.025, 0.8]
        cax = ax.inset_axes(cpos, transform=ax.transAxes)
        cb = fig.colorbar(im, ax=ax, cax=cax)
        cb.set_label(label)
        return

    def save(self, filepath):
        self.fig.savefig(filepath, bbox_inches="tight", facecolor=(1, 1, 1, 1))
        return

    def close(self):
        self.fig.clf()
        plt.close()
        return
