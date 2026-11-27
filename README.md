# SCP-Light 1.0.7

SCP-Light is an early QGIS 4 and Qt 6 port based on the official Semi-Automatic Classification Plugin 7.10.11 release by Luca Congedo. It is an independent trial fork and is not an official SCP release.

## Install in QGIS 4

1. Open **Plugins → Manage and Install Plugins…**.
2. Choose **Install from ZIP**.
3. Select `SCP_Light_v1.0.7.zip` and install **SCP-Light**.
4. Enable it from the Installed plugins list if QGIS does not enable it automatically.

## Sentinel downloads through Copernicus Data Space

In **SCP → Download products → Login data**:

- Enter your Copernicus Data Space account username and password.
- Leave **Catalogue OData endpoint** at `https://catalogue.dataspace.copernicus.eu/odata/v1`.
- Do not paste the long Copernicus Browser sign-in URL into the endpoint field. That address is a temporary browser authentication redirect, not the catalogue API.

Product search uses the public CDSE OData catalogue. Downloading product files requires an account token; SCP-Light requests and keeps that token in memory for the current QGIS session. If the first token request indicates that two-factor authentication is needed, SCP-Light prompts for the current authentication code. The inherited **remember** option starts checked and can save credentials in QGIS settings; uncheck it before entering credentials if you do not want them saved.

This alpha adapts Sentinel-1, Sentinel-2, and Sentinel-3 search and download paths to CDSE. The connection and product paths still need a live check with a CDSE account and selected products. Landsat and the other inherited download workflows have not been changed as part of this CDSE update.

Version 0.2.1 skips the cloud-cover filter when the maximum is 100% and includes the catalogue's response text in the error message if a search is rejected. Version 0.2.2 clears SCP's temporary map overlays when the plugin unloads. Version 0.2.3 requests CDSE Assets and Attributes separately, and clears temporary overlays when the SCP dialog closes. Version 0.2.4 matches the Sentinel-2 preview layer name used by the download filter and reports when that filter skips all products. Version 0.2.5 downloads only selected rows in the product table (or all rows when none are selected), skips the legacy Sentinel-2 cloud-mask file when CDSE does not list it, and handles cancel without reporting a partial band as damaged. Version 0.2.6 catches OGR's exception when it tries to open a raster, allowing CRS lookup to fall back to GDAL for JP2 inputs during raster clipping. When **Only if preview in Layers** is checked, the product's preview raster must be loaded as a QGIS map layer; the preview panel alone is insufficient.

## Port notes

Versions 0.1.1–0.1.6 addressed Qt 6 and Python 3.14 compatibility issues encountered during startup. SCP-Light does not use Remotior Sensus. Some legacy tools may need more QGIS 4 fixes, and some optional workflows may require ESA SNAP.

## Source and license

The starting point was SCP 7.10.11, available from the [QGIS Plugin Repository](https://plugins.qgis.org/plugins/SemiAutomaticClassificationPlugin/version/7.10.11/). Original copyright belongs to Luca Congedo. This derivative remains under GNU GPL version 3; see `COPYING.txt`.
