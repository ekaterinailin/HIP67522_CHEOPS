import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from astropy.io import fits
from scipy.optimize import curve_fit


from altaipony.flarelc import FlareLightCurve

from astropy import units as u
from astropy.modeling import models
from astropy.constants import sigma_sb

import batman


flux_label = r"Flux [e$^{-}$/s]"
time_label = "Time [BJD]"

def extract(data, stri):
    """Quick function to extract light curve columns from a fits file"""
    return data[stri].byteswap().newbyteorder()



def get_residual_image(file, index=664):
    IMG = f'../data/hip67522/CHEOPS-products-{file}/Outdata/00000/residuals_sa.fits'
    hdulist = fits.open(IMG)
    print(f"Residuals image file found for {file}:\n {IMG}\n")

    # get the image data
    image_data = hdulist[0].data


    # sum over the first axis
    image_data = image_data[index:index+20].sum(axis=0)

    # show the image
    plt.imshow(image_data, cmap="viridis", origin="lower", vmin=-600, vmax=6000)
    plt.colorbar(label=flux_label)

    plt.xlabel("x pixel number")
    plt.ylabel("y pixel number")

    plt.tight_layout()
    plt.savefig(f"../plots/{file}/random_residuals_sa.png")

def metafunc(offset2, transit):
    """Defines a polynomial function with a time offset and a known transit included.
    
    Parameters
    ----------
    offset2 : float
        Time offset. Use the last time stamp in light curve.
    transit : array
        Transit model. Use the batman model.

    Returns
    -------
    func : function
        Function that can be used to fit the light curve.
    
    """
    def func(x, a, b, c, d, e, f, offset):
        return (f * (x - offset2 + offset)**5 + 
                e * (x - offset2 + offset)**4 + 
                a * (x - offset2 + offset)**3 + 
                b * (x - offset2 + offset)**2 + 
                c * (x - offset2 + offset) + d + 
                transit)
    return func
    

if __name__ == '__main__':

    # GET THE IMAGE DATA -----------------------------------------------------------
    file = sys.argv[1]

    # file name
    IMG = f'../data/hip67522/CHEOPS-products-{file}/Outdata/00000/hip67522_CHEOPS-products-{file}_im.fits'

    # open the fits file
    hdulist = fits.open(IMG)
    print(f"Imagette file found for {file}:\n {IMG}\n")

    # get the image data
    image_data = hdulist[1].data


    # get LC data
    t, f, ferr, roll, dT, flag, bg, xc, yc = [extract(image_data, stri) for stri in ["BJD_TIME", "FLUX", "FLUXERR",
                                                                                    "ROLL", "thermFront_2", "FLAG",
                                                                                    "BG", "XC", "YC"]]

    # make sure the data is in fact 10s cadence
    assert np.diff(t).min() * 24 * 60 * 60 < 10.05, "Time series is not 10s cadence"

    # initial mask
    mask = (f < 2.96e6) & (f > 2.3e6) & (flag==0)
    print(f"Initial mask: {mask.sum()} data points")

    # apply the mask
    t, f, ferr, roll, dT, flag, bg, xc, yc = [arr[mask] for arr in [t, f, ferr, roll, dT, flag, bg, xc, yc]]

    # make a diagnostic plot of the residuals on the detector 
    get_residual_image(file, index=664)

    # PLOT THE INITIAL LIGHT CURVE -------------------------------------------------

    plt.figure(figsize=(10, 5))
    plt.plot(t, f, ".", markersize=1)

    plt.xlabel(time_label)
    plt.ylabel(flux_label)
    plt.title("Initial light curve, masking outliers")
    plt.savefig(f"../plots/{file}/flares/hip67522_initial_lc.png")

    # -----------------------------------------------------------------------------


    # DEFINE A TRANSIT MODEL USING BARBER ET AL. 2024 PARAMETERS -------------------

    # use batman to create a transit model
    params = batman.TransitParams()

    params.t0 = 1604.02344 + 2457000.             #time of inferior conjunction in BJD
    params.per = 6.9594738               #orbital period
    params.rp = 0.0668                      #planet radius (in units of stellar radii)
    params.a = 11.74                       #semi-major axis (in units of stellar radii)
    params.inc = 89.46                     #orbital inclination (in degrees)
    params.ecc = 0.053                      #eccentricity
    params.w = 199.1                       #longitude of periastron (in degrees)
    params.u = [0.22, 0.27]                #limb darkening coefficients [u1, u2]
    params.limb_dark = "quadratic"       #limb darkening model

    m = batman.TransitModel(params, t)    #initializes model
    transit = m.light_curve(params)          #calculates light curve

    transit = (transit - 1) * np.median(f) # scale to the median flux

    # -----------------------------------------------------------------------------

    # FIT A POLYNOMIAL MODEL -------------------------------------------------------

    # 5th degree polynomial with a time offset and a transit
    modelfunc = metafunc(t[-1], transit)

    # fit the model to the light curve
    popt, pcov = curve_fit(modelfunc, t, f, p0=[-1.45888787e+04, -1.41685433e+08, -1.03596058e+09,  1.00000000e+00,
            1.19292031e-02, -2.42900480e-09,  8.42088604e-01])

    # get the fitted model
    fitted = modelfunc(t, *popt)

    # PLOT THE FITTED MODEL -------------------------------------------------------

    plt.figure(figsize=(10, 5))

    # flux
    plt.plot(t, f, ".", markersize=2, color="red")
    # fitted model
    plt.plot(t, fitted, color="blue", lw=1)

    plt.xlabel(time_label)
    plt.ylabel(flux_label)
    plt.title("First polynomial fit to the light curve w/o flare")
    plt.savefig(f"../plots/{file}/flares/hip67522_polyfit_init.png")

    # -----------------------------------------------------------------------------

    # SUBTRACT THE FITTED MODEL  ---------------------------------------------------

    # median
    med = np.median(f)

    # subtract the fitted model
    f_sub = f - fitted + med

    # get a new median
    newmed = np.median(f_sub)


    # MASK OUTLIERS ----------------------------------------------------------------

    # mask out the outliers
    mask = (f_sub < newmed + 4 * np.std(f_sub)) & (f_sub > newmed - 4 * np.std(f_sub))

    plt.figure(figsize=(10, 5))
    plt.plot(t, f, ".", markersize=1)
    plt.plot(t[mask], f_sub[mask], ".", markersize=1)
    plt.plot(t[~mask], f_sub[~mask], ".", markersize=6, color="red")
    plt.axhline(med, color="red", lw=1)

    plt.xlabel(time_label)
    plt.ylabel(flux_label)
    plt.title("Subtracting the polynomial fit and masking outliers")
    plt.savefig(f"../plots/{file}/flares/hip67522_subtract_polyfit_init.png")

    # -----------------------------------------------------------------------------


    # UPDATE TRANSIT MODEL WITH SUBTRACTED LIGHT CURVE -----------------------------
    m = batman.TransitModel(params, t[mask])    #initializes model
    transit = m.light_curve(params)          #calculates light curve

    transit = (transit - 1) * np.median(f_sub[mask])


    # FIT A SECOND POLYNOMIAL MODEL ------------------------------------------------

    # define a new model function with the new transit model
    newmodelfunc = metafunc(t[mask][-1], transit)

    # fit the new model to the subtracted light curve
    popt, pcov = curve_fit(newmodelfunc, t[mask], f[mask], p0=popt)

    # get the new fitted model but use the full array
    newfitted = modelfunc(t, *popt)


    # subtract the new fitted model
    newf_sub = f - newfitted + newmed

    # PLOT THE NEW FITTED MODEL RESIDUALS WITH THE OLD FITTED MODEL  ----------------

    plt.figure(figsize=(10, 5))
    plt.plot(t, fitted-newfitted, color="blue", lw=1)
    plt.xlabel(time_label)
    plt.ylabel(flux_label)
    plt.title("Difference between first and second polynomial fit")
    plt.savefig(f"../plots/{file}/flares/hip67522_polyfit_diff.png")

    # --------------------------------------------------------------------------------

    # PLOT THE FINAL LIGHT CURVE WITH MODEL ------------------------------------------

    plt.figure(figsize=(10, 5))

    plt.plot(t, f, ".", markersize=1, color="grey")
    plt.plot(t, newfitted, ".", markersize=1, color="black")
    plt.xlabel(time_label)
    plt.ylabel(flux_label)
    plt.title("Second polynomial fit to the light curve w/o flare")
    plt.savefig(f"../plots/{file}/flares/hip67522_polyfit_final.png")

    # --------------------------------------------------------------------------------

    # PLOT THE FINAL QUIET LIGHT CURVE AGAINST ROLL ANGLE ----------------------------
    plt.figure(figsize=(10, 5))
    plt.plot(roll, newf_sub, ".", markersize=1)
    plt.xlabel("Roll")
    plt.ylabel(flux_label)
    plt.savefig(f"../plots/{file}/flares/hip67522_roll_flux.png")

    # --------------------------------------------------------------------------------

    # ROLL ANGLE CORRECTION ---------------------------------------------------------

    # approximate the flux at the roll values in the flare region with 
    # the flux at the closest roll value in the non-flare region

    f_sub_no_flare_approx = np.zeros_like(newf_sub)
    for i, r in enumerate(roll):
        
        idx = [np.argmin(np.abs(roll - r - delt)) for delt in np.linspace(-2, 2, 100)]
        
        f_sub_no_flare_approx[i] = np.median(newf_sub[idx])


    # DEFINE THE FINAL FLUX ---------------------------------------------------------

    # final flux 
    ff = newf_sub - f_sub_no_flare_approx + newmed


    # PLOT THE FINAL FLUX  ----------------------------------------------------------

    plt.figure(figsize=(10, 5))

    plt.plot(t, ff, ".", markersize=1, color="red", label="quiescent model")

    plt.xlabel(time_label)
    plt.ylabel(flux_label)
    plt.title("Final de-trendend ligh curve")
    plt.savefig(f"../plots/{file}/flares/hip67522_final_detrended_light_curve.png")

    # --------------------------------------------------------------------------------


    # WRITE THE FINAL LIGHT CURVE TO A CSV FILE ------------------------------------------

    df = pd.DataFrame({"time": t, "flux": ff, "flux_err": ferr, "roll": roll, "dT": dT, "flag": flag, "bg": bg, "xc": xc, "yc": yc})
    df.to_csv(f"../data/hip67522/CHEOPS-products-{file}/Outdata/00000/{file}_detrended_lc.csv")
