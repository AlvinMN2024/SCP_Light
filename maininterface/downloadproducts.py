import numpy as np
# -*- coding: utf-8 -*-
'''
/**************************************************************************************************************************
 SemiAutomaticClassificationPlugin

 The Semi-Automatic Classification Plugin for QGIS allows for the supervised classification of remote sensing images, 
 providing tools for the download, the preprocessing and postprocessing of images.

							 -------------------
		begin				: 2012-12-29
		copyright		: (C) 2012-2021 by Luca Congedo
		email				: ing.congedoluca@gmail.com
**************************************************************************************************************************/
 
/**************************************************************************************************************************
 *
 * This file is part of Semi-Automatic Classification Plugin
 * 
 * Semi-Automatic Classification Plugin is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU General Public License as published by the Free Software Foundation, 
 * version 3 of the License.
 * 
 * Semi-Automatic Classification Plugin is distributed in the hope that it will be useful, 
 * but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or 
 * FITNESS FOR A PARTICULAR PURPOSE. 
 * See the GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License along with 
 * Semi-Automatic Classification Plugin. If not, see <http://www.gnu.org/licenses/>. 
 * 
**************************************************************************************************************************/

'''



cfg = __import__(str(__name__).split('.')[0] + '.core.config', fromlist=[''])

class DownloadProducts:

	def __init__(self):
		# check all bands
		self.checkAll = 'No'
		self.rbbrBndPol = cfg.qgisGuiSCP.QgsRubberBand(cfg.cnvs, cfg.qgisCoreSCP.QgsWkbTypes.LineGeometry)
		cfg.ui.dateEdit_to.setDate(cfg.QDateSCP.currentDate())
		cfg.ui.dateEdit_from.setDate(cfg.QDateSCP.currentDate().addDays(-365))
		cfg.ui.download_images_tableWidget.setSelectionMode(cfg.QtWidgetsSCP.QAbstractItemView.SelectionMode.ExtendedSelection)
		cfg.ui.download_images_tableWidget.setToolTip(cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Select one or more rows to download only those scenes. Clear the selection to download all scenes in the table.'))
		
	# add satellite list to combo

	# Copernicus Data Space Ecosystem (CDSE) OData helpers
	def _cdseCatalogueBase(self):
		default = 'https://catalogue.dataspace.copernicus.eu/odata/v1'
		service = cfg.ui.sentinel_service_lineEdit.text().strip().rstrip('/')
		if not service or 'scihub.copernicus.eu' in service.lower() or '/auth/realms/' in service.lower():
			service = default
			cfg.ui.sentinel_service_lineEdit.setText(service)
		if service.endswith('/Products'):
			service = service[:-len('/Products')]
		if not service.endswith('/odata/v1'):
			service += '/odata/v1'
		return service

	def _cdseProductsUrl(self):
		return 'https://download.dataspace.copernicus.eu/odata/v1/Products'

	def _cdseNodeUrl(self, product_id, *nodes):
		from urllib.parse import quote
		url = self._cdseProductsUrl() + '(' + str(product_id) + ')'
		for node in nodes:
			url += '/Nodes(' + quote(str(node), safe='') + ')'
		return url + '/$value'

	def _cdseNodesUrl(self, product_id, *nodes):
		from urllib.parse import quote
		url = self._cdseProductsUrl() + '(' + str(product_id) + ')'
		for node in nodes:
			url += '/Nodes(' + quote(str(node), safe='') + ')'
		return url + '/Nodes'

	def _cdseListNodes(self, product_id, *nodes):
		import json
		try:
			content = self._cdseFetch(self._cdseNodesUrl(product_id, *nodes), authenticated=False)
			if content == 'No':
				return []
			if isinstance(content, bytes):
				content = content.decode('utf-8')
			payload = json.loads(content)
			return payload.get('result', []) if isinstance(payload, dict) else []
		except Exception as err:
			cfg.utls.logCondition(str(__name__) + ' CDSE optional node listing failed: ' + str(err))
		return []

	def _downloadRowIndices(self, table):
		selection = table.selectionModel()
		selected = set()
		if selection is not None:
			selected.update(index.row() for index in selection.selectedRows())
			if not selected:
				selected.update(index.row() for index in table.selectedIndexes())
		if selected:
			return sorted(selected)
		return list(range(table.rowCount()))

	def _cdseMessage(self, message, title='Copernicus Data Space'):
		try:
			cfg.mx.msgBarWarning(title, message)
		except Exception:
			int(0)

	def _cdseToken(self, force=False):
		import time
		now = time.time()
		token = getattr(cfg, 'cdseAccessToken', '')
		if not force and token and now < getattr(cfg, 'cdseTokenExpiresAt', 0) - 45:
			return token
		username = cfg.ui.user_scihub_lineEdit.text().strip()
		password = cfg.ui.password_scihub_lineEdit.text()
		if not username or not password:
			self._cdseMessage('Enter your Copernicus Data Space username and password in the Sentinel login tab before downloading.')
			return None
		endpoint = 'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'
		refresh = getattr(cfg, 'cdseRefreshToken', '')
		if refresh and not force:
			try:
				response = cfg.requestsSCP.post(endpoint, data={'client_id': 'cdse-public', 'grant_type': 'refresh_token', 'refresh_token': refresh}, timeout=(15, 30))
				response.raise_for_status()
				payload = response.json()
			except Exception:
				payload = None
		else:
			payload = None
		if payload is None:
			try:
				response = cfg.requestsSCP.post(endpoint, data={'client_id': 'cdse-public', 'grant_type': 'password', 'username': username, 'password': password}, timeout=(15, 30))
				response.raise_for_status()
				payload = response.json()
			except Exception as err:
				if getattr(locals().get('response'), 'status_code', None) in (400, 401):
					try:
						totp, accepted = cfg.QtWidgetsSCP.QInputDialog.getText(None, 'Copernicus Data Space', 'If your account uses two-factor authentication, enter the current code:')
						if accepted and totp.strip():
							response = cfg.requestsSCP.post(endpoint, data={'client_id': 'cdse-public', 'grant_type': 'password', 'username': username, 'password': password, 'totp': totp.strip()}, timeout=(15, 30))
							response.raise_for_status()
							payload = response.json()
					except Exception:
						payload = None
				if payload and payload.get('access_token'):
					cfg.cdseAccessToken = payload['access_token']
					cfg.cdseRefreshToken = payload.get('refresh_token', refresh)
					cfg.cdseTokenExpiresAt = now + int(payload.get('expires_in', 300))
					return cfg.cdseAccessToken
				try:
					detail = response.json().get('error_description', response.json().get('error', str(err)))
				except Exception:
					detail = str(err)
				cfg.utls.logCondition(str(__name__) + ' CDSE authentication failed: ' + str(detail))
				self._cdseMessage('CDSE sign-in failed. Check your account username and password; do not paste the Browser login URL into the Service field.')
				return None
		if not payload or not payload.get('access_token'):
			self._cdseMessage('CDSE did not return an access token. Check your account credentials.')
			return None
		cfg.cdseAccessToken = payload['access_token']
		cfg.cdseRefreshToken = payload.get('refresh_token', refresh)
		cfg.cdseTokenExpiresAt = now + int(payload.get('expires_in', 300))
		return cfg.cdseAccessToken

	def _cdseFetch(self, url, authenticated=False, output=None, progress=None):
		from urllib.parse import urljoin, urlparse
		for auth_attempt in range(2):
			token = self._cdseToken(force=(auth_attempt > 0)) if authenticated else None
			if authenticated and not token:
				return 'No'
			current_url = url
			response = None
			for redirect_count in range(6):
				host = (urlparse(current_url).hostname or '').lower()
				trusted_cdse = host == 'dataspace.copernicus.eu' or host.endswith('.dataspace.copernicus.eu')
				headers = {'Authorization': 'Bearer ' + token} if authenticated and trusted_cdse else {}
				response = cfg.requestsSCP.get(current_url, headers=headers, stream=(output is not None), allow_redirects=False, timeout=(20, 180))
				if response.is_redirect or response.is_permanent_redirect:
					location = response.headers.get('Location')
					response.close()
					if not location:
						raise RuntimeError('CDSE returned a redirect without a Location header')
					current_url = urljoin(current_url, location)
					continue
				break
			else:
				raise RuntimeError('Too many CDSE download redirects')
			if response.status_code == 401 and authenticated and auth_attempt == 0:
				response.close()
				continue
			response.raise_for_status()
			if output is None:
				content = response.content
				response.close()
				return content
			total = int(response.headers.get('Content-Length', 0) or 0)
			written = 0
			try:
				with open(output, 'wb') as target:
					for block in response.iter_content(chunk_size=1024 * 1024):
						if not block:
							continue
						if cfg.actionCheck == 'No':
							raise RuntimeError('Download cancelled')
						target.write(block)
						written += len(block)
						if progress is not None:
							if total:
								label = '(' + str(round(written / 1048576, 2)) + '/' + str(round(total / 1048576, 2)) + ' MB)'
							else:
								label = '(' + str(round(written / 1048576, 2)) + ' MB)'
							cfg.uiUtls.updateBar(progress, label + ' ' + url, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Downloading'))
							cfg.QtWidgetsSCP.QApplication.instance().processEvents()
				response.close()
				return 'Yes'
			except Exception:
				response.close()
				try:
					cfg.osSCP.remove(output)
				except Exception:
					int(0)
				raise
		return 'No'


	def _cdseDownloadFile(self, url, output, progress=None, optional=False):
		try:
			result = self._cdseFetch(url, authenticated=True, output=output, progress=progress)
			return result
		except Exception as err:
			if optional and getattr(getattr(err, 'response', None), 'status_code', None) == 404:
				cfg.utls.logCondition(str(__name__) + ' optional CDSE asset is not available: ' + str(url))
				return 'No'
			if str(err) == 'Download cancelled' or cfg.actionCheck != 'Yes':
				cfg.cdseDownloadCancelled = True
				return 'No'
			cfg.utls.logCondition(str(__name__) + ' CDSE file download failed: ' + str(err))
			self._cdseMessage('CDSE download failed: ' + str(err))
			return 'No'

	def _cdseSearch(self, collection, satellite, mission, maxCloudCover=100):
		import datetime
		base = self._cdseCatalogueBase()
		from_date = cfg.ui.dateEdit_from.date().toPyDate()
		to_date = cfg.ui.dateEdit_to.date().toPyDate() + datetime.timedelta(days=1)
		filters = ["Collection/Name eq '" + collection + "'", 'ContentDate/Start ge ' + from_date.strftime('%Y-%m-%dT00:00:00.000Z'), 'ContentDate/Start lt ' + to_date.strftime('%Y-%m-%dT00:00:00.000Z')]
		if mission == 'SENTINEL-1':
			filters.append("contains(Name,'GRD')")
		elif mission == 'SENTINEL-3':
			filters.append("contains(Name,'OL_1_EFR')")
		elif mission == 'SENTINEL-2' and int(maxCloudCover) < 100:
			filters.append("Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value le " + str(int(maxCloudCover)) + '.00)')
		try:
			x1 = float(cfg.ui.UX_lineEdit_3.text())
			y1 = float(cfg.ui.UY_lineEdit_3.text())
			x2 = float(cfg.ui.LX_lineEdit_3.text())
			y2 = float(cfg.ui.LY_lineEdit_3.text())
			min_x, max_x = min(x1, x2), max(x1, x2)
			min_y, max_y = min(y1, y2), max(y1, y2)
			polygon = 'POLYGON((' + str(min_x) + ' ' + str(min_y) + ',' + str(max_x) + ' ' + str(min_y) + ',' + str(max_x) + ' ' + str(max_y) + ',' + str(min_x) + ' ' + str(max_y) + ',' + str(min_x) + ' ' + str(min_y) + '))'
			filters.append("OData.CSC.Intersects(area=geography'SRID=4326;" + polygon + "')")
		except Exception:
			self._cdseMessage('Enter valid longitude and latitude bounds before searching.')
			return 'No'
		text_filters = [x.strip().lower().replace('*', '') for x in cfg.ui.imageID_lineEdit.text().replace(';', ',').split(',') if x.strip()]
		limit = max(1, min(int(cfg.ui.result_number_spinBox_2.value()), 500))
		def fetch_expanded(expand):
			params = {'$filter': ' and '.join(filters), '$orderby': 'ContentDate/Start desc', '$top': str(limit), '$expand': expand}
			found = []
			url = base + '/Products'
			while url and len(found) < limit:
				response = cfg.requestsSCP.get(url, params=params if url.endswith('/Products') else None, timeout=(15, 60))
				response.raise_for_status()
				payload = response.json()
				found.extend(payload.get('value', []))
				url = payload.get('@odata.nextLink')
				params = None
			return found
		try:
			products = fetch_expanded('Assets')
		except Exception as err:
			response = getattr(err, 'response', None)
			detail = str(getattr(response, 'text', '')).strip()[:500] if response is not None else ''
			message = 'Catalogue search failed: ' + (detail if detail else str(err))
			cfg.utls.logCondition(str(__name__) + ' ' + message)
			self._cdseMessage(message)
			return 'No'
		if mission in ('SENTINEL-1', 'SENTINEL-2'):
			try:
				attributes = {str(product.get('Id')): product.get('Attributes', []) for product in fetch_expanded('Attributes')}
				for product in products:
					if str(product.get('Id')) in attributes:
						product['Attributes'] = attributes[str(product.get('Id'))]
			except Exception as err:
				cfg.utls.logCondition(str(__name__) + ' CDSE product attributes were not returned: ' + str(err))
		if text_filters:
			products = [p for p in products if any(term in p.get('Name', '').lower() for term in text_filters)]
		return products

	def _cdseProductAttributes(self, product):
		attributes = {}
		for item in product.get('Attributes', []) or []:
			name = item.get('Name')
			value = item.get('Value')
			if value is None:
				for key, nested in item.items():
					if key.endswith('Attribute') and isinstance(nested, dict):
						value = nested.get('Value')
			if name:
				attributes[str(name).lower()] = value
		return attributes

	def _cdseBounds(self, geometry):
		values = []
		def visit(node):
			if isinstance(node, (list, tuple)):
				if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
					values.append((float(node[0]), float(node[1])))
				else:
					for child in node:
						visit(child)
		if isinstance(geometry, dict):
			visit(geometry.get('coordinates'))
		if not values:
			return None
		return min(y for x, y in values), min(x for x, y in values), max(y for x, y in values), max(x for x, y in values)

	def _cdseQuicklook(self, product, base):
		for asset in product.get('Assets', []) or []:
			name = str(asset.get('Name', '')).lower()
			type_name = str(asset.get('Type', '')).lower()
			if 'quicklook' in name or 'quicklook' in type_name or 'thumbnail' in name:
				asset_id = asset.get('Id')
				if asset_id:
					return base + '/Assets(' + str(asset_id) + ')/$value'
				return asset.get('DownloadLink', '')
		return ''

	def _cdsePopulateResults(self, mission, collection):
		max_cloud = int(cfg.ui.cloud_cover_spinBox.value())
		products = self._cdseSearch(collection, cfg.ui.landsat_satellite_combo.currentText(), mission, max_cloud)
		if products == 'No':
			cfg.uiUtls.removeProgressBar()
			return 'No'
		table = cfg.ui.download_images_tableWidget
		table.setSortingEnabled(False)
		base = self._cdseCatalogueBase()
		for product in products:
			name = str(product.get('Name', '')).removesuffix('.SAFE').removesuffix('.SEN3').removesuffix('.zip')
			product_id = str(product.get('Id', ''))
			content_date = product.get('ContentDate') or {}
			acquisition = str(content_date.get('Start', ''))
			if not name or not product_id or not acquisition:
				continue
			attributes = self._cdseProductAttributes(product)
			cloud = attributes.get('cloudcover', 0) or 0
			bounds = self._cdseBounds(product.get('GeoFootprint'))
			if bounds is None:
				min_lat = min_lon = max_lat = max_lon = 0.0
			else:
				min_lat, min_lon, max_lat, max_lon = bounds
			try:
				size = str(round(float(product.get('ContentLength', 0)) / 1048576, 1)) + ' MB'
			except Exception:
				size = ''
			quicklook = self._cdseQuicklook(product, base)
			row = table.rowCount()
			table.setRowCount(row + 1)
			cells = [''] * 14
			cells[0] = cfg.ui.landsat_satellite_combo.currentText()
			cells[1] = name
			cells[2] = acquisition
			cells[3] = str(cloud)
			cells[6] = str(min_lat)
			cells[7] = str(min_lon)
			cells[8] = str(max_lat)
			cells[9] = str(max_lon)
			cells[10] = size
			cells[11] = quicklook
			cells[12] = product_id
			cells[13] = name
			if mission == 'SENTINEL-2':
				parts = name.split('_')
				level = 'L2A' if 'MSIL2A' in name else 'L1C'
				tile = next((part for part in parts if len(part) == 6 and part.startswith('T')), '')
				cells[1] = level + '_' + tile if tile else name
				cells[4] = tile
			elif mission == 'SENTINEL-1':
				cells[3] = ''
				cells[4] = str(attributes.get('orbitdirection', ''))
				cells[5] = str(attributes.get('relativeorbitnumber', ''))
			elif mission == 'SENTINEL-3':
				cells[3] = '0'
				cells[4] = name[64:81] if len(name) >= 81 else ''
			for col, value in enumerate(cells):
				cfg.utls.addTableItem(table, value, row, col)
		table.setSortingEnabled(True)
		cfg.uiUtls.removeProgressBar()
		self.clearCanvasPoly()
		return 'Yes'

	def _cdseGranuleName(self, product_id, product_name):
		cache = getattr(cfg, 'cdseGranules', {})
		if product_id in cache:
			return cache[product_id]
		level = 'L2A' if 'MSIL2A' in product_name else 'L1C'
		metadata_name = 'MTD_MSIL2A.xml' if level == 'L2A' else 'MTD_MSIL1C.xml'
		url = self._cdseNodeUrl(product_id, product_name + '.SAFE', metadata_name)
		try:
			content = self._cdseFetch(url, authenticated=True)
		except Exception as err:
			cfg.utls.logCondition(str(__name__) + ' CDSE Sentinel-2 metadata request failed: ' + str(err))
			self._cdseMessage('Could not retrieve Sentinel-2 product metadata from CDSE.')
			return None
		if content == 'No':
			return None
		try:
			document = cfg.minidomSCP.parseString(content)
		except Exception as err:
			cfg.utls.logCondition(str(__name__) + ' CDSE Sentinel-2 metadata parse failed: ' + str(err))
			self._cdseMessage('The Sentinel-2 metadata returned by CDSE could not be read.')
			return None
		tags = ['IMAGE_FILE_2A', 'IMAGE_FILE'] if level == 'L2A' else ['IMAGE_FILE']
		for tag in tags:
			for item in document.getElementsByTagName(tag):
				if item.firstChild:
					parts = item.firstChild.data.strip().split('/')
					if 'GRANULE' in parts:
						granule = parts[parts.index('GRANULE') + 1]
						cache[product_id] = granule
						cfg.cdseGranules = cache
						return granule
		self._cdseMessage('Could not read the Sentinel-2 granule name from product metadata.')
		return None

	def addSatelliteToCombo(self, satelliteList):
		for i in satelliteList:
			cfg.ui.landsat_satellite_combo.addItem(i)
		# logger
		cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), " satellites added")
			
	# user
	def rememberUser(self):
		if cfg.ui.remember_user_checkBox_2.isChecked():
			user = cfg.ui.user_usgs_lineEdit.text()
			pswd = cfg.utls.encryptPassword(cfg.ui.password_usgs_lineEdit.text())
			cfg.utls.setQGISRegSetting(cfg.regUSGSUser, user)
			cfg.utls.setQGISRegSetting(cfg.regUSGSPass, pswd)
			
	def rememberUserCheckbox(self):
		if cfg.ui.remember_user_checkBox_2.isChecked():
			self.rememberUser()
		else:
			cfg.utls.setQGISRegSetting(cfg.regUSGSUser, "")
			cfg.utls.setQGISRegSetting(cfg.regUSGSPass, "")
		
	# add rubber band
	def addRubberBandPolygon(self, pointUL, pointLR):
		try:
			self.clearCanvasPoly()
		except:
			int(0)
		pointF = cfg.QtCoreSCP.QPointF()
		polF = cfg.QtGuiSCP.QPolygonF()
		pointF.setX(pointUL.x())
		pointF.setY(pointUL.y())
		polF.append(pointF)
		pointF.setX(pointLR.x())
		pointF.setY(pointUL.y())
		polF.append(pointF)
		pointF.setX(pointLR.x())
		pointF.setY(pointLR.y())
		polF.append(pointF)
		pointF.setX(pointUL.x())
		pointF.setY(pointLR.y())
		polF.append(pointF)
		pointF.setX(pointUL.x())
		pointF.setY(pointUL.y())
		polF.append(pointF)
		g = cfg.qgisCoreSCP.QgsGeometry().fromQPolygonF(polF)
		self.rbbrBndPol.setToGeometry(g, None)
		clr = cfg.QtGuiSCP.QColor('#ff0000')
		clr.setAlpha(50)
		self.rbbrBndPol.setFillColor(clr)
		self.rbbrBndPol.setWidth(3)
		
	# clear canvas
	def clearCanvasPoly(self):
		self.rbbrBndPol.reset()
		self.rbbrBndPol.hide()
		cfg.cnvs.refresh()

	# Activate pointer
	def pointerActive(self):
		# connect to click
		t = cfg.dwnlPrdPnt
		cfg.cnvs.setMapTool(t)
		px = cfg.QtGuiSCP.QPixmap(':/pointer/icons/pointer/ROI_pointer.svg')
		c = cfg.QtGuiSCP.QCursor(px)
		cfg.cnvs.setCursor(c)
		# logger
		cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), 'pointer active: Landsat')
		
	# left click pointer
	def pointerLeftClick(self, point):
		self.pointerClickUL(point)
			
	# right click pointer
	def pointerRightClick(self, point):
		self.pointerClickLR(point)
			
	# show area
	def showArea(self):
		pCrs = cfg.utls.getQGISCrs()
		# WGS84 EPSG 4326
		iCrs = cfg.qgisCoreSCP.QgsCoordinateReferenceSystem()
		iCrs.createFromProj4('+proj=longlat +datum=WGS84 +no_defs')
		try:
			UL = cfg.qgisCoreSCP.QgsPointXY(float(cfg.ui.UX_lineEdit_3.text()), float(cfg.ui.UY_lineEdit_3.text()))
			UL1 = cfg.utls.projectPointCoordinates(UL, iCrs, pCrs)
			LR = cfg.qgisCoreSCP.QgsPointXY(float(cfg.ui.LX_lineEdit_3.text()), float(cfg.ui.LY_lineEdit_3.text()))
			LR1 = cfg.utls.projectPointCoordinates(LR, iCrs, pCrs)
			self.addRubberBandPolygon(UL1, LR1)
		except:
			int(0)
			
	# set coordinates
	def pointerClickLR(self, point):
		pCrs = cfg.utls.getQGISCrs()
		# WGS84 EPSG 4326
		iCrs = cfg.qgisCoreSCP.QgsCoordinateReferenceSystem('EPSG:4326')
		point1 = cfg.utls.projectPointCoordinates(point, pCrs, iCrs)
		if point1 is not False:
			try:
				if float(cfg.ui.UX_lineEdit_3.text()) < point1.x():
					cfg.ui.LX_lineEdit_3.setText(str(point1.x()))
				else:
					cfg.ui.LX_lineEdit_3.setText(str(cfg.ui.UX_lineEdit_3.text()))
					cfg.ui.UX_lineEdit_3.setText(str(point1.x()))
				if float(cfg.ui.UY_lineEdit_3.text()) > point1.y():
					cfg.ui.LY_lineEdit_3.setText(str(point1.y()))
				else:
					cfg.ui.LY_lineEdit_3.setText(str(cfg.ui.UY_lineEdit_3.text()))
					cfg.ui.UY_lineEdit_3.setText(str(point1.y()))
			except:
				cfg.ui.LX_lineEdit_3.setText(str(point1.x()))
				cfg.ui.LY_lineEdit_3.setText(str(point1.y()))
			self.showArea()
		
	# set coordinates
	def pointerClickUL(self, point):
		pCrs = cfg.utls.getQGISCrs()
		# WGS84 EPSG 4326
		iCrs = cfg.qgisCoreSCP.QgsCoordinateReferenceSystem('EPSG:4326')
		point1 = cfg.utls.projectPointCoordinates(point, pCrs, iCrs)
		if point1 is not False:
			try:
				if float(cfg.ui.LX_lineEdit_3.text()) > point1.x():
					cfg.ui.UX_lineEdit_3.setText(str(point1.x()))
				else:
					cfg.ui.UX_lineEdit_3.setText(str(cfg.ui.LX_lineEdit_3.text()))
					cfg.ui.LX_lineEdit_3.setText(str(point1.x()))
				if float(cfg.ui.LY_lineEdit_3.text()) < point1.y():
					cfg.ui.UY_lineEdit_3.setText(str(point1.y()))
				else:
					cfg.ui.UY_lineEdit_3.setText(str(cfg.ui.LY_lineEdit_3.text()))
					cfg.ui.LY_lineEdit_3.setText(str(point1.y()))
			except:
				cfg.ui.UX_lineEdit_3.setText(str(point1.x()))
				cfg.ui.UY_lineEdit_3.setText(str(point1.y()))
			self.showArea()
		
	# save download table
	def saveDownloadTable(self, file = None):
		downloadTable = cfg.utls.tableToText(cfg.ui.download_images_tableWidget)
		if file is None:
			cfg.utls.writeProjectVariable('SCP_DownloadTable', str(downloadTable))
		else:
			try:
				l = open(file, 'w')
			except:
				int(0)
			try:
				l.write(downloadTable)
				l.close()
			except Exception as err:
				# logger
				cfg.utls.logCondition(str(__name__) + '-' + (cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))	
		
	# open download table
	def openDownloadTable(self, file = None):
		if file is None:
			text = cfg.utls.readProjectVariable('SCP_DownloadTable', '')
		else:
			f = open(file, 'r')
			text = f.read()
		if len(text) > 0:
			downloadTable = cfg.utls.textToTable(cfg.ui.download_images_tableWidget, text)
			if downloadTable == 'No':
				cfg.utls.clearTable(cfg.ui.download_images_tableWidget)
				cfg.mx.msgErr19()
	
	# import table file
	def importTableText(self):
		file = cfg.utls.getOpenFileName(None , cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Select a text file of product table'), '', 'txt (*.txt)')
		if len(file) > 0:
			self.openDownloadTable(file)
		
	# find images
	def exportTableText(self):
		tW = cfg.ui.download_images_tableWidget
		c = tW.rowCount()
		if c > 0:
			d = cfg.utls.getSaveFileName(None , cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Export table to file'), '', '*.txt', 'txt')
			if d is not False:
				if d.lower().endswith('.txt'):
					pass
				else:
					d = d + '.txt'
				self.saveDownloadTable(d)
		
	# find images
	def findImages(self):
		self.downloadMetadata()
				
	# download image metadata
	def downloadMetadata(self):
		sat = cfg.ui.landsat_satellite_combo.currentText()
		if sat in cfg.satSentinelList:
			self.queryDatabaseSentinel2()
		elif sat in cfg.satSentinel3List:
			self.queryDatabaseSentinel3()
		elif sat in cfg.satSentinel1List:
			self.queryDatabaseSentinel1()
		elif sat in cfg.satLandsatList:
			self.downloadMetadataLandsat()
		elif sat in cfg.satASTERtList:
			self.downloadMetadataASTER()
		elif sat in cfg.satMODIStList:
			self.downloadMetadataMODIS()
		elif sat in cfg.satGOEStList:
			self.downloadMetadataGOES()
			
	# download image metadata from NASA CMR Search https://cmr.earthdata.nasa.gov/search/site/search_api_docs.html
	def downloadMetadataLandsat(self):
		listImgID = []
		QdateFrom = cfg.ui.dateEdit_from.date()
		QdateTo = cfg.ui.dateEdit_to.date()
		dateFrom = QdateFrom.toPyDate().strftime('%Y-%m-%d') 
		dateTo = QdateTo.toPyDate().strftime('%Y-%m-%d') 
		maxCloudCover = int(cfg.ui.cloud_cover_spinBox.value())
		resultNum = int(cfg.ui.result_number_spinBox_2.value())
		sat = cfg.ui.landsat_satellite_combo.currentText()
		if sat == cfg.usgsLandsat8:
			NASAcollection = cfg.NASALandsat8Collection
			USGScollection = cfg.usgsLandsat8Collection
		elif sat == cfg.usgsLandsat7:
			NASAcollection = cfg.NASALandsat7Collection
			USGScollection = cfg.usgsLandsat7Collection
		elif sat == cfg.usgsLandsat45:
			NASAcollection = cfg.NASALandsat45Collection
			USGScollection = cfg.usgsLandsat45Collection
		elif sat == cfg.usgsLandsat15:
			NASAcollection = cfg.NASALandsat15Collection
			USGScollection = cfg.usgsLandsat15Collection
		imageFindList = []
		if len(cfg.ui.imageID_lineEdit.text()) > 0:
			imgIDLine = cfg.ui.imageID_lineEdit.text()
			imgIDLineSplit = str(imgIDLine).replace(' ', '').split(';')
			if len(imgIDLineSplit) == 1:
				imgIDLineSplit = str(imgIDLine).replace(' ', '').split(',')
			for m in imgIDLineSplit:
				imageFindList.append(m.lower())
		try:
			rubbRect = cfg.qgisCoreSCP.QgsRectangle(float(cfg.ui.UX_lineEdit_3.text()), float(cfg.ui.UY_lineEdit_3.text()), float(cfg.ui.LX_lineEdit_3.text()), float(cfg.ui.LY_lineEdit_3.text()))
		except Exception as err:
			# logger
			cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
			cfg.mx.msg23()
			return 'No'
		try:
			cfg.uiUtls.addProgressBar()
			cfg.QtWidgetsSCP.QApplication.instance().processEvents()
			tW = cfg.ui.download_images_tableWidget
			tW.setSortingEnabled(False)
			cfg.uiUtls.updateBar(30, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching ...'))
			# cloud cover returns 0 results
			# without cloud cover
			searchUrl = 'https://cmr.earthdata.nasa.gov/search/granules.echo10?bounding_box=' + cfg.ui.UX_lineEdit_3.text() + '%2C' + cfg.ui.LY_lineEdit_3.text() + '%2C' + cfg.ui.LX_lineEdit_3.text() + '%2C' + cfg.ui.UY_lineEdit_3.text() + '&echo_collection_id=' + NASAcollection + '&temporal=' + dateFrom + '%2C' + dateTo + 'T23%3A59%3A59.000Z&sort_key%5B%5D=-start_date&page_size=' + str(resultNum) + '&pretty=true'
			# connect and search
			searchResult = cfg.utls.NASASearch(searchUrl)
			xmlFile = searchResult.read()
			imgIDList = []
			doc = cfg.minidomSCP.parseString(xmlFile)
			entries = doc.getElementsByTagName('Granule')
			pages = len(entries)
			page = 0
			cloudCover = 0
			for entry in entries:
				page = page + 1
				cfg.uiUtls.updateBar(30 + int(page * 70 / pages), cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching ...'))
				gId = entry.getElementsByTagName('GranuleUR')[0]
				imgID = gId.firstChild.data
				lId = entry.getElementsByTagName('LocalVersionId')[0]
				lImgId = lId.firstChild.data
				if imgID not in imgIDList:
					imgIDList.append(imgID)
					imgDispID = imgID
					on = entry.getElementsByTagName('ProviderBrowseUrl')
					url = on[0].getElementsByTagName('URL')[0]
					imgPreview = url.firstChild.data
					if 'https://ims.cr.usgs.gov/browse/' not in imgPreview and 'https://earthexplorer.usgs.gov' not in imgPreview:
						imgPreview = 'https://ims.cr.usgs.gov/browse/' + imgPreview
					StartCoordinate1 = entry.getElementsByTagName('StartCoordinate1')[0]
					path = StartCoordinate1.firstChild.data
					StartCoordinate2 = entry.getElementsByTagName('StartCoordinate2')[0]
					row = StartCoordinate2.firstChild.data
					dt = entry.getElementsByTagName('BeginningDateTime')[0]
					imgDate = dt.firstChild.data
					imgDate = cfg.datetimeSCP.datetime.strptime(imgDate[0:19], '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
					try:
						cc = entry.getElementsByTagName('QAPercentCloudCover')[0]
						cloudCover = cc.firstChild.data
					except:
						addAttrs = entry.getElementsByTagName('AdditionalAttribute')
						for addAttr in addAttrs:
							addAttrNames = addAttr.getElementsByTagName('Name')
							for addAttrName in addAttrNames:
								addAttrNameC = addAttrName.firstChild.data
								if addAttrNameC == 'LandCloudCover':
									addAttrValues = addAttr.getElementsByTagName('Values')[0]
									addAttrVal = addAttrValues.getElementsByTagName('Value')[0]
									cloudCover = addAttrVal.firstChild.data
					PointLatitude = entry.getElementsByTagName('PointLatitude')
					PointLongitude = entry.getElementsByTagName('PointLongitude')
					lat = []
					for latit in PointLatitude:
						lat.append(float(latit.firstChild.data))
					lon = []
					for longi in PointLongitude:
						lon.append(float(longi.firstChild.data))
					listImgID.append([imgID, imgDate, cloudCover, path, row, lon, lat, imgPreview, lImgId])
			c = tW.rowCount()
			for imID in listImgID:
				if len(imageFindList) > 0:
					for iF in imageFindList:
						if iF in imID[0].lower():
							imgCheck = 'Yes'
							break
						else:
							imgCheck = 'No'
				# workaround for cloud cover filter
				elif maxCloudCover < float(imID[2]):
					imgCheck = 'No'
				else:
					imgCheck = 'Yes'
				if imgCheck == 'Yes':
					c = tW.rowCount()
					# add list items to table
					tW.setRowCount(c + 1)
					cfg.utls.addTableItem(tW, sat, c, 0)
					cfg.utls.addTableItem(tW, imID[0], c, 1)
					cfg.utls.addTableItem(tW, str(imID[1]), c, 2)
					cfg.utls.addTableItem(tW, int(round(float(imID[2]))), c, 3)
					cfg.utls.addTableItem(tW, imID[3], c, 4)
					cfg.utls.addTableItem(tW, imID[4], c, 5)
					min_lon = min(imID[5])
					max_lon = max(imID[5])
					min_lat = min(imID[6])
					max_lat = max(imID[6])
					cfg.utls.addTableItem(tW, float(min_lat), c, 6)
					cfg.utls.addTableItem(tW, float(min_lon), c, 7)
					cfg.utls.addTableItem(tW, float(max_lat), c, 8)
					cfg.utls.addTableItem(tW,float(max_lon), c, 9)
					cfg.utls.addTableItem(tW, USGScollection, c, 10)
					cfg.utls.addTableItem(tW, imID[7], c, 11)
					cfg.utls.addTableItem(tW, NASAcollection, c, 12)
					cfg.utls.addTableItem(tW, imID[8], c, 13)
			tW.setSortingEnabled(True)		
			cfg.uiUtls.removeProgressBar()
			self.clearCanvasPoly()
			# logger
			cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' Landsat images')
			c = tW.rowCount()
			if c == 0:
				cfg.mx.msg21()
		except Exception as err:
			cfg.mx.msgErr39()
			cfg.uiUtls.removeProgressBar()
			# logger
			cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
	
	# Add OpenStreetMap to the map as described in https://wiki.openstreetmap.org/wiki/QGIS (© OpenStreetMap contributors. The cartography is licensed as CC BY-SA)
	def displayOSM(self):
		cfg.utls.addRasterLayer(cfg.plgnDir + '/docs/openstreetmap_wms.xml', 'OpenStreetMap')
		# logger
		cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' OSM added')
	
	# display images
	def displayImages(self):
		tW = cfg.ui.download_images_tableWidget
		ids = []
		for i in tW.selectedIndexes():
			ids.append(i.row())
		id = set(ids)
		if len(id) > 0:
			progressStep = 100 / len(id)
			cfg.uiUtls.addProgressBar()
			# disable map canvas render for speed
			cfg.cnvs.setRenderFlag(False)
			progress = 0
			for i in id:
				sat = str(tW.item(i, 0).text())
				if sat in cfg.satSentinelList:
					self.displayGranulesSentinel2(i, progress)
				elif sat in cfg.satSentinel3List:
					self.displayGranulesSentinel3(i, progress)
				elif sat in cfg.satSentinel1List:
					self.displayGranulesSentinel1(i, progress)
				elif sat in cfg.satLandsatList or sat in cfg.satASTERtList or sat in cfg.satMODIStList:
					self.displayImagesNASA(i, progress)
				progress = progress + progressStep
				cfg.uiUtls.updateBar(progress, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Downloading ...'))
			cfg.uiUtls.removeProgressBar()
			cfg.cnvs.setRenderFlag(True)
			cfg.cnvs.refresh()
			
	# display images
	def displayImagesNASA(self, row, progress, preview = 'No'):
		i = row
		tW = cfg.ui.download_images_tableWidget
		sat = str(tW.item(i, 0).text())
		imgID = str(tW.item(i, 1).text())
		path = str(tW.item(i, 4).text())
		row = str(tW.item(i, 5).text())
		min_lat = str(tW.item(i, 6).text())
		min_lon = str(tW.item(i, 7).text())
		max_lat = str(tW.item(i, 8).text())
		max_lon = str(tW.item(i, 9).text())
		jpg = str(tW.item(i, 11).text())
		# image preview
		imOut = cfg.tmpDir + '//' + imgID + '_thumb.jpg'
		if preview == 'Yes' and cfg.osSCP.path.isfile(imOut):
			self.previewInLabel(imOut)
			return imOut
		if cfg.osSCP.path.isfile(cfg.tmpDir + '//' + imgID + '.vrt'):
			l = cfg.utls.selectLayerbyName(imgID)
			if l is not None:		
				cfg.utls.setLayerVisible(l, True)
				cfg.utls.moveLayerTop(l)
			else:
				r =cfg.utls.addRasterLayer(cfg.tmpDir + '//' + imgID + '.vrt')
				cfg.utls.setRasterColorComposite(r, 1, 2, 3)
		else:
			self.downloadThumbnail(imgID, path, row, min_lat, min_lon, max_lat, max_lon, jpg, sat, progress, preview)
			if cfg.osSCP.path.isfile(cfg.tmpDir + '//' + imgID + '.vrt'):
				r =cfg.utls.addRasterLayer(cfg.tmpDir + '//' + imgID + '.vrt')
				cfg.utls.setRasterColorComposite(r, 1, 2, 3)
		# logger
		cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' thumbnails displayed')
						
	# display image in label
	def previewInLabel(self, imagePath):
		tmpImage = cfg.reSCP.sub(r'\.jp2$', '.png', str(imagePath)) 
		if imagePath.endswith('.jp2') and not cfg.osSCP.path.isfile(tmpImage):
			cfg.utls.getGDALForMac()
			# georeference thumbnail
			a = cfg.gdalPath + 'gdal_translate ' + imagePath + ' ' + tmpImage + ' -of PNG'
			if cfg.sysSCPNm != 'Windows':
				a = cfg.shlexSCP.split(a)
			try:
				if cfg.sysSCPNm == 'Windows':
					startupinfo = cfg.subprocessSCP.STARTUPINFO()
					startupinfo.dwFlags = cfg.subprocessSCP.STARTF_USESHOWWINDOW
					startupinfo.wShowWindow = cfg.subprocessSCP.SW_HIDE
					sP = cfg.subprocessSCP.Popen(a, shell=False, startupinfo = startupinfo, stdin = cfg.subprocessSCP.DEVNULL)
				else:
					sP = cfg.subprocessSCP.Popen(a, shell=False)
				sP.wait()
			# in case of errors
			except Exception as err:
				# logger
				cfg.utls.logCondition(str(__name__) + '-' + (cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
		imagePath = tmpImage
		label = cfg.ui.image_preview_label
		pixmap = cfg.QtGuiSCP.QPixmap(imagePath).scaled(300, 300)
		label.setPixmap(pixmap)
		return imagePath
				
	# table click
	def tableClick(self):
		tW = cfg.ui.download_images_tableWidget
		i = tW.currentRow()
		ids = []
		for tI in tW.selectedIndexes():
			ids.append(tI.row())
		idT = set(ids)
		if i >= 0 and not len(idT) > 1:
			cfg.uiUtls.addProgressBar()
			progress = 10
			sat = str(tW.item(i, 0).text())
			if sat in cfg.satSentinelList:
				self.displayGranulesSentinel2(i, progress, 'Yes')
			elif sat in cfg.satSentinel3List:
				self.displayGranulesSentinel3(i, progress, 'Yes')
			elif sat in cfg.satSentinel1List:
				self.displayGranulesSentinel1(i, progress, 'Yes')
			elif sat in cfg.satLandsatList or sat in cfg.satASTERtList or sat in cfg.satMODIStList:
				self.displayImagesNASA(i, progress, 'Yes')
			cfg.uiUtls.updateBar(progress, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Downloading ...'))
			cfg.uiUtls.removeProgressBar()
			# logger
			cfg.utls.logCondition(str(__name__) + '-' + (cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' image index: ' + str(i))
						
	# download thumbnail
	def downloadThumbnail(self, imgID, path, row, min_lat, min_lon, max_lat, max_lon, imageJPG, sat, progress = None, preview = 'No'):
		imOut = cfg.tmpDir + '//' + imgID + '_thumb.jpg'
		if sat in cfg.satLandsatList:
			check = cfg.utls.downloadFile(imageJPG, imOut, imgID + '_thumb.jpg', progress)			
		elif sat == cfg.usgsASTER:
			user = cfg.ui.user_usgs_lineEdit_2.text()
			password = cfg.ui.password_usgs_lineEdit_2.text()
			check = cfg.utls.passwordConnectPython(user, password, imageJPG, 'urs.earthdata.nasa.gov', imOut, progress, 'No')
		elif sat in cfg.satMODIStList:
			user = cfg.ui.user_usgs_lineEdit_2.text()
			password =cfg.ui.password_usgs_lineEdit_2.text()
			check = cfg.utls.passwordConnectPython(user, password, imageJPG, 'urs.earthdata.nasa.gov', imOut, progress, 'No')
		if check == 'Yes':
			if preview == 'Yes':
				self.previewInLabel(imOut)
				return imOut
			self.onflyGeorefImage(cfg.tmpDir + '//' + imgID + '_thumb.jpg ', cfg.tmpDir + '//' + imgID + '.vrt', min_lon, max_lon, min_lat, max_lat)
		else:
			cfg.mx.msgErr40()
	
	# remove highlighted images from table
	def removeImageFromTable(self):
		tW = cfg.ui.download_images_tableWidget
		cfg.utls.removeRowsFromTable(tW)
					
	# download images in table
	def downloadImages(self):
		tW = cfg.ui.download_images_tableWidget
		c = len(self._downloadRowIndices(tW))
		if c > 0:
			d = cfg.utls.getExistingDirectory(None , cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Download the images in the table (requires internet connection)'))
			if len(d) > 0:
				cfg.cdseDownloadCancelled = False
				if self.downloadSentinelImages(d) == 'No':
					return
				if getattr(cfg, 'cdseDownloadCancelled', False):
					return
				if self.downloadSentinel3Images(d) == 'No':
					return
				if getattr(cfg, 'cdseDownloadCancelled', False):
					return
				if self.downloadSentinel1Images(d) == 'No':
					return
				if getattr(cfg, 'cdseDownloadCancelled', False):
					return
				if self.downloadLandsatImages(d) == 'No':
					return
				if getattr(cfg, 'cdseDownloadCancelled', False):
					return
				if self.downloadASTERImages(d) == 'No':
					return
				if getattr(cfg, 'cdseDownloadCancelled', False):
					return
				if self.downloadMODISImages(d) == 'No':
					return
				if getattr(cfg, 'cdseDownloadCancelled', False):
					return
				if self.downloadGOESImages(d) == 'No':
					return
				if getattr(cfg, 'cdseDownloadCancelled', False):
					return
				cfg.utls.sendSMTPMessage(None, str(__name__))
				cfg.utls.finishSound()
		
	# download Landsat data
	def downloadLandsatImages(self, outputDirectory, exporter = 'No'):
		cfg.uiUtls.addProgressBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Downloading'), message = '')
		tW = cfg.ui.download_images_tableWidget
		if cfg.ui.virtual_download_checkBox.isChecked():
			virtualDownload = 'vrt'
		else:
			virtualDownload = None
		try:
			iLeft = float(cfg.ui.UX_lineEdit_3.text())
			iTop = float(cfg.ui.UY_lineEdit_3.text())
			iRight = float(cfg.ui.LX_lineEdit_3.text())
			iBottom = float(cfg.ui.LY_lineEdit_3.text())
			extentList = [iLeft, iRight, iTop, iBottom]
		except:
			extentList = None
		rows = self._downloadRowIndices(tW)
		c = len(rows)
		if c == 0:
			cfg.uiUtls.removeProgressBar()
			return []
		progressStep = 100 / c
		progressStep2 = progressStep/12
		progress = 0
		outDirList = []
		imgList = []
		links = []
		for i in rows:
			sat = str(tW.item(i, 0).text())
			if cfg.actionCheck == 'Yes':
				if sat in cfg.satLandsatList:
					imgID = str(tW.item(i, 1).text())
					if cfg.ui.download_if_preview_in_legend_checkBox.isChecked() and cfg.utls.selectLayerbyName(imgID, 'Yes') is None:
						pass
					else:
						acquisitionDate = str(tW.item(i, 2).text())
						path = str(tW.item(i, 4).text())
						row = str(tW.item(i, 5).text())
						USGScollection = str(tW.item(i, 10).text())
						NASAcollection = str(tW.item(i, 12).text())
						lImgID = str(tW.item(i, 13).text())
						outDir = outputDirectory + '/' + imgID + '_' + acquisitionDate[0:10]
						oDir = cfg.utls.makeDirectory(outDir)
						if oDir is None:
							cfg.uiUtls.removeProgressBar()
							cfg.mx.msgErr58()
							return 'No'
						outDirList.append(outDir)
						# download Landsat data using the service https://storage.googleapis.com/gcp-public-data-landsat
						sat = imgID[0:4]
						collID = '01'
						urlL = 'https://storage.googleapis.com/gcp-public-data-landsat/'+ sat + '/' + collID +'/' + path.zfill(3) + '/' + row.zfill(3) +'/' + imgID + '/' + imgID + '_'
						check = cfg.utls.downloadFile( urlL + 'MTL.txt', outDir + '//' + imgID + '_MTL.txt', imgID + '_MTL.txt', progress)
						if check == 'Yes':
							meta = open(outDir + '//' + imgID + '_MTL.txt', 'r').read()
							if 'NoSuchKey' in meta:
								check = 'No'
						if check == 'Yes':
							links.append(urlL + 'MTL.txt')
							if NASAcollection == cfg.NASALandsat8Collection:
								bRange = [1,2,3,4,5,6,7,8,9,10,11,12]
							elif NASAcollection == cfg.NASALandsat7Collection:
								bRange = [1,2,3,4,5,6,7,8,12]
							elif NASAcollection == cfg.NASALandsat45Collection:
								bRange = [1,2,3,4,5,6,7,12]
							elif NASAcollection == cfg.NASALandsat15Collection:
								if sat[-1] == '4' or sat[-1]== '5':
									bRange = [1,2,3,4]
								else:
									bRange = [4,5,6,7]
							for i in bRange:
								progress = progress + progressStep2
								if cfg.actionCheck == 'Yes':
									if exporter == 'Yes':
										links.append(urlL + 'B' + str(i) + '.TIF')
									else:
										t = 'cfg.ui.checkBox_band_' + str(i) + '.isChecked()'
										checkBand = cfg.scp_eval(t, locals())
										if checkBand is True:
											# Landsat 7 bands 6
											if NASAcollection == cfg.NASALandsat7Collection and i == 6:
												self.downloadDispatcher( urlL + 'B6_VCID_1.TIF', outDir + '//' + imgID  + '_' + acquisitionDate[0:10] + '_B6_VCID_1.TIF', imgID + '_B6_VCID_1.TIF', progress, extentList, virtualDownload)
												if cfg.osSCP.path.isfile(outDir + '//' + imgID  + '_' + acquisitionDate[0:10] + '_B6_VCID_1.TIF'):
													imgList.append(outDir + '//' + imgID  + '_' + acquisitionDate[0:10] + '_B6_VCID_1.TIF')
													# logger
													cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' image downloaded ' + imgID + '_B6_VCID_1.TIF')
												self.downloadDispatcher( urlL + 'B6_VCID_2.TIF', outDir + '//' + imgID  + '_' + acquisitionDate[0:10] + '_B6_VCID_1.TIF', imgID + '_B6_VCID_2.TIF', progress, extentList, virtualDownload)
												if cfg.osSCP.path.isfile(outDir + '//' + imgID  + '_' + acquisitionDate[0:10] + '_B6_VCID_2.TIF'):
													imgList.append(outDir + '//' + imgID  + '_' + acquisitionDate[0:10] + '_B6_VCID_2.TIF')
													# logger
													cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' image downloaded ' + imgID + '_B6_VCID_2.TIF')
											else:
												self.downloadDispatcher(urlL + 'B' + str(i) + '.TIF', outDir + '//' + imgID  + '_' + acquisitionDate[0:10] + '_B' + str(i) + '.TIF', imgID + '_B' + str(i) + '.TIF', progress, extentList, virtualDownload)
												if cfg.osSCP.path.isfile(outDir + '//' + imgID  + '_' + acquisitionDate[0:10] + '_B' + str(i) + '.TIF'):
													imgList.append(outDir + '//' + imgID  + '_' + acquisitionDate[0:10] + '_B' + str(i) + '.TIF')
													# logger
													cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' image downloaded ' + imgID + '_B' + str(i))
								else:
									cfg.uiUtls.removeProgressBar()
									return 'No'
							if cfg.actionCheck == 'Yes':
								progress = progress + progressStep2
								if cfg.ui.checkBox_band_12.isChecked():
									if exporter == 'Yes':
										links.append(urlL + 'BQA.TIF')
									else:
										self.downloadDispatcher( urlL + 'BQA.TIF', outDir + '//' + imgID  + '_' + acquisitionDate[0:10] + '_BQA.TIF', imgID + '_BQA.TIF', progress, extentList, virtualDownload)
										if cfg.osSCP.path.isfile(outDir + '//' + imgID + '_' + acquisitionDate[0:10] + '_BQA.TIF'):
											imgList.append(outDir + '//' + imgID + '_' + acquisitionDate[0:10] + '_BQA.TIF')
											# logger
											cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' image downloaded ' + imgID + '_BQA.TIF')
						else:
							outUrl = self.downloadLandsatImagesFromUSGS(lImgID, USGScollection, row, outDir, progress, exporter)
							links.append(outUrl)
							progress = progress + progressStep
			else:
				cfg.uiUtls.removeProgressBar()
				return 'No'
		if exporter == 'Yes':
			return links
		else:
			cfg.cnvs.setRenderFlag(False)
			if cfg.ui.preprocess_checkBox.isChecked():
				n = len(outDirList)
				i = 0
				for d in outDirList:
					i = i + 1
					cfg.uiUtls.updateBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Processing') + ' [' + str(i) + '/' + str(n) + '] ' + cfg.osSCP.path.basename(d), message = '')
					if cfg.actionCheck == 'Yes':
						cfg.landsatT.populateTable(d, 'Yes')
						o = d + '_converted'
						cfg.utls.makeDirectory(o)
						cfg.landsatT.landsat(d, o, 'Yes')
			elif cfg.ui.load_in_QGIS_checkBox.isChecked():
				for d in outDirList:
					try:
						for f in cfg.osSCP.listdir(d):
							if f.lower().endswith('.tif'):
								r =cfg.utls.addRasterLayer(d + '/' + f)
					except Exception as err:
						# logger
						cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
			cfg.uiUtls.removeProgressBar()
			cfg.cnvs.setRenderFlag(True)
			
	# download image preview
	def downloadLandsatImagesFromUSGS(self, imageID, collection, row, outputDirectory, progress, exporter = 'No'):
		url = 'http://earthexplorer.usgs.gov/download/' + collection + '/' + imageID + '/STANDARD/EE'
		if exporter == 'Yes':
			return url
		else:
			user = cfg.ui.user_usgs_lineEdit.text()
			password =cfg.ui.password_usgs_lineEdit.text()
			try:
				imgID = imageID + '.tar.gz'
				check = cfg.utls.downloadFileUSGS(user, password, 'https://ers.cr.usgs.gov', url, cfg.tmpDir + '//' + imgID, imgID, progress, 'Yes')
				if str(check) == 'Cancel action':
					return check
				if cfg.osSCP.path.getsize(cfg.tmpDir + '//' + imgID) > 10000:
					tarFiles = cfg.tarfileSCP.open(cfg.tmpDir + '//' + imgID, 'r:gz')
					tarFiles.extractall(outputDirectory, filter="data")
					tarFiles.close()
					cfg.osSCP.remove(cfg.tmpDir + '//' + imgID)
					return url
				else:
					cfg.mx.msgErr55(imgID)
					return 'No'
			except Exception as err:
				cfg.mx.msgErr50(str(err))
				# logger
				cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
				return 'No'
					
	# select the download type
	def downloadDispatcher(self, url, outputPath, fileName = None, progress = None, extentList = None, downloadType = None):
		if downloadType is None:
			cfg.utls.downloadFile(url, outputPath, fileName, progress)
		elif downloadType == 'vrt':
			cfg.utls.downloadVirtualImages(url, outputPath, fileName, progress, extentList)
			
	# export links
	def exportLinks(self):
		tW = cfg.ui.download_images_tableWidget
		rows = self._downloadRowIndices(tW)
		c = len(rows)
		if c == 0:
			return
		if c > 0:
			d = cfg.utls.getSaveFileName(None , cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Export download links'), '', '*.txt', 'txt')
			if d is not False:
				if d.lower().endswith('.txt'):
					pass
				else:
					d = d + '.txt'
				linksS = self.downloadSentinelImages(cfg.tmpDir, 'Yes')
				linksS3 = self.downloadSentinel3Images(cfg.tmpDir, 'Yes')
				linksS1 = self.downloadSentinel1Images(cfg.tmpDir, 'Yes')
				linksL = self.downloadLandsatImages(cfg.tmpDir, 'Yes')
				linksA = self.downloadASTERImages(cfg.tmpDir, 'Yes')
				linksM = self.downloadMODISImages(cfg.tmpDir, 'Yes')
				linksG = self.downloadGOESImages(cfg.tmpDir, 'Yes')
				links =  linksS + linksS3 + linksS1 + linksL + linksA + linksM + linksG
				if links == 'No':
					pass
				else:
					l = open(d, 'w')
					for t in links:
						l.write(t + '\n')
					l.close()
					cfg.utls.finishSound()
					cfg.uiUtls.removeProgressBar()
				
	# check all bands
	def checkAllBands(self):
		if self.checkAll == 'Yes':
			for i in range(1, 13):
				t = 'cfg.ui.checkBox_band_' + str(i) + '.setCheckState(cfg.QtSCP.CheckState.Checked)'
				cfg.scp_eval(t, locals())
			self.checkAll = 'No'
		else:
			for i in range(1, 13):
				t = 'cfg.ui.checkBox_band_' + str(i) + '.setCheckState(cfg.QtSCP.CheckState.Unchecked)'
				cfg.scp_eval(t, locals())
			self.checkAll = 'Yes'
			
	# clear table
	def clearTable(self):
		# ask for confirm
		a = cfg.utls.questionBox(cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Reset signature list'), cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Are you sure you want to clear the table?'))
		if a == 'Yes':
			tW = cfg.ui.download_images_tableWidget
			cfg.utls.clearTable(tW)
			
	# show hide area radio button
	def showHideArea(self):
		try:
			if cfg.ui.show_area_radioButton_2.isChecked():				
				self.showArea()
			else:
				self.clearCanvasPoly()
		except:
			int(0)
			
### Sentinel-3
					
	# read database
	def queryDatabaseSentinel3(self):
		cfg.uiUtls.addProgressBar()
		cfg.uiUtls.updateBar(20, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching Copernicus Data Space ...'))
		cfg.QtWidgetsSCP.QApplication.instance().processEvents()
		return self._cdsePopulateResults('SENTINEL-3', 'SENTINEL-3')

	def displayGranulesSentinel3(self, row, progress, preview = 'No'):
		i = row
		tW = cfg.ui.download_images_tableWidget
		imgNm = str(tW.item(i, 1).text())
		acquisitionDate = str(tW.item(i, 2).text())
		imgID = imgNm + '.vrt'
		url = str(tW.item(i, 11).text())
		# image preview
		imOut = cfg.tmpDir + '//' + imgID
		if preview == 'Yes' and cfg.osSCP.path.isfile(imOut):
			self.previewInLabel(imOut)
			return imOut
		if cfg.osSCP.path.isfile(imOut + '.vrt'):
			l = cfg.utls.selectLayerbyName(imgID)
			if l is not None:		
				cfg.utls.setLayerVisible(l, True)
				cfg.utls.moveLayerTop(l)
			else:
				r =cfg.utls.addRasterLayer(imOut, imgID)
		else:		
			min_lat = str(tW.item(i, 6).text())
			min_lon = str(tW.item(i, 7).text())
			max_lat = str(tW.item(i, 8).text())
			max_lon = str(tW.item(i, 9).text())
			self.downloadThumbnailSentinel3(imgID, min_lat, min_lon, max_lat, max_lon, url, progress, preview)
			if cfg.osSCP.path.isfile(imOut + '.vrt'):
				r =cfg.utls.addRasterLayer(imOut + '.vrt', imgID)
				cfg.utls.setRasterColorComposite(r, 1, 2, 3)		
		# logger
		cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), " granules displayed")
		
	# download image preview
	def downloadThumbnailSentinel3(self, imgID, min_lat, min_lon, max_lat, max_lon, imageJPG, progress=None, preview='No'):
		if not imageJPG:
			return 'No'
		im_out = cfg.tmpDir + '//' + imgID
		if self._cdseDownloadFile(imageJPG, im_out, progress) != 'Yes':
			return 'No'
		if preview == 'Yes':
			self.previewInLabel(im_out)
			return im_out
		self.onflyGeorefImage(im_out, im_out + '.vrt', min_lon, max_lon, min_lat, max_lat)
		return im_out


	def downloadSentinel3Images(self, outputDirectory, exporter = 'No'):
		cfg.uiUtls.addProgressBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Downloading'), message = '')
		tW = cfg.ui.download_images_tableWidget
		outDirList = []
		imgList = []
		links = []
		rows = self._downloadRowIndices(tW)
		c = len(rows)
		if c == 0:
			cfg.uiUtls.removeProgressBar()
			cfg.cnvs.setRenderFlag(True)
			return []
		progressStep = 100 / c
		progress = 0
		# disable map canvas render for speed
		cfg.cnvs.setRenderFlag(False)
		for i in rows:
			sat = str(tW.item(i, 0).text())
			if cfg.actionCheck == 'Yes':
				if sat == cfg.esaSentinel3:
					imgName = str(tW.item(i, 13).text())
					acquisitionDate = str(tW.item(i, 2).text())
					imgID = str(tW.item(i, 12).text())
					imgName2 = str(tW.item(i, 1).text())
					imgJp2 = imgName2 + '.vrt'
					if cfg.ui.download_if_preview_in_legend_checkBox.isChecked() and cfg.utls.selectLayerbyName(imgJp2, 'Yes') is None:
						pass
					else:
						outFiles = []
						outDirList.append(outputDirectory + '//' + imgName2)
						progress = progress + progressStep
						if exporter == 'No':
							oDir = cfg.utls.makeDirectory(outputDirectory + '//' + imgName2)
							if oDir is None:
								cfg.mx.msgErr58()
								cfg.uiUtls.removeProgressBar()
								cfg.cnvs.setRenderFlag(True)
								return 'No'
						# download bands
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_1, '01', imgID, imgName, imgName2, acquisitionDate,outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_2, '02', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_3, '03', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_4, '04', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_5, '05', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_6, '06', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_7, '07', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_8, '08', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_9, '09', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_10, '10', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_11, '11', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_12, '12', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_13, '13', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_14, '14', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_15, '15', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_16, '16', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_17, '17', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_18, '18', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_19, '19', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_20, '20', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.checkBoxs3_band_21, '21', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.s3_ancillary_data_checkBox, 'ancillary1', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.s3_ancillary_data_checkBox, 'ancillary2', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.s3_ancillary_data_checkBox, 'ancillary3', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						self.checkSentinel3ImageBands(cfg.ui.s3_ancillary_data_checkBox, 'ancillary4', imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFiles, links)
						for oFile in outFiles:
							cfg.shutilSCP.copy(oFile[0], oFile[1])
							cfg.osSCP.remove(oFile[0])
			else:
				cfg.uiUtls.removeProgressBar()
				cfg.cnvs.setRenderFlag(True)
				return 'No'
		if cfg.ui.preprocess_checkBox.isChecked() and exporter == 'No':
			n = len(outDirList)
			i = 0
			for d in outDirList:
				i = i + 1
				cfg.uiUtls.updateBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Processing') + ' [' + str(i) + '/' + str(n) + '] ' + cfg.osSCP.path.basename(d), message = '')
				if cfg.actionCheck == 'Yes':
					cfg.sentinel3T.populateTable(d, 'Yes')
					o = d + '_con'
					oDir = cfg.utls.makeDirectory(o)
					if oDir is None:
						cfg.mx.msgErr58()
						cfg.uiUtls.removeProgressBar()
						cfg.cnvs.setRenderFlag(True)
						return 'No'
					cfg.sentinel3T.sentinel3(d, o, 'Yes')
		cfg.uiUtls.removeProgressBar()
		cfg.cnvs.setRenderFlag(True)
		return links
					
	# check band download
	def checkSentinel3ImageBands(self, checkbox, bandNumber, imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFilesList, linksList):
		if cfg.actionCheck != 'Yes' or not checkbox.isChecked():
			return
		if bandNumber == 'ancillary1':
			filename = 'tie_geometries.nc'
		elif bandNumber == 'ancillary2':
			filename = 'qualityFlags.nc'
		elif bandNumber == 'ancillary3':
			filename = 'geo_coordinates.nc'
		elif bandNumber == 'ancillary4':
			filename = 'instrument_data.nc'
		else:
			filename = 'Oa' + bandNumber + '_radiance.nc'
		url = self._cdseNodeUrl(imgID, imgName + '.SEN3', filename)
		product_output = outputDirectory + '//' + imgName2
		if bandNumber.startswith('ancillary'):
			output_copy = product_output + '//' + filename
		else:
			output_copy = product_output + '//' + imgName + '_' + acquisitionDate[:10] + '_B' + bandNumber + '.nc'
		if exporter == 'No':
			temp_file = cfg.tmpDir + '//' + imgName[:15] + '_' + acquisitionDate[:10] + '_B' + bandNumber + '.nc'
			if self.downloadFileSentinel3(url, temp_file, progress) == 'No':
				return 'No'
			outFilesList.append([temp_file, output_copy])
		else:
			linksList.append(url)


	def downloadFileSentinel3(self, url, output, progress=None):
		return output if self._cdseDownloadFile(url, output, progress) == 'Yes' else 'No'


	def rememberUserSentinel2(self):	
		if cfg.ui.remember_user_checkBox.isChecked():
			user = cfg.ui.user_scihub_lineEdit.text()
			pswd = cfg.utls.encryptPassword(cfg.ui.password_scihub_lineEdit.text())
			cfg.utls.setQGISRegSetting(cfg.regSciHubUser, user)
			cfg.utls.setQGISRegSetting(cfg.regSciHubPass, pswd)
			
	def rememberUserCheckboxSentinel2(self):
		if cfg.ui.remember_user_checkBox.isChecked():
			self.rememberUserSentinel2()
		else:
			cfg.utls.setQGISRegSetting(cfg.regSciHubUser, '')
			cfg.utls.setQGISRegSetting(cfg.regSciHubPass, '')
			
	def alternativeCheckboxSentinel2(self):
		if cfg.ui.sentinel2_alternative_search_checkBox.isChecked():
			cfg.utls.setQGISRegSetting(cfg.regSentinelAlternativeSearch, '2')
		else:
			cfg.utls.setQGISRegSetting(cfg.regSentinelAlternativeSearch, '0')
			
	# reset service
	def resetService(self):
		cfg.ui.sentinel_service_lineEdit.setText(cfg.SciHubServiceNm)
		cfg.utls.setQGISRegSetting(cfg.regSciHubService, cfg.SciHubServiceNm)

	# service
	def rememberService(self):
		service = cfg.ui.sentinel_service_lineEdit.text()
		cfg.utls.setQGISRegSetting(cfg.regSciHubService, service)
			
	# download file
	def downloadFileSentinel2(self, url, output, progress=None, optional=False):
		if 'storage.googleapis.com' in url:
			return cfg.utls.downloadFile(url, output, None, progress)
		return self._cdseDownloadFile(url, output, progress, optional)


	def displayGranulesSentinel2(self, row, progress, preview = 'No'):
		i = row
		tW = cfg.ui.download_images_tableWidget
		imgNm = str(tW.item(i, 1).text())
		acquisitionDate = str(tW.item(i, 2).text())
		if imgNm[0:4] == 'L1C_':
			imgID = imgNm + '_p.jp2'
		elif imgNm[0:4] == 'L2A_':
			imgID = imgNm + '_p.jp2'
		else:
			imgID = imgNm[0:-7] + '_p.jp2'
		url = str(tW.item(i, 11).text())
		# image preview
		imOut = cfg.tmpDir + '//' + imgID
		if preview == 'Yes' and cfg.osSCP.path.isfile(imOut):
			self.previewInLabel(imOut)
			return imOut
		if cfg.osSCP.path.isfile(imOut  + '.vrt') or cfg.osSCP.path.isfile(cfg.reSCP.sub(r'\.jp2$', '.png', str(imOut)) + '.vrt' ):
			l = cfg.utls.selectLayerbyName(imgID)
			if l is not None:		
				cfg.utls.setLayerVisible(l, True)
				cfg.utls.moveLayerTop(l)
			else:
				r =cfg.utls.addRasterLayer(imOut + '.vrt', imgID)
		else:
			if 'storage.googleapis.com' in url:
				check = cfg.utls.downloadFile(url, imOut, None, progress)
			else:
				check = self.downloadFileSentinel2(url, imOut, progress)
			if check != 'No':
				if preview == 'Yes':
					self.previewInLabel(imOut)
					return imOut
				min_lat = str(tW.item(i, 6).text())
				min_lon = str(tW.item(i, 7).text())
				max_lat = str(tW.item(i, 8).text())
				max_lon = str(tW.item(i, 9).text())
				self.onflyGeorefImage(imOut, imOut + '.vrt', min_lon, max_lon, min_lat, max_lat)
				if cfg.osSCP.path.isfile(imOut + '.vrt'):
					r =cfg.utls.addRasterLayer(imOut + '.vrt', cfg.reSCP.sub(r'\.vrt$', '', str(imgID)))
		# logger
		cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' granules displayed')
					
	# use CREODIAS Finder API https://creodias.eu/ (from https://creodias.eu/eo-data-finder-api-manual the database is accessible free and anonymously, and open for anonymous access to everyone, no authorization is used). For other DIAS platforms see https://www.copernicus.eu/en/access-data/dias
	def queryDatabaseSentinel2Alternative(self):
		QdateFrom = cfg.ui.dateEdit_from.date()
		QdateTo = cfg.ui.dateEdit_to.date()
		dateFrom = QdateFrom.toPyDate().strftime('%Y-%m-%d') 
		dateTo = QdateTo.toPyDate().strftime('%Y-%m-%d') 
		maxCloudCover = int(cfg.ui.cloud_cover_spinBox.value())
		resultNum = int(cfg.ui.result_number_spinBox_2.value())
		sat = cfg.ui.landsat_satellite_combo.currentText()
		imageFindList = []
		m = 'S2*'
		if len(cfg.ui.imageID_lineEdit.text()) > 0:
			imgIDLine = cfg.ui.imageID_lineEdit.text()
			imgIDLineSplit = str(imgIDLine).replace(' ', '').split(';')
			if len(imgIDLineSplit) == 1:
				imgIDLineSplit = str(imgIDLine).replace(' ', '').split(',')
			for m in imgIDLineSplit:
				imageFindList.append(m.lower().replace('*', ''))
			imgQuery = ''
			if len(imageFindList) == 1:
				imgQuery = m + '%20AND%20'
		else:
			imageFindList.append('s2')
			imgQuery = ''
		try:
			NoRect = 'No'
			rubbRect = cfg.qgisCoreSCP.QgsRectangle(float(cfg.ui.UX_lineEdit_3.text()), float(cfg.ui.UY_lineEdit_3.text()), float(cfg.ui.LX_lineEdit_3.text()), float(cfg.ui.LY_lineEdit_3.text()))
			if abs(float(cfg.ui.UX_lineEdit_3.text()) - float(cfg.ui.LX_lineEdit_3.text())) > 10 or abs(float(cfg.ui.UY_lineEdit_3.text()) - float(cfg.ui.LY_lineEdit_3.text())) > 10:
				cfg.mx.msgWar18()
		except Exception as err:
			if len(imageFindList) == 1:
				imgQuery = m + '*' + '%20AND%20'
				NoRect = 'Yes'
			else:
				# logger
				cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
				cfg.mx.msg23()
				return 'No'
		cfg.uiUtls.addProgressBar()
		imgQuery = cfg.ui.imageID_lineEdit.text()
		if len(imgQuery) == 0:
			imgQuery = 'S2'
		tW = cfg.ui.download_images_tableWidget
		cfg.uiUtls.updateBar(30, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching ...'))
		cfg.QtWidgetsSCP.QApplication.instance().processEvents()
		imageTableList = []
		# loop for results
		maxResultNum = resultNum
		if maxResultNum > 100:
			maxResultNum = 100
		page = 0
		for startR in range(0, resultNum, maxResultNum):
			page = page + 1
			if NoRect == 'Yes':
				url = 'https://finder.creodias.eu/resto/api/collections/Sentinel2/search.json?cloudCover=[0%2C' + str(maxCloudCover) + ']&maxRecords=' + str(maxResultNum) + '&page=' + str(page) + '&sortParam=startDate&sortOrder=descending&status=all&dataset=ESA-DATASET' + '&productIdentifier=%25' + imgQuery + '%25&startDate=' + str(dateFrom) + 'T00%3A00%3A00Z&completionDate=' + str(dateTo) + 'T23%3A59%3A59Z'
			else:
				url = 'https://finder.creodias.eu/resto/api/collections/Sentinel2/search.json?cloudCover=[0%2C' + str(maxCloudCover) + ']&maxRecords=' + str(maxResultNum) + '&page=' + str(page) + '&sortParam=startDate&sortOrder=descending&status=all&dataset=ESA-DATASET' + '&productIdentifier=%25' + imgQuery + '%25&startDate=' + str(dateFrom) + 'T00%3A00%3A00Z&completionDate=' + str(dateTo) + 'T23%3A59%3A59Z&geometry=POLYGON((' + cfg.ui.UX_lineEdit_3.text() + '%20' + cfg.ui.UY_lineEdit_3.text() + ',' + cfg.ui.UX_lineEdit_3.text() + '%20' + cfg.ui.LY_lineEdit_3.text() + ',' + cfg.ui.LX_lineEdit_3.text() + '%20' + cfg.ui.LY_lineEdit_3.text() + ',' + cfg.ui.LX_lineEdit_3.text() + '%20' + cfg.ui.UY_lineEdit_3.text() + ',' + cfg.ui.UX_lineEdit_3.text() + '%20' + cfg.ui.UY_lineEdit_3.text() + '))'
			jsonT = cfg.utls.createTempRasterPath('json')
			check = cfg.utls.downloadFile(url, jsonT)
			if check != 'Yes':
				cfg.uiUtls.removeProgressBar()
				return 'No'
			try:
				with open(jsonT) as jsonTF:
					doc = cfg.jsonSCP.load(jsonTF)
			except Exception as err:
				# logger
				cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
				cfg.mx.msgErr40()
				cfg.uiUtls.removeProgressBar()
				return 'No'
			tW.setSortingEnabled(False)
			entries = doc['features']
			e = 0
			for entry in entries:
				if cfg.actionCheck == 'Yes':
					productType = 'S2MSI1C'
					e = e + 1
					cfg.uiUtls.updateBar(30 + e * int(70/len(entries)), cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching ...'))
					imgName = entry['properties']['title'].replace('.SAFE', '')
					acqDateI =  entry['properties']['startDate']
					productType =  entry['properties']['productType']
					cloudcoverpercentage =  entry['properties']['cloudCover']
					footprintCoord =  entry['geometry']['coordinates'][0]
					xList = []
					yList = []
					for coords in footprintCoord:
						xList.append(float(coords[0]))
						yList.append(float(coords[1]))
					min_lon = min(xList)
					max_lon = max(xList)
					min_lat = min(yList)
					max_lat = max(yList)
					if cfg.actionCheck == 'Yes':
						# download Sentinel data using the service https://storage.googleapis.com/gcp-public-data-sentinel-2
						if productType == 'L1C':
							url2 = 'https://storage.googleapis.com/gcp-public-data-sentinel-2/tiles/' + imgName[39:41] + '/'+  imgName[41]  + '/'+ imgName[42:44] + '/' +imgName + '.SAFE/MTD_MSIL1C.xml'
						else:
							url2 = 'https://storage.googleapis.com/gcp-public-data-sentinel-2/L2/tiles/' + imgName[39:41] + '/'+  imgName[41]  + '/'+ imgName[42:44] + '/' +imgName + '.SAFE/MTD_MSIL2A.xml'
						xml2T = cfg.utls.createTempRasterPath('xml')
						check = cfg.utls.downloadFile(url2, xml2T)
						# logger
						cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' xml downloaded' )
						try:
							newV = None
							if xml2T is not None:
								doc2 = cfg.minidomSCP.parse(xml2T)
							else:
								doc2 = cfg.minidomSCP.parseString(xml2)
							try:
								imgName2Tag = doc2.getElementsByTagName('IMAGE_FILE')[0]
							except:
								imgName2Tag = doc2.getElementsByTagName('IMAGE_FILE_2A')[0]
							imgName2 = imgName2Tag.firstChild.data.split('/')[1]
							if cfg.actionCheck == 'Yes':								
								for filter in imageFindList:
									if filter in imgName.lower() or filter in imgName2.lower():
										acZoneI = imgName2.split("_")[1][1:]
										# add item to table
										c = tW.rowCount()
										# add list items to table
										tW.setRowCount(c + 1)
										if productType == 'L1C':
											imgName3 = imgName2Tag.firstChild.data.split('/')[3]
											imgName3 = imgName3.split('_')
											pviName = imgName3[0] + '_' + imgName3[1] + '_PVI.jp2'
											imgPreview = 'https://storage.googleapis.com/gcp-public-data-sentinel-2/tiles/' + imgName[39:41] + '/'+  imgName[41]  + '/'+ imgName[42:44] + '/' +imgName + '.SAFE/GRANULE/' + imgName2 + '/QI_DATA/' + pviName 
										else:
											imgName3 = imgName2Tag.firstChild.data.split('/')[4]
											imgName3 = imgName3.split('_')
											pviName = imgName3[0] + '_' + imgName3[1] + '_PVI.jp2'
											imgPreview = 'https://storage.googleapis.com/gcp-public-data-sentinel-2/L2/tiles/' + imgName[39:41] + '/'+  imgName[41]  + '/'+ imgName[42:44] + '/' +imgName + '.SAFE/GRANULE/' + imgName2 + '/QI_DATA/' + pviName
										cfg.utls.addTableItem(tW, sat, c, 0)
										cfg.utls.addTableItem(tW, imgName2, c, 1)
										cfg.utls.addTableItem(tW, acqDateI, c, 2)
										cfg.utls.addTableItem(tW, float(cloudcoverpercentage), c, 3)
										cfg.utls.addTableItem(tW, acZoneI, c, 4)
										cfg.utls.addTableItem(tW, '', c, 5)
										cfg.utls.addTableItem(tW, float(min_lat), c, 6)
										cfg.utls.addTableItem(tW, float(min_lon), c, 7)
										cfg.utls.addTableItem(tW, float(max_lat), c, 8)
										cfg.utls.addTableItem(tW, float(max_lon), c, 9)
										cfg.utls.addTableItem(tW, '', c, 10)
										cfg.utls.addTableItem(tW, imgPreview, c, 11)
										cfg.utls.addTableItem(tW, imgName, c, 12)
										cfg.utls.addTableItem(tW, imgName, c, 13)
										newV = 'Yes'
										break
						except Exception as err:
							if cfg.actionCheck == 'Yes':								
								for filter in imageFindList:
									if filter in imgName.lower():
										# add item to table
										c = tW.rowCount()
										co = cfg.QtGuiSCP.QColor(160, 160, 160)
										# add list items to table
										tW.setRowCount(c + 1)
										cfg.utls.addTableItem(tW, sat, c, 0, 'Yes', co)
										cfg.utls.addTableItem(tW, imgName, c, 1, 'Yes', co)
										cfg.utls.addTableItem(tW, acqDateI, c, 2, 'Yes', co)
										cfg.utls.addTableItem(tW, float(cloudcoverpercentage), c, 3, 'Yes', co)
										cfg.utls.addTableItem(tW, '', c, 4, 'Yes', co)
										cfg.utls.addTableItem(tW, '', c, 5, 'Yes', co)
										cfg.utls.addTableItem(tW, float(min_lat), c, 6, 'Yes', co)
										cfg.utls.addTableItem(tW, float(min_lon), c, 7, 'Yes', co)
										cfg.utls.addTableItem(tW, float(max_lat), c, 8, 'Yes', co)
										cfg.utls.addTableItem(tW, float(max_lon), c, 9, 'Yes', co)
										cfg.utls.addTableItem(tW, '', c, 10, 'Yes', co)
										cfg.utls.addTableItem(tW, '', c, 11, 'Yes', co)
										cfg.utls.addTableItem(tW, imgName, c, 12, 'Yes', co)
										cfg.utls.addTableItem(tW, imgName, c, 13, 'Yes', co)
										newV = 'Yes'
										# logger
										cfg.utls.logCondition(str(__name__) + '-' + (cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
										break
		tW.setSortingEnabled(True)		
		cfg.uiUtls.removeProgressBar()
		self.clearCanvasPoly()
		# logger
		cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' Sentinel images')
		
	# read database
	def queryDatabaseSentinel2(self):
		if cfg.ui.sentinel2_alternative_search_checkBox.isChecked():
			return self.queryDatabaseSentinel2Alternative()
		cfg.uiUtls.addProgressBar()
		cfg.uiUtls.updateBar(20, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching Copernicus Data Space ...'))
		cfg.QtWidgetsSCP.QApplication.instance().processEvents()
		return self._cdsePopulateResults('SENTINEL-2', 'SENTINEL-2')

	def downloadSentinelImages(self, outputDirectory, exporter='No'):
		table = cfg.ui.download_images_tableWidget
		rows = self._downloadRowIndices(table)
		row_count = len(rows)
		if row_count == 0:
			return []
		cfg.uiUtls.addProgressBar(mainMessage=cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Downloading'), message='')
		cfg.cnvs.setRenderFlag(False)
		links = []
		out_dir_list = []
		skipped_by_preview_filter = False
		progress_step = 100 / max(row_count, 1)
		band_controls = [
			(cfg.ui.checkBoxs_band_1, '01'), (cfg.ui.checkBoxs_band_2, '02'),
			(cfg.ui.checkBoxs_band_3, '03'), (cfg.ui.checkBoxs_band_4, '04'),
			(cfg.ui.checkBoxs_band_5, '05'), (cfg.ui.checkBoxs_band_6, '06'),
			(cfg.ui.checkBoxs_band_7, '07'), (cfg.ui.checkBoxs_band_8, '08'),
			(cfg.ui.checkBoxs_band_9, '8A'), (cfg.ui.checkBoxs_band_10, '09'),
			(cfg.ui.checkBoxs_band_11, '10'), (cfg.ui.checkBoxs_band_12, '11'),
			(cfg.ui.checkBoxs_band_13, '12')]
		try:
			for position, row in enumerate(rows):
				if cfg.actionCheck != 'Yes':
					return 'No'
				satellite = str(table.item(row, 0).text())
				if satellite not in cfg.satSentinelList:
					continue
				product_id = str(table.item(row, 12).text())
				product_name = str(table.item(row, 13).text())
				acquisition = str(table.item(row, 2).text())
				preview_layer_name = str(table.item(row, 1).text()) + '_p.jp2'
				if exporter == 'No' and cfg.ui.download_if_preview_in_legend_checkBox.isChecked() and cfg.utls.selectLayerbyName(preview_layer_name, 'Yes') is None:
					skipped_by_preview_filter = True
					continue
				level = 'L2A' if 'MSIL2A' in product_name else 'L1C'
				granule = self._cdseGranuleName(product_id, product_name)
				if not granule:
					return 'No'
				progress = min((position + 1) * progress_step, 100)
				out_dir = outputDirectory + '//' + granule + '_' + acquisition[:10]
				if exporter == 'No':
					if cfg.utls.makeDirectory(out_dir) is None:
						cfg.mx.msgErr58()
						return 'No'
					out_dir_list.append(out_dir)
					root_node = product_name + '.SAFE'
					mtd_name = 'MTD_MSIL2A.xml' if level == 'L2A' else 'MTD_MSIL1C.xml'
					metadata_url = self._cdseNodeUrl(product_id, root_node, mtd_name)
					if self.downloadFileSentinel2(metadata_url, out_dir + '//' + mtd_name, progress) == 'No':
						return 'No'
					tile_metadata_url = self._cdseNodeUrl(product_id, root_node, 'GRANULE', granule, 'MTD_TL.xml')
					tile_metadata_result = self.downloadFileSentinel2(tile_metadata_url, out_dir + '//MTD_TL.xml', progress)
					if tile_metadata_result == 'No' and cfg.actionCheck != 'Yes':
						return 'No'
					if cfg.ui.ancillary_data_checkBox.isChecked():
						qi_nodes = self._cdseListNodes(product_id, root_node, 'GRANULE', granule, 'QI_DATA')
						cloud_mask = next((node.get('Name', node.get('Id', '')) for node in qi_nodes if str(node.get('Name', node.get('Id', ''))).lower() == 'msk_clouds_b00.gml'), '')
						if cloud_mask:
							cloud_mask_url = self._cdseNodeUrl(product_id, root_node, 'GRANULE', granule, 'QI_DATA', cloud_mask)
							self.downloadFileSentinel2(cloud_mask_url, out_dir + '//' + cloud_mask, progress, optional=True)
				out_files = []
				for control, band in band_controls:
					self.checkImageBands(control, band, product_id, product_name, granule, acquisition, outputDirectory, exporter, progress, out_files, links)
					if cfg.actionCheck != 'Yes':
						break
				for item in out_files:
					cfg.shutilSCP.copy(item[0], item[1] + '.jp2')
					cfg.osSCP.remove(item[0])
					if cfg.ui.load_in_QGIS_checkBox.isChecked() and not cfg.ui.preprocess_checkBox.isChecked():
						cfg.utls.addRasterLayer(item[1] + '.jp2')
				if cfg.actionCheck != 'Yes':
					return 'No'
			if cfg.ui.preprocess_checkBox.isChecked() and exporter == 'No':
				for index, directory in enumerate(out_dir_list, start=1):
					cfg.uiUtls.updateBar(mainMessage=cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Processing') + ' [' + str(index) + '/' + str(len(out_dir_list)) + '] ' + cfg.osSCP.path.basename(directory), message='')
					cfg.sentinel2T.populateTable(directory, 'Yes')
					converted = directory + '_con'
					if cfg.utls.makeDirectory(converted) is None:
						cfg.mx.msgErr58()
						return 'No'
					cfg.sentinel2T.sentinel2(directory, converted, 'Yes')
			return links
		finally:
			cfg.uiUtls.removeProgressBar()
			cfg.cnvs.setRenderFlag(True)
			if skipped_by_preview_filter and not out_dir_list and exporter == 'No':
				self._cdseMessage('No Sentinel-2 products were downloaded because "Only if preview in Layers" is checked and no matching preview layer was found. Load the preview as a QGIS layer or uncheck that option.')


	def checkAllBandsSentinel2(self):
		if self.checkAll == 'Yes':
			for i in range(1, 14):
				t = 'cfg.ui.checkBoxs_band_' + str(i) + '.setCheckState(cfg.QtSCP.CheckState.Checked)'
				cfg.scp_eval(t, locals())
			cfg.ui.ancillary_data_checkBox.setCheckState(cfg.QtSCP.CheckState.Checked)
			self.checkAll = 'No'
		else:
			for i in range(1, 14):
				t = 'cfg.ui.checkBoxs_band_' + str(i) + '.setCheckState(cfg.QtSCP.CheckState.Unchecked)'
				cfg.scp_eval(t, locals())
			cfg.ui.ancillary_data_checkBox.setCheckState(cfg.QtSCP.CheckState.Unchecked)
			self.checkAll = 'Yes'
			
	# check all bands
	def checkAllBandsSentinel3(self):
		if self.checkAll == 'Yes':
			for i in range(1, 22):
				t = 'cfg.ui.checkBoxs3_band_' + str(i) + '.setCheckState(cfg.QtSCP.CheckState.Checked)'
				cfg.scp_eval(t, locals())
			cfg.ui.s3_ancillary_data_checkBox.setCheckState(cfg.QtSCP.CheckState.Checked)
			self.checkAll = 'No'
		else:
			for i in range(1, 22):
				t = 'cfg.ui.checkBoxs3_band_' + str(i) + '.setCheckState(cfg.QtSCP.CheckState.Unchecked)'
				cfg.scp_eval(t, locals())
			cfg.ui.s3_ancillary_data_checkBox.setCheckState(cfg.QtSCP.CheckState.Unchecked)
			self.checkAll = 'Yes'
			
	# check all bands
	def checkAllBandsGOES(self):
		if self.checkAll == 'Yes':
			for i in range(1, 7):
				t = 'cfg.ui.checkBoxs_goes_band_' + str(i) + '.setCheckState(cfg.QtSCP.CheckState.Checked)'
				cfg.scp_eval(t, locals())
			self.checkAll = 'No'
		else:
			for i in range(1, 7):
				t = 'cfg.ui.checkBoxs_goes_band_' + str(i) + '.setCheckState(cfg.QtSCP.CheckState.Unchecked)'
				cfg.scp_eval(t, locals())
			self.checkAll = 'Yes'
			
	# check band download
	def checkImageBands(self, checkbox, bandNumber, imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFilesList, linksList, checkDownload=None):
		if cfg.actionCheck != 'Yes' or not checkbox.isChecked():
			return
		level = 'L2A' if 'MSIL2A' in imgName else 'L1C'
		tile = imgName2.split('_')[1] if '_' in imgName2 else ''
		sensing_time = imgName.split('_')[2] if len(imgName.split('_')) > 2 else ''
		if level == 'L1C':
			filename = tile + '_' + sensing_time + '_B' + bandNumber + '.jp2'
			nodes = [imgName + '.SAFE', 'GRANULE', imgName2, 'IMG_DATA', filename]
			output_name = 'L1C_' + imgName2[4:] + '_B' + bandNumber
		else:
			if bandNumber in ['02', '03', '04', '08']:
				resolution = 'R10m'
				suffix = '_10m.jp2'
			elif bandNumber in ['05', '06', '07', '11', '12', '8A']:
				resolution = 'R20m'
				suffix = '_20m.jp2'
			elif bandNumber in ['01', '09']:
				resolution = 'R60m'
				suffix = '_60m.jp2'
			else:
				return
			filename = tile + '_' + sensing_time + '_B' + bandNumber + suffix
			nodes = [imgName + '.SAFE', 'GRANULE', imgName2, 'IMG_DATA', resolution, filename]
			output_name = imgName2[4:] + '_B' + bandNumber
		url = self._cdseNodeUrl(imgID, *nodes)
		if exporter == 'No':
			temp_file = cfg.tmpDir + '//' + filename
			if self.downloadFileSentinel2(url, temp_file, progress) == 'Yes':
				final_path = outputDirectory + '//' + imgName2 + '_' + acquisitionDate[:10] + '//' + output_name
				outFilesList.append([temp_file, final_path])
			else:
				if cfg.actionCheck == 'Yes':
					cfg.mx.msgWar23(filename)
		else:
			linksList.append(url)


	def downloadThumbnailSentinel2(self, imgID, min_lat, min_lon, max_lat, max_lon, imageJPG, progress=None, preview='No'):
		if not imageJPG:
			return 'No'
		im_out = cfg.tmpDir + '//' + imgID
		if self._cdseDownloadFile(imageJPG, im_out, progress) != 'Yes':
			return 'No'
		if preview == 'Yes':
			self.previewInLabel(im_out)
			return im_out
		self.onflyGeorefImage(im_out, im_out + '.vrt', min_lon, max_lon, min_lat, max_lat)
		return im_out


	def onflyGeorefImage(self, inputImage, outputVRT, min_lon, max_lon, min_lat, max_lat):
		cLon = (float(min_lon) + float(max_lon)) / 2
		cLat = (float(min_lat) + float(max_lat)) / 2
		# calculate UTM zone (adapted from http://stackoverflow.com/questions/9186496/determining-utm-zone-to-convert-from-longitude-latitude)
		zone = 1 + int((cLon + 180) / 6)
		# exceptions
		if cLon >= 3.0 and cLon < 12.0 and cLat >= 56.0 and cLat < 64.0:
			zone = 32
		elif cLon >= 0.0 and cLon < 9.0 and cLat >= 72.0 and cLat < 84.0:
			zone = 31
		elif cLon >= 9.0 and cLon < 21.0 and cLat >= 72.0 and cLat < 84.0:
			zone = 33
		elif cLon >= 21.0 and cLon < 33.0 and cLat >= 72.0 and cLat < 84.0:
			zone = 35		
		elif cLon >= 33.0 and cLon < 42.0 and cLat >= 72.0 and cLat < 84.0:
			zone = 37
		UL = cfg.qgisCoreSCP.QgsPointXY(float(min_lon), float(max_lat))
		LR = cfg.qgisCoreSCP.QgsPointXY(float(max_lon), float(min_lat))
		# WGS84 EPSG 4326
		wgsCrs = cfg.qgisCoreSCP.QgsCoordinateReferenceSystem()
		wgsCrs.createFromProj4('+proj=longlat +datum=WGS84 +no_defs')
		iCrs = cfg.qgisCoreSCP.QgsCoordinateReferenceSystem()
		iCrs.createFromProj4('+proj=utm +zone=' + str(zone) + ' +datum=WGS84 +units=m +no_defs')
		UL1 = cfg.utls.projectPointCoordinates(UL, wgsCrs, iCrs)
		LR1 = cfg.utls.projectPointCoordinates(LR, wgsCrs, iCrs)
		if UL1 != False and LR1 != False:
			cfg.utls.getGDALForMac()
			# georeference thumbnail
			a = cfg.gdalPath + 'gdal_translate -of VRT -a_ullr ' + str(UL1.x()) + ' ' + str(UL1.y()) + ' ' + str(LR1.x()) + ' ' + str(LR1.y()) + ' -a_srs "+proj=utm +zone=' + str(zone) + ' +datum=WGS84 +units=m +no_defs" ' + inputImage + ' ' + outputVRT
			if cfg.sysSCPNm != 'Windows':
				a = cfg.shlexSCP.split(a)
			try:
				if cfg.sysSCPNm == 'Windows':
					startupinfo = cfg.subprocessSCP.STARTUPINFO()
					startupinfo.dwFlags = cfg.subprocessSCP.STARTF_USESHOWWINDOW
					startupinfo.wShowWindow = cfg.subprocessSCP.SW_HIDE
					sP = cfg.subprocessSCP.Popen(a, shell=False, startupinfo = startupinfo, stdin = cfg.subprocessSCP.DEVNULL)
				else:
					sP = cfg.subprocessSCP.Popen(a, shell=False)
				sP.wait()
			# in case of errors
			except Exception as err:
				# logger
				cfg.utls.logCondition(str(__name__) + '-' + (cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
			# logger
			cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' onfly georef' + str(inputImage))
		else:
			cfg.mx.msgErr41()
	
### Sentinel-1

	# read database S1
	def queryDatabaseSentinel1(self):
		cfg.uiUtls.addProgressBar()
		cfg.uiUtls.updateBar(20, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching Copernicus Data Space ...'))
		cfg.QtWidgetsSCP.QApplication.instance().processEvents()
		return self._cdsePopulateResults('SENTINEL-1', 'SENTINEL-1')

	def displayGranulesSentinel1(self, row, progress, preview = 'No'):
		i = row
		tW = cfg.ui.download_images_tableWidget
		imgNm = str(tW.item(i, 1).text())
		acquisitionDate = str(tW.item(i, 2).text())
		imgID = imgNm + '_p.jpg'
		url = str(tW.item(i, 11).text())
		# image preview
		imOut = cfg.tmpDir + '//' + imgID
		if preview == 'Yes' and cfg.osSCP.path.isfile(imOut):
			self.previewInLabel(imOut)
			return imOut
		if cfg.osSCP.path.isfile(imOut  + '.vrt'):
			l = cfg.utls.selectLayerbyName(imgID)
			if l is not None:		
				cfg.utls.setLayerVisible(l, True)
				cfg.utls.moveLayerTop(l)
			else:
				r =cfg.utls.addRasterLayer(imOut, imgID)
		else:
			min_lat = str(tW.item(i, 6).text())
			min_lon = str(tW.item(i, 7).text())
			max_lat = str(tW.item(i, 8).text())
			max_lon = str(tW.item(i, 9).text())
			self.downloadThumbnailSentinel1(imgID, min_lat, min_lon, max_lat, max_lon, url, progress, preview)
			if cfg.osSCP.path.isfile(imOut + '.vrt'):
				r =cfg.utls.addRasterLayer(imOut + '.vrt', imgID)
				cfg.utls.setRasterColorComposite(r, 1, 2, 3)
		# logger
		cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' granules displayed')
	
	# download image preview
	def downloadThumbnailSentinel1(self, imgID, min_lat, min_lon, max_lat, max_lon, imageJPG, progress=None, preview='No'):
		if not imageJPG:
			return 'No'
		im_out = cfg.tmpDir + '//' + imgID
		if self._cdseDownloadFile(imageJPG, im_out, progress) != 'Yes':
			return 'No'
		if preview == 'Yes':
			self.previewInLabel(im_out)
			return im_out
		self.onflyGeorefImage(im_out, im_out + '.vrt', min_lon, max_lon, min_lat, max_lat)
		return im_out


	def downloadSentinel1Images(self, outputDirectory, exporter = 'No'):
		cfg.uiUtls.addProgressBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Downloading'), message = '')
		tW = cfg.ui.download_images_tableWidget
		outDirList = []
		imgList = []
		links = []
		rows = self._downloadRowIndices(tW)
		c = len(rows)
		if c == 0:
			cfg.uiUtls.removeProgressBar()
			cfg.cnvs.setRenderFlag(True)
			return []
		progressStep = 100 / c
		progress = 0
		# disable map canvas render for speed
		cfg.cnvs.setRenderFlag(False)
		outFiles = []
		for i in rows:
			sat = str(tW.item(i, 0).text())
			if cfg.actionCheck == 'Yes':
				if sat == cfg.esaSentinel1:
					imgName = str(tW.item(i, 13).text())
					acquisitionDate = str(tW.item(i, 2).text())
					orbit = str(tW.item(i, 3).text())
					relativeOrbit = str(tW.item(i, 4).text())
					sliceNumber = str(tW.item(i, 5).text())
					imgID = str(tW.item(i, 12).text())
					imgJp2 = imgName + '_p.jpg'
					if cfg.ui.download_if_preview_in_legend_checkBox.isChecked() and cfg.utls.selectLayerbyName(imgJp2, 'Yes') is None:
						pass
					else:
						# add info to name
						try:
							imgName = imgName.replace('.zip', '') + '_s' + orbit[0] + '_' + relativeOrbit + '_' + sliceNumber + '_' + acquisitionDate[0:10]
						except:
							imgName = imgName.replace('.zip', '')
						outDirList.append(outputDirectory + '//' + imgName)
						progress = progress + progressStep
						if exporter == 'No':
							oDir = cfg.utls.makeDirectory(outputDirectory + '//' + imgName)
							if oDir is None:
								cfg.mx.msgErr58()
								cfg.uiUtls.removeProgressBar()
								cfg.cnvs.setRenderFlag(True)
								return 'No'
						# download ancillary data
						if cfg.ui.ancillary_data_checkBox.isChecked():
							pass
						# download bands
						self.checkImageS1Bands(None, None, imgID, imgName, None, acquisitionDate,outputDirectory + '//' + imgName, exporter, progress, outFiles, links)
						for oFile in outFiles:
							cfg.shutilSCP.copy(oFile[0], oFile[1])
							cfg.osSCP.remove(oFile[0])
			else:
				cfg.uiUtls.removeProgressBar()
				cfg.cnvs.setRenderFlag(True)
				return 'No'
		if cfg.ui.preprocess_checkBox.isChecked() and exporter == 'No':
			n = len(outFiles)
			i = 0
			for oFile in outFiles:
				if cfg.actionCheck == 'Yes':
					d = oFile[1]
					o = oFile[2] + '_con'
					i = i + 1
					cfg.uiUtls.updateBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Processing') + ' [' + str(i) + '/' + str(n) + '] ' + cfg.osSCP.path.basename(d), message = '')
					oDir = cfg.utls.makeDirectory(o)
					if oDir is None:
						cfg.mx.msgErr58()
						cfg.uiUtls.removeProgressBar()
						cfg.cnvs.setRenderFlag(True)
						return 'No'
					cfg.sentinel1T.sentinel1(d, o, 'Yes')
		cfg.uiUtls.removeProgressBar()
		cfg.cnvs.setRenderFlag(True)
		return links
		
	# check band download
	def checkImageS1Bands(self, checkbox, bandNumber, imgID, imgName, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFilesList, linksList):
		if cfg.actionCheck != 'Yes':
			return
		url = self._cdseProductsUrl() + '(' + str(imgID) + ')/$value'
		temp_file = cfg.tmpDir + '//' + imgName + '.zip'
		copy_file = outputDirectory + '//' + imgName + '.zip'
		if exporter == 'No':
			if self.downloadFileSentinel1(url, temp_file, progress) == 'No':
				return 'No'
			outFilesList.append([temp_file, copy_file, outputDirectory])
		else:
			linksList.append(url)


	def downloadFileSentinel1(self, url, output, progress=None):
		return output if self._cdseDownloadFile(url, output, progress) == 'Yes' else 'No'


	def downloadMetadataASTER(self):
		listImgID = []
		QdateFrom = cfg.ui.dateEdit_from.date()
		QdateTo = cfg.ui.dateEdit_to.date()
		dateFrom = QdateFrom.toPyDate().strftime('%Y-%m-%d') 
		dateTo = QdateTo.toPyDate().strftime('%Y-%m-%d') 
		maxCloudCover = int(cfg.ui.cloud_cover_spinBox.value())
		resultNum = int(cfg.ui.result_number_spinBox_2.value())
		sat = cfg.ui.landsat_satellite_combo.currentText()
		if sat == cfg.usgsASTER:
			NASAcollection = cfg.NASAASTERCollection
		imageFindList = []
		if len(cfg.ui.imageID_lineEdit.text()) > 0:
			imgIDLine = cfg.ui.imageID_lineEdit.text()
			imgIDLineSplit = str(imgIDLine).replace(' ', '').split(';')
			if len(imgIDLineSplit) == 1:
				imgIDLineSplit = str(imgIDLine).replace(' ', '').split(',')
			for m in imgIDLineSplit:
				imageFindList.append(m.lower())
		try:
			rubbRect = cfg.qgisCoreSCP.QgsRectangle(float(cfg.ui.UX_lineEdit_3.text()), float(cfg.ui.UY_lineEdit_3.text()), float(cfg.ui.LX_lineEdit_3.text()), float(cfg.ui.LY_lineEdit_3.text()))
		except Exception as err:
			# logger
			cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), " ERROR exception: " + str(err))
			cfg.mx.msg23()
			return 'No'
		try:
			cfg.uiUtls.addProgressBar()
			cfg.QtWidgetsSCP.QApplication.instance().processEvents()
			tW = cfg.ui.download_images_tableWidget
			tW.setSortingEnabled(False)
			cfg.uiUtls.updateBar(30, cfg.QtWidgetsSCP.QApplication.translate("semiautomaticclassificationplugin", "Searching ..."))
			searchUrl = 'https://cmr.earthdata.nasa.gov/search/granules.echo10?bounding_box=' + cfg.ui.UX_lineEdit_3.text() + '%2C' + cfg.ui.LY_lineEdit_3.text() + '%2C' + cfg.ui.LX_lineEdit_3.text() + '%2C' + cfg.ui.UY_lineEdit_3.text() + '&echo_collection_id=' + NASAcollection + '&temporal=' + dateFrom + '%2C' + dateTo + 'T23%3A59%3A59.000Z&cloud_cover=0,' + str(maxCloudCover) + '&sort_key%5B%5D=-start_date&page_size=' + str(resultNum) + '&pretty=true'
			# connect and search
			searchResult = cfg.utls.NASASearch(searchUrl)
			xmlFile = searchResult.read()
			imgIDList = []
			doc = cfg.minidomSCP.parseString(xmlFile)
			entries = doc.getElementsByTagName("Granule")
			pages = len(entries)
			page = 0
			for entry in entries:
				page = page + 1
				cfg.uiUtls.updateBar(30 + int(page * 70 / pages), cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching ...'))
				gId = entry.getElementsByTagName('ProducerGranuleId')[0]
				imgID = gId.firstChild.data
				if imgID not in imgIDList:
					imgIDList.append(imgID)
					imgDispID = imgID
					cc = entry.getElementsByTagName('QAPercentCloudCover')[0]
					cloudCover = cc.firstChild.data
					on = entry.getElementsByTagName('OnlineResources')
					urls = on[0].getElementsByTagName('URL')
					imgPreview = ''
					for ur in urls:
						url = ur.firstChild.data
						if '.jpg' in url:
							imgPreview = url
							break
					dt = entry.getElementsByTagName('SingleDateTime')[0]
					imgDate = dt.firstChild.data
					imgDate = cfg.datetimeSCP.datetime.strptime(imgDate[0:19], '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
					PointLatitude = entry.getElementsByTagName('PointLatitude')
					lat = []
					for latit in PointLatitude:
						lat.append(float(latit.firstChild.data))
					PointLongitude = entry.getElementsByTagName('PointLongitude')
					lon = []
					for longi in PointLongitude:
						lon.append(float(longi.firstChild.data))
					DayNightFlag = entry.getElementsByTagName('DayNightFlag')[0]
					dayNight = DayNightFlag.firstChild.data
					listImgID.append([imgID, imgDate, cloudCover, imgDispID, dayNight, lon, lat, imgPreview.replace('http:', 'https:')])
			cfg.uiUtls.updateBar(100, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching ...'))
			c = tW.rowCount()
			for imID in listImgID:
				if len(imageFindList) > 0:
					for iF in imageFindList:
						if iF in imID[0].lower():
							imgCheck = 'Yes'
							break
						else:
							imgCheck = 'No'
				else:
					imgCheck = 'Yes'
				if imgCheck == 'Yes':
					c = tW.rowCount()
					# add list items to table
					tW.setRowCount(c + 1)
					cfg.utls.addTableItem(tW, sat, c, 0)					
					cfg.utls.addTableItem(tW, imID[3], c, 1)
					cfg.utls.addTableItem(tW, str(imID[1]), c, 2)
					cfg.utls.addTableItem(tW, int(round(float(imID[2]))), c, 3)
					cfg.utls.addTableItem(tW, "", c, 4)
					cfg.utls.addTableItem(tW, imID[4], c, 5)
					min_lon = min(imID[5])
					max_lon = max(imID[5])
					min_lat = min(imID[6])
					max_lat = max(imID[6])
					cfg.utls.addTableItem(tW, float(min_lat), c, 6)
					cfg.utls.addTableItem(tW, float(min_lon), c, 7)
					cfg.utls.addTableItem(tW, float(max_lat), c, 8)
					cfg.utls.addTableItem(tW,float(max_lon), c, 9)
					cfg.utls.addTableItem(tW,'EOSDIS Earthdata', c, 10)
					cfg.utls.addTableItem(tW, imID[7], c, 11)
					cfg.utls.addTableItem(tW, NASAcollection, c, 12)
					cfg.utls.addTableItem(tW, imID[0], c, 13)
			tW.setSortingEnabled(True)	
			cfg.uiUtls.removeProgressBar()
			self.clearCanvasPoly()
			# logger
			cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ASTER images')
			c = tW.rowCount()
			if c == 0:
				cfg.mx.msg21()
		except Exception as err:
			cfg.mx.msgErr39()
			cfg.uiUtls.removeProgressBar()
			# logger
			cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
	
	# user
	def rememberUserEarthdata(self):
		if cfg.ui.remember_user_checkBox_3.isChecked():
			user = cfg.ui.user_usgs_lineEdit_2.text()
			pswd = cfg.utls.encryptPassword(cfg.ui.password_usgs_lineEdit_2.text())
			cfg.utls.setQGISRegSetting(cfg.regUSGSUserASTER, user)
			cfg.utls.setQGISRegSetting(cfg.regUSGSPassASTER, pswd)
			
	def rememberUserCheckboxEarthdata(self):
		if cfg.ui.remember_user_checkBox_3.isChecked():
			self.rememberUserEarthdata()
		else:
			cfg.utls.setQGISRegSetting(cfg.regUSGSUserASTER, "")
			cfg.utls.setQGISRegSetting(cfg.regUSGSPassASTER, "")
			
		
	# download ASTER data
	def downloadASTERImages(self, outputDirectory, exporter = 'No'):
		cfg.uiUtls.addProgressBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Downloading'), message = '')
		tW = cfg.ui.download_images_tableWidget
		rows = self._downloadRowIndices(tW)
		c = len(rows)
		if c == 0:
			cfg.uiUtls.removeProgressBar()
			return []
		progressStep = 100 / c
		progressStep2 = progressStep/12
		progress = 0
		outDirList = []
		outFileList = []
		imgList = []
		links = []		
		for i in rows:
			sat = str(tW.item(i, 0).text())
			if cfg.actionCheck == 'Yes':
				if sat in cfg.satASTERtList:
					imgID = str(tW.item(i, 13).text())
					imgDispID = str(tW.item(i, 1).text())
					date = str(tW.item(i, 2).text())[0:10]
					if cfg.ui.download_if_preview_in_legend_checkBox.isChecked() and cfg.utls.selectLayerbyName(imgDispID, 'Yes') is None:
						pass
					else:
						NASAcollection = str(tW.item(i, 12).text())
						outDir = outputDirectory + '/' + imgDispID
						if exporter == 'No':
							oDir = cfg.utls.makeDirectory(outDir)
							if oDir is None:
								cfg.mx.msgErr58()
								cfg.uiUtls.removeProgressBar()
								return 'No'
						outDirList.append(outDir)
						outFileList.append(outDir + '//' + imgDispID + '.hdf')
						progress = progress + progressStep
						outUrl = self.downloadASTERImagesFromNASA(imgID, NASAcollection, imgDispID, outDir, progress, exporter, date)
						links.append(outUrl)
			else:
				cfg.uiUtls.removeProgressBar()
				return 'No'
		if exporter == 'Yes':
			return links
		else:
			cfg.cnvs.setRenderFlag(False)
			if cfg.ui.preprocess_checkBox.isChecked():
				n = len(outFileList)
				i = 0
				for d in outFileList:
					i = i + 1
					cfg.uiUtls.updateBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Processing') + ' [' + str(i) + '/' + str(n) + '] ' + cfg.osSCP.path.basename(d), message = '')
					if cfg.actionCheck == 'Yes':
						cfg.ASTERT.populateTable(d, 'Yes')
						o = d + '_converted'
						oDir = cfg.utls.makeDirectory(o)
						cfg.ASTERT.ASTER(d, o, 'Yes')
			elif cfg.ui.load_in_QGIS_checkBox.isChecked():
				for d in outDirList:
					try:
						for f in cfg.osSCP.listdir(d):
							if f.lower().endswith('.tif'):
								r =cfg.utls.addRasterLayer(d + '/' + f)
					except Exception as err:
						# logger
						cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
			cfg.uiUtls.removeProgressBar()
			cfg.cnvs.setRenderFlag(True)
			
	# download image
	def downloadASTERImagesFromNASA(self, imageID, collection, imageDisplayID, outputDirectory, progress, exporter = 'No', date = None):
		# The ASTER L1T data products are retrieved from the online Data Pool, courtesy of the NASA Land Processes Distributed Active Archive Center (LP DAAC), USGS/Earth Resources Observation and Science (EROS) Center, Sioux Falls, South Dakota, https://lpdaac.usgs.gov/data_access/data_pool'
		url = 'https://e4ftl01.cr.usgs.gov/ASTT/AST_L1T.003/' + date.replace('-', '.')+ '/' + imageDisplayID + '.hdf'
		if exporter == 'Yes':
			return url
		else:
			user = cfg.ui.user_usgs_lineEdit_2.text()
			password =cfg.ui.password_usgs_lineEdit_2.text()
			try:
				imgID = imageDisplayID + '.hdf'
				check = cfg.utls.passwordConnectPython(user, password, url, 'urs.earthdata.nasa.gov', cfg.tmpDir + '//' + imgID, progress)
				if str(check) == 'Cancel action':
					return check
				if cfg.osSCP.path.getsize(cfg.tmpDir + '//' + imgID) > 10000:
					if collection == cfg.NASAASTERCollection:
						cfg.shutilSCP.copy(cfg.tmpDir + '//' + imgID, outputDirectory + '//' + imgID)
						cfg.osSCP.remove(cfg.tmpDir + '//' + imgID)
					else:
						tarFiles = cfg.tarfileSCP.open(cfg.tmpDir + '//' + imgID, 'r:gz')
						tarFiles.extractall(outputDirectory, filter="data")
						tarFiles.close()
						cfg.osSCP.remove(cfg.tmpDir + '//' + imgID)
						return url
				else:
					cfg.mx.msgErr55(imgID)
					return 'No'
			except Exception as err:
				cfg.mx.msgErr55(imgID)
				# logger
				cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
				return 'No'
	
### GOES

	# download image metadata from Amazon Web Services https://registry.opendata.aws/noaa-goes/
	def downloadMetadataGOES(self):
		QdateFrom = cfg.ui.dateEdit_from.date()
		dStrT = QdateFrom.toPyDate().timetuple()
		# calculate julian day
		fromDay = dStrT.tm_yday
		fromYear = dStrT.tm_year
		QdateTo = cfg.ui.dateEdit_to.date()
		dStrTo = QdateTo.toPyDate().timetuple()
		# calculate julian day
		toDay = dStrTo.tm_yday
		toYear = dStrTo.tm_year
		if fromYear != toYear:
			cfg.mx.msgWar34()
		resultNum = int(cfg.ui.result_number_spinBox_2.value())
		sat = cfg.ui.landsat_satellite_combo.currentText()
		if sat == cfg.goes16:
			goesCol = 'https://noaa-goes16.s3.amazonaws.com'
		elif sat == cfg.goes17:
			goesCol = 'https://noaa-goes17.s3.amazonaws.com'
		imageFindList = []
		if len(cfg.ui.imageID_lineEdit.text()) > 0:
			imgIDLine = cfg.ui.imageID_lineEdit.text()
			imgIDLineSplit = str(imgIDLine).replace(' ', '').split(';')
			if len(imgIDLineSplit) == 1:
				imgIDLineSplit = str(imgIDLine).replace(' ', '').split(',')
			for m in imgIDLineSplit:
				imageFindList.append(m.lower())
		else:
			imageFindList.append('l1b')
		cfg.uiUtls.addProgressBar()
		cfg.QtWidgetsSCP.QApplication.instance().processEvents()
		tW = cfg.ui.download_images_tableWidget
		tW.setSortingEnabled(False)
		cfg.uiUtls.updateBar(30, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching ...'))
		# iterat days
		dCount = 0
		for day in range(fromDay, toDay + 1):
			if cfg.actionCheck == 'Yes':
				dCount = dCount + 1
				if dCount < resultNum:
					# iterate hours
					for hour in range(0, 24):
						if cfg.actionCheck == 'Yes':
							cfg.uiUtls.updateBar(30 + int(hour * 70 / 24), cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching ... [day ' + str(day) + ']'))
							searchUrl = goesCol + '/?list-type=2&delimiter=/&prefix=ABI-L1b-RadF/' + str(fromYear) + '/' + str(day).zfill(3) + '/' + str(hour).zfill(2) + '/'
							# connect and search
							xml2T = cfg.utls.createTempRasterPath('xml')
							searchResult = cfg.utls.downloadFile(searchUrl, xml2T)
							xmlFile = open(xml2T, 'r').read()
							imgIDList = []
							doc = cfg.minidomSCP.parseString(xmlFile)
							entries = doc.getElementsByTagName('Key')
							for entry in entries:
								if cfg.actionCheck == 'Yes':
									imgID = entry.firstChild.data
									if 'C01' in imgID:
										for imF in imageFindList:
											if imF in imgID.lower():
												c = tW.rowCount()
												inDate = cfg.datetimeSCP.datetime.strptime(imgID.split('_s')[1][0:13],  '%Y%j%H%M%S').strftime('%Y.%m.%dT%H_%M_%S')
												# add list items to table
												tW.setRowCount(c + 1)
												cfg.utls.addTableItem(tW, sat, c, 0)
												cfg.utls.addTableItem(tW, imgID.split('/')[-1], c, 1)
												cfg.utls.addTableItem(tW, str(inDate), c, 2)
												cfg.utls.addTableItem(tW, '', c, 3)
												cfg.utls.addTableItem(tW, '', c, 4)
												cfg.utls.addTableItem(tW, '', c, 5)
												cfg.utls.addTableItem(tW, '', c, 6)
												cfg.utls.addTableItem(tW, '', c, 7)
												cfg.utls.addTableItem(tW, '', c, 8)
												cfg.utls.addTableItem(tW, '', c, 9)
												cfg.utls.addTableItem(tW,'AWS', c, 10)
												cfg.utls.addTableItem(tW, '', c, 11)
												cfg.utls.addTableItem(tW, imgID.split('_s')[1][0:14], c, 12)
												cfg.utls.addTableItem(tW, searchUrl, c, 13)
		tW.setSortingEnabled(True)
		cfg.uiUtls.removeProgressBar()
		self.clearCanvasPoly()
		# logger
		cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' GOES images')
		c = tW.rowCount()
		if c == 0:
			cfg.mx.msg21()
			
	# download images
	def downloadGOESImages(self, outputDirectory, exporter = 'No'):
		cfg.uiUtls.addProgressBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Downloading'), message = '')
		tW = cfg.ui.download_images_tableWidget
		outDirList = []
		imgList = []
		links = []
		rows = self._downloadRowIndices(tW)
		c = len(rows)
		if c == 0:
			cfg.uiUtls.removeProgressBar()
			cfg.cnvs.setRenderFlag(True)
			return []
		progressStep = 100 / c
		progress = 0
		# disable map canvas render for speed
		cfg.cnvs.setRenderFlag(False)
		for i in rows:
			sat = str(tW.item(i, 0).text())
			if cfg.actionCheck == 'Yes':
				if sat == cfg.goes16 or sat == cfg.goes17:
					imgID = str(tW.item(i, 1).text())
					acquisitionDate = str(tW.item(i, 2).text())
					imgName2 = str(tW.item(i, 12).text())
					searchUrl = str(tW.item(i, 13).text())
					if cfg.ui.download_if_preview_in_legend_checkBox.isChecked():
						pass
					else:
						outFiles = []
						outDirList.append(outputDirectory + '//' + imgID[0:25]  + '_' + acquisitionDate)
						progress = progress + progressStep
						if exporter == 'No':
							oDir = cfg.utls.makeDirectory(outputDirectory + '//' + imgID[0:25]  + '_' + acquisitionDate)
							if oDir is None:
								cfg.mx.msgErr58()
								cfg.uiUtls.removeProgressBar()
								cfg.cnvs.setRenderFlag(True)
								return 'No'
						# download bands
						self.checkGOESImageBands(cfg.ui.checkBoxs_goes_band_1, '01', imgID, searchUrl, imgName2, acquisitionDate, outputDirectory + '//' + imgID[0:25]  + '_' + acquisitionDate, exporter, progress, outFiles, links)
						self.checkGOESImageBands(cfg.ui.checkBoxs_goes_band_2, '02', imgID, searchUrl, imgName2, acquisitionDate, outputDirectory + '//' + imgID[0:25]  + '_' + acquisitionDate, exporter, progress, outFiles, links)
						self.checkGOESImageBands(cfg.ui.checkBoxs_goes_band_3, '03', imgID, searchUrl, imgName2, acquisitionDate, outputDirectory + '//' + imgID[0:25]  + '_' + acquisitionDate, exporter, progress, outFiles, links)
						self.checkGOESImageBands(cfg.ui.checkBoxs_goes_band_4, '04', imgID, searchUrl, imgName2, acquisitionDate, outputDirectory + '//' + imgID[0:25]  + '_' + acquisitionDate, exporter, progress, outFiles, links)
						self.checkGOESImageBands(cfg.ui.checkBoxs_goes_band_5, '05', imgID, searchUrl, imgName2, acquisitionDate, outputDirectory + '//' + imgID[0:25]  + '_' + acquisitionDate, exporter, progress, outFiles, links)
						self.checkGOESImageBands(cfg.ui.checkBoxs_goes_band_6, '06', imgID, searchUrl, imgName2, acquisitionDate, outputDirectory + '//' + imgID[0:25]  + '_' + acquisitionDate, exporter, progress, outFiles, links)
						for oFile in outFiles:
							cfg.shutilSCP.copy(oFile[0], oFile[1])
							cfg.osSCP.remove(oFile[0])
			else:
				cfg.uiUtls.removeProgressBar()
				cfg.cnvs.setRenderFlag(True)
				return 'No'
		if cfg.ui.preprocess_checkBox.isChecked() and exporter == 'No':
			n = len(outDirList)
			i = 0
			for d in outDirList:
				i = i + 1
				cfg.uiUtls.updateBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Processing') + ' [' + str(i) + '/' + str(n) + '] ' + cfg.osSCP.path.basename(d), message = '')
				if cfg.actionCheck == 'Yes':
					cfg.goesT.populateTable(d, 'Yes')
					o = d + "_con"
					oDir = cfg.utls.makeDirectory(o)
					if oDir is None:
						cfg.mx.msgErr58()
						cfg.uiUtls.removeProgressBar()
						cfg.cnvs.setRenderFlag(True)
						return 'No'
					cfg.goesT.GOES(d, o, 'Yes')
		cfg.uiUtls.removeProgressBar()
		cfg.cnvs.setRenderFlag(True)
		return links
					
	# check band download
	def checkGOESImageBands(self, checkbox, bandNumber, imgName, searchUrl, imgName2, acquisitionDate, outputDirectory, exporter, progress, outFilesList, linksList):
		if cfg.actionCheck == 'Yes':
			if checkbox.isChecked():
				# connect and search
				xml2T = cfg.utls.createTempRasterPath('xml')
				searchResult = cfg.utls.downloadFile(searchUrl, xml2T)
				xmlFile = open(xml2T, 'r').read()
				imgIDList = []
				doc = cfg.minidomSCP.parseString(xmlFile)
				entries = doc.getElementsByTagName('Key')
				for entry in entries:
					imgID = entry.firstChild.data
					if 'C' + str(bandNumber) in imgID and imgName2 in imgID:
						outFile = cfg.tmpDir + '//' + imgName[0:25] + '_' + acquisitionDate+ '_B' + bandNumber + '.nc'
						outCopyFile = outputDirectory + '//' + imgName[0:25]  + '_' + acquisitionDate + '_B' + bandNumber + '.nc'
						urlL = searchUrl.split('?')[0] + imgID
						if exporter == 'No':
							cfg.utls.downloadFile(urlL, outFile)
							outFilesList.append([outFile, outCopyFile])
						else:
							linksList.append(urlL)
		else:
			cfg.uiUtls.removeProgressBar()
			return 'No'
			
			
### MODIS

	# download image metadata from NASA CMR Search https://cmr.earthdata.nasa.gov/search/site/search_api_docs.html
	def downloadMetadataMODIS(self):
		listImgID = []
		QdateFrom = cfg.ui.dateEdit_from.date()
		QdateTo = cfg.ui.dateEdit_to.date()
		dateFrom = QdateFrom.toPyDate().strftime("%Y-%m-%d") 
		dateTo = QdateTo.toPyDate().strftime("%Y-%m-%d") 
		maxCloudCover = int(cfg.ui.cloud_cover_spinBox.value())
		resultNum = int(cfg.ui.result_number_spinBox_2.value())
		sat = cfg.ui.landsat_satellite_combo.currentText()
		if sat == cfg.usgsMODIS_MOD09GQ:
			NASAcollection = cfg.NASAMOD09GQCollection
		elif sat == cfg.usgsMODIS_MYD09GQ:
			NASAcollection = cfg.NASAMYD09GQCollection
		elif sat == cfg.usgsMODIS_MOD09GA:
			NASAcollection = cfg.NASAMOD09GACollection
		elif sat == cfg.usgsMODIS_MYD09GA:
			NASAcollection = cfg.NASAMYD09GACollection
		elif sat == cfg.usgsMODIS_MOD09Q1:
			NASAcollection = cfg.NASAMOD09Q1Collection
		elif sat == cfg.usgsMODIS_MYD09Q1:
			NASAcollection = cfg.NASAMYD09Q1Collection
		elif sat == cfg.usgsMODIS_MOD09A1:
			NASAcollection = cfg.NASAMOD09A1Collection
		elif sat == cfg.usgsMODIS_MYD09A1:
			NASAcollection = cfg.NASAMYD09A1Collection
		imageFindList = []
		if len(cfg.ui.imageID_lineEdit.text()) > 0:
			imgIDLine = cfg.ui.imageID_lineEdit.text()
			imgIDLineSplit = str(imgIDLine).replace(' ', '').split(';')
			if len(imgIDLineSplit) == 1:
				imgIDLineSplit = str(imgIDLine).replace(' ', '').split(',')
			for m in imgIDLineSplit:
				imageFindList.append(m.lower())
		try:
			rubbRect = cfg.qgisCoreSCP.QgsRectangle(float(cfg.ui.UX_lineEdit_3.text()), float(cfg.ui.UY_lineEdit_3.text()), float(cfg.ui.LX_lineEdit_3.text()), float(cfg.ui.LY_lineEdit_3.text()))
		except Exception as err:
			# logger
			cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
			cfg.mx.msg23()
			return 'No'
		try:
			cfg.uiUtls.addProgressBar()
			cfg.QtWidgetsSCP.QApplication.instance().processEvents()
			tW = cfg.ui.download_images_tableWidget
			tW.setSortingEnabled(False)
			cfg.uiUtls.updateBar(30, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching ...'))
			# issue with cloud cover search
			#searchUrl = 'https://cmr.earthdata.nasa.gov/search/granules.echo10?bounding_box=' + cfg.ui.UX_lineEdit_3.text() + '%2C' + cfg.ui.LY_lineEdit_3.text() + '%2C' + cfg.ui.LX_lineEdit_3.text() + '%2C' + cfg.ui.UY_lineEdit_3.text() + '&echo_collection_id=' + NASAcollection + '&temporal=' + dateFrom + '%2C' + dateTo + 'T23%3A59%3A59.000Z&cloud_cover=0,' + str(maxCloudCover) + '&sort_key%5B%5D=-start_date&page_size=' + str(resultNum) + '&pretty=true'
			searchUrl = 'https://cmr.earthdata.nasa.gov/search/granules.echo10?bounding_box=' + cfg.ui.UX_lineEdit_3.text() + '%2C' + cfg.ui.LY_lineEdit_3.text() + '%2C' + cfg.ui.LX_lineEdit_3.text() + '%2C' + cfg.ui.UY_lineEdit_3.text() + '&echo_collection_id=' + NASAcollection + '&temporal=' + dateFrom + '%2C' + dateTo + 'T23%3A59%3A59.000Z&sort_key%5B%5D=-start_date&page_size=' + str(resultNum) + '&pretty=true'
			# connect and search
			searchResult = cfg.utls.NASASearch(searchUrl)
			xmlFile = searchResult.read()
			imgIDList = []
			doc = cfg.minidomSCP.parseString(xmlFile)
			entries = doc.getElementsByTagName('Granule')
			pages = len(entries)
			page = 0
			for entry in entries:
				page = page + 1
				cfg.uiUtls.updateBar(30 + int(page * 70 / pages), cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching ...'))
				gId = entry.getElementsByTagName('ProducerGranuleId')[0]
				imgID = gId.firstChild.data
				if imgID not in imgIDList:
					imgIDList.append(imgID)
					imgDispID = imgID.replace('.hdf', '')
					#cc = entry.getElementsByTagName("QAPercentCloudCover")[0]
					#cloudCover = cc.firstChild.data
					cloudCover = 0
					on = entry.getElementsByTagName('OnlineResources')
					url = on[0].getElementsByTagName('URL')[1]
					imgPreview = url.firstChild.data
					# in case of missing preview
					if not imgPreview.lower().endswith('.jpg'):
						inTime = entry.getElementsByTagName('InsertTime')[0]
						inDate = inTime.firstChild.data
						inDate = cfg.datetimeSCP.datetime.strptime(inDate[0:19], '%Y-%m-%dT%H:%M:%S').strftime('%Y.%m.%d')
						imgPreview = 'https://e4ftl01.cr.usgs.gov/WORKING/BRWS/Browse.001/' + inDate + '/BROWSE.' + imgDispID.replace('GQ', 'GA') + '.1.jpg'
					dt = entry.getElementsByTagName('BeginningDateTime')[0]
					imgDate = dt.firstChild.data
					imgDate = cfg.datetimeSCP.datetime.strptime(imgDate[0:19], '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
					PointLatitude = entry.getElementsByTagName('PointLatitude')
					lat = []
					for latit in PointLatitude:
						lat.append(float(latit.firstChild.data))
					PointLongitude = entry.getElementsByTagName('PointLongitude')
					lon = []
					for longi in PointLongitude:
						pppLon = float(longi.firstChild.data)
						if pppLon < -170:
							pppLon = 180 + (180 + pppLon)
						lon.append(pppLon)
					DayNightFlag = entry.getElementsByTagName('DayNightFlag')[0]
					dayNight = DayNightFlag.firstChild.data
					listImgID.append([imgID, imgDate, cloudCover, imgDispID, dayNight, lon, lat, imgPreview.replace('http:', 'https:')])
			cfg.uiUtls.updateBar(100, cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Searching ...'))
			c = tW.rowCount()
			for imID in listImgID:
				if len(imageFindList) > 0:
					for iF in imageFindList:
						if iF in imID[0].lower():
							imgCheck = 'Yes'
							break
						else:
							imgCheck = 'No'
				else:
					imgCheck = 'Yes'
				if imgCheck == 'Yes':
					c = tW.rowCount()
					# add list items to table
					tW.setRowCount(c + 1)
					cfg.utls.addTableItem(tW, sat, c, 0)
					cfg.utls.addTableItem(tW, imID[3], c, 1)
					cfg.utls.addTableItem(tW, str(imID[1]), c, 2)
					cfg.utls.addTableItem(tW, int(round(float(imID[2]))), c, 3)
					cfg.utls.addTableItem(tW, '', c, 4)
					cfg.utls.addTableItem(tW, imID[4], c, 5)
					min_lon = min(imID[5])
					max_lon = max(imID[5])
					min_lat = min(imID[6])
					max_lat = max(imID[6])
					cfg.utls.addTableItem(tW, float(min_lat), c, 6)
					cfg.utls.addTableItem(tW, float(min_lon), c, 7)
					cfg.utls.addTableItem(tW, float(max_lat), c, 8)
					cfg.utls.addTableItem(tW,float(max_lon), c, 9)
					cfg.utls.addTableItem(tW,'EOSDIS Earthdata', c, 10)
					cfg.utls.addTableItem(tW, imID[7], c, 11)
					cfg.utls.addTableItem(tW, NASAcollection, c, 12)
					cfg.utls.addTableItem(tW, imID[0], c, 13)
			tW.setSortingEnabled(True)	
			cfg.uiUtls.removeProgressBar()
			self.clearCanvasPoly()
			# logger
			cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' MODIS images')
			c = tW.rowCount()
			if c == 0:
				cfg.mx.msg21()
		except Exception as err:
			cfg.mx.msgErr39()
			cfg.uiUtls.removeProgressBar()
			# logger
			cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), " ERROR exception: " + str(err))
			
	# download MODIS data
	def downloadMODISImages(self, outputDirectory, exporter = 'No'):
		cfg.uiUtls.addProgressBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Downloading'), message = '')
		tW = cfg.ui.download_images_tableWidget
		rows = self._downloadRowIndices(tW)
		c = len(rows)
		if c == 0:
			cfg.uiUtls.removeProgressBar()
			return []
		progressStep = 100 / c
		progressStep2 = progressStep/12
		progress = 0
		outDirList = []
		outFileList = []
		imgList = []
		links = []		
		for i in rows:
			sat = str(tW.item(i, 0).text())
			if cfg.actionCheck == 'Yes':
				if sat in cfg.satMODIStList:
					imgID = str(tW.item(i, 13).text())
					imgDispID = str(tW.item(i, 1).text())
					date = str(tW.item(i, 2).text())[0:10]
					if cfg.ui.download_if_preview_in_legend_checkBox.isChecked() and cfg.utls.selectLayerbyName(imgDispID, 'Yes') is None:
						pass
					else:
						NASAcollection = str(tW.item(i, 12).text())
						outDir = outputDirectory + "/" + imgDispID
						if exporter == 'No':
							oDir = cfg.utls.makeDirectory(outDir)
							if oDir is None:
								cfg.mx.msgErr58()
								cfg.uiUtls.removeProgressBar()
								return 'No'
						outDirList.append(outDir)
						outFileList.append(outDir + "//" + imgDispID + ".hdf")
						progress = progress + progressStep
						outUrl = self.downloadMODISImagesFromNASA(imgID, NASAcollection, imgDispID, outDir, progress, exporter, date)
						links.append(outUrl)
			else:
				cfg.uiUtls.removeProgressBar()
				return 'No'
		if exporter == 'Yes':
			return links
		else:
			cfg.cnvs.setRenderFlag(False)
			if cfg.ui.preprocess_checkBox.isChecked():
				n = len(outFileList)
				i = 0
				for d in outFileList:
					i = i + 1
					cfg.uiUtls.updateBar(mainMessage = cfg.QtWidgetsSCP.QApplication.translate('semiautomaticclassificationplugin', 'Processing') + ' [' + str(i) + '/' + str(n) + '] ' + cfg.osSCP.path.basename(d), message = '')
					if cfg.actionCheck == 'Yes':
						cfg.MODIST.populateTable(d, 'Yes')
						o = d + '_converted'
						oDir = cfg.utls.makeDirectory(o)
						cfg.MODIST.MODIS(d, o, 'Yes')
			elif cfg.ui.load_in_QGIS_checkBox.isChecked():
				for d in outDirList:
					try:
						for f in cfg.osSCP.listdir(d):
							if f.lower().endswith('.tif'):
								r =cfg.utls.addRasterLayer(d + '/' + f)
					except Exception as err:
						# logger
						cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), ' ERROR exception: ' + str(err))
			cfg.uiUtls.removeProgressBar()
			cfg.cnvs.setRenderFlag(True)
			
	# download image
	def downloadMODISImagesFromNASA(self, imageID, collection, imageDisplayID, outputDirectory, progress, exporter = 'No', date = None):
		# The MODIS data products are retrieved from the online Data Pool, courtesy of the NASA Land Processes Distributed Active Archive Center (LP DAAC), USGS/Earth Resources Observation and Science (EROS) Center, Sioux Falls, South Dakota, https://lpdaac.usgs.gov/data_access/data_pool'
		if collection == cfg.NASAMOD09GQCollection:
			url = 'https://e4ftl01.cr.usgs.gov/MOLT/MOD09GQ.006/' + date.replace('-', '.')+ '/' + imageDisplayID + '.hdf'
		elif collection == cfg.NASAMYD09GQCollection:
			url = 'https://e4ftl01.cr.usgs.gov/MOLA/MYD09GQ.006/' + date.replace('-', '.')+ '/' + imageDisplayID + '.hdf'
		elif collection == cfg.NASAMOD09GACollection:
			url = 'https://e4ftl01.cr.usgs.gov/MOLT/MOD09GA.006/' + date.replace('-', '.')+ '/' + imageDisplayID + '.hdf'
		elif collection == cfg.NASAMYD09GACollection:
			url = 'https://e4ftl01.cr.usgs.gov/MOLA/MYD09GA.006/' + date.replace('-', '.')+ '/' + imageDisplayID + '.hdf'
		elif collection == cfg.NASAMOD09Q1Collection:
			url = 'https://e4ftl01.cr.usgs.gov/MOLT/MOD09Q1.006/' + date.replace('-', '.')+ '/' + imageDisplayID + '.hdf'
		elif collection == cfg.NASAMYD09Q1Collection:
			url = 'https://e4ftl01.cr.usgs.gov/MOLA/MYD09Q1.006/' + date.replace('-', '.')+ '/' + imageDisplayID + '.hdf'
		elif collection == cfg.NASAMOD09A1Collection:
			url = 'https://e4ftl01.cr.usgs.gov/MOLT/MOD09A1.006/' + date.replace('-', '.')+ '/' + imageDisplayID + '.hdf'
		elif collection == cfg.NASAMYD09A1Collection:
			url = 'https://e4ftl01.cr.usgs.gov/MOLA/MYD09A1.006/' + date.replace('-', '.')+ '/' + imageDisplayID + '.hdf'
		if exporter == 'Yes':
			return url
		else:
			user = cfg.ui.user_usgs_lineEdit_2.text()
			password =cfg.ui.password_usgs_lineEdit_2.text()
			try:
				imgID = imageDisplayID + '.hdf'
				check = cfg.utls.passwordConnectPython(user, password, url, 'urs.earthdata.nasa.gov', cfg.tmpDir + '//' + imgID, progress)
				if str(check) == 'Cancel action':
					return check
				if cfg.osSCP.path.getsize(cfg.tmpDir + '//' + imgID) > 10000:
					cfg.shutilSCP.copy(cfg.tmpDir + '//' + imgID, outputDirectory + '//' + imgID)
					cfg.osSCP.remove(cfg.tmpDir + '//' + imgID)
				else:
					cfg.mx.msgErr55(imgID)
					return 'No'
			except Exception as err:
				cfg.mx.msgErr55(imgID)
				# logger
				cfg.utls.logCondition(str(__name__) + '-' + str(cfg.inspectSCP.stack()[0][3])+ ' ' + cfg.utls.lineOfCode(), " ERROR exception: " + str(err))
				return 'No'
			
	# perform bands filter
	def filterTable(self):
		l = cfg.ui.download_images_tableWidget
		text = cfg.ui.products_filter_lineEdit.text()
		items = l.findItems(text, cfg.QtSCP.MatchFlag.MatchContains)
		c = l.rowCount()
		list = []
		for item in items:
			list.append( item.row())
		l.blockSignals(True)
		for i in range (0, c):
			l.setRowHidden(i, False)
			if i not in list:
				l.setRowHidden(i, True)
		l.blockSignals(False)
