###############################################################################
import os
import numpy as np
import scipy.integrate as integrate
import scipy.signal as signal


###############################################################################
def smooth_gaussian(x, y, sigma):
    """
    Takes an array and applies Gaussian smoothing in units of the input
    x array.

    Sigma is the smoothing scale in whatever units x has.
    Reflective boundaries can be implemented.
    """
    # get the spacing:
    dx = (np.amax(x)-np.amin(x))/float(len(x)-1)
    # test for legality of sigma:
    if np.abs(6.*sigma) <= dx:
        raise ValueError('smoothing scale (sigma) is smaller than discretization grid')
    # get the grid:
    gx = np.arange(-6*sigma, 6*sigma, dx)
    # define the un-normalized kernel:
    kernel = np.exp(-0.5*(gx/sigma)**2)
    # normalize the kernel:
    kernel = kernel/integrate.simps(kernel, range(len(kernel)))
    # if the kernel is larger than the signal mirror the signal an appropriate number of times:
    if len(kernel) > len(y):
        num_rep = int(np.ceil(len(kernel)/len(y)))
        # make sure repetitions are even:
        if num_rep % 2 == 0:
            num_rep += 1
        _y = np.tile(y, num_rep)
    else:
        _y = y
    # perform the convolution:
    _temp = signal.fftconvolve(_y, kernel, mode="same")
    # get the central part if we have tiled:
    if len(kernel) > len(y):
        _temp = _temp[len(y)*(num_rep-1)//2:len(y)*(num_rep-1)//2+len(y)]
    #
    return _temp

###############################################################################
