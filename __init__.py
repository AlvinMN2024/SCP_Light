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


def name():
    return 'SCP-Light'


def description():
    return 'Early QGIS 4 and Qt 6 port of SCP 7.10.11 for remote sensing classification.'


def version():
    return '1.0.7 (based on SCP 7.10.11)'


def icon():
    return 'semiautomaticclassificationplugin.png'


def qgisMinimumVersion():
    return '4.0'

def author():
    return 'Luca Congedo'

def email():
    return 'ing.congedoluca@gmail.com'

def category():
    return 'Raster'

def classFactory(iface):
    from .semiautomaticclassificationplugin import SemiAutomaticClassificationPlugin
    return SemiAutomaticClassificationPlugin(iface)

def homepage():
    return ''

def tracker():
    return ''
	
def repository():
	return ''

