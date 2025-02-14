"""Module containing constans used in the app."""
import os

UNIT = 1e-6  # Lenght units used in the whole script are microns
PIXEL_SIZE_MICRONS = 1  # Size of pixel in microns. Used during gerber conversion
PLOT_STYLE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "antmicro.mplstyle")

# Via geometry is aproximated using n-sided right prism
VIA_POLYGON = 8

STACKUP_FORMAT_VERSION = "1.0"
CONFIG_FORMAT_VERSION = "1.1"
