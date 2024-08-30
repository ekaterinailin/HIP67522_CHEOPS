"""
UTF-8, Python 3

------------
HIP 67522
------------

Ekaterina Ilin, 2024, MIT License


This module contains helpful IO functions.
"""

import glob
import numpy as np

from astropy.io import fits

import lightkurve as lk

def get_tess_orbital_phases(period, split=0.1, by_sector = False):
    """Download the TESS light curves for HIP 67522 and calculate the observing 
    time in the first 10% and last 90% of the orbit, or any other split.  
    
    Parameters
    ----------
    period : float
        The orbital period of the planet in days.
    split : float
        The phase split of the light curve to calculate the observing time for.
        Default is 0.1.
    by_sector : bool
        If True, return the phases for each sector separately. Default is False.

    Returns
    -------
    tessphases : array
        The phases of the TESS light curves
    ttess01 : float
        The observing time in days in the first 10% of the light curve.
    ttess09 : float
        The observing time in days in the last 90% of the light curve.
    ttess : float
        The total observing time in days of the TESS light curves.
    """
    lcs = lk.search_lightcurvefile("HIP 67522", mission="TESS",author="SPOC", exptime=120)

    # predictions from Rizzuto et al. 2020 using the NASA prediction tool for simplicity for each Sector
    midpoints = [2458694.49725,2459425.24506,2460155.99288] 

    # get the light curves
    lcs = [lc.download() for lc in lcs]

    # get all phases for the TESS light curves
    tessphases = []
    for lc, midpoint in zip(lcs, midpoints):
        lc = lc[lc.quality < 1]    
        tessphases.append(((lc.time.value - midpoint) % period) / period)


    if by_sector:
    
        return tessphases
    
    else:

        tessphases = np.concatenate(tessphases)
        # get the observing time for first 10% and last 90% of the light curve
        ttess01 = len(tessphases[tessphases < split]) * 2. / 60. / 24.
        ttess09 = len(tessphases[tessphases > split]) * 2. / 60. / 24.

        ttess = ttess01 + ttess09
        return tessphases, ttess01, ttess09, ttess

def get_cheops_orbital_phases(period, midpoint, split=0.1):

    files = glob.glob('../data/hip67522/CHEOPS-products-*/Outdata/00000/hip67522_CHEOPS-products-*_im.fits')
    time = np.array([])
    flux = np.array([])
    cheopsphases = np.array([])


    for file in files:
        hdulist = fits.open(file)


        # get the image data
        image_data = hdulist[1].data

        t, f, ferr, roll = image_data["BJD_TIME"], image_data["FLUX"], image_data["FLUXERR"], image_data["ROLL"]

        # make sure the data is in fact 10s cadence
        assert np.diff(t).min() * 24 * 60 * 60 < 10.05, "Time series is not 10s cadence"

        # big endian to little endian
        t = t.byteswap().newbyteorder()
        f = f.byteswap().newbyteorder()
        ferr = ferr.byteswap().newbyteorder()
        roll = roll.byteswap().newbyteorder()

        time = np.concatenate([time, t])
        flux = np.concatenate([flux, f])
        cheopsphases = np.concatenate([cheopsphases, ((t - midpoint) % period) / period])

    tot_obs_time_d_cheops = len(time) * 10. / 60. / 60. / 24.
    tcheops01 = len(time[cheopsphases < split]) * 10. / 60. / 60. / 24.
    tcheops09 = len(time[cheopsphases > split]) * 10. / 60. / 60. / 24.

    return cheopsphases, tcheops01, tcheops09, tot_obs_time_d_cheops
