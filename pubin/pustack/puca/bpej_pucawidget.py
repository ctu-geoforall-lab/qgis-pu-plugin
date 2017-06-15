# -*- coding: utf-8 -*-
"""
/***************************************************************************
 BpejPuCaWidget and BpejLabelPuCaWidget
                                 A QGIS plugin
 Plugin pro pozemkové úpravy
                             -------------------
        begin                : 2016-09-01
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Ondřej Svoboda
        email                : svoboond@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from PyQt4.QtGui import QWidget, QLabel, QComboBox
from PyQt4.QtCore import Qt, QDir, QFileInfo

from qgis.gui import (QgsMapLayerComboBox, QgsMapLayerProxyModel,
                      QgsFieldComboBox, QgsMessageBar)
from qgis.core import *

import processing

from collections import defaultdict
from datetime import datetime

import os
import urllib
import zipfile
import csv

from configparser import RawConfigParser

from pucawidget import PuCaWidget


class BpejPuCaWidget(PuCaWidget):
    """A widget for 'BPEJ' analysis."""
    
    def _build_widgets(self):
        """Builds own widgets."""
        
        self.lastBpejLayer = None
        
        self.bpejMapLayerComboBox = QgsMapLayerComboBox(self)
        self.bpejMapLayerComboBox.setObjectName(u'bpejMapLayerComboBox')
        self.bpejMapLayerComboBox.setFilters(
            QgsMapLayerProxyModel.PolygonLayer)
        self.bpejMapLayerComboBox.activated.connect(self._set_last_bpej_layer)
        QgsMapLayerRegistry.instance().layersAdded.connect(
            self._rollback_bpej_layer)
        QgsMapLayerRegistry.instance().layersRemoved.connect(
            self._reset_bpej_layer)
        self.set_bpej_layer(self.lastBpejLayer)
        self.vBoxLayout.addWidget(self.bpejMapLayerComboBox)
        
        self.bpejFieldComboBox = QgsFieldComboBox(self)
        self.bpejFieldComboBox.setObjectName(u'bpejFieldComboBox')
        self.bpejFieldComboBox.setLayer(
            self.bpejMapLayerComboBox.currentLayer())
        self.vBoxLayout.addWidget(self.bpejFieldComboBox)
        
        self.bpejMapLayerComboBox.layerChanged.connect(
            self.bpejFieldComboBox.setLayer)
    
    def set_bpej_layer(self, bpejLayer, lastBpejLayer=True):
        """Sets the BPEJ layer in the bpejMapLayerComboBox.
        
        Args:
            bpejLayer (QgsVectorLayer): A reference to the BPEJ layer.
            lastBpejLayer (bool): True to set self.lastBpejLayer,
                False otherwise.
        
        """
        
        if lastBpejLayer:
            self.lastBpejLayer = bpejLayer
        
        self.bpejMapLayerComboBox.setLayer(bpejLayer)
    
    def _set_last_bpej_layer(self):
        """Sets the lastBpejLayer.
        
        Sets the lastBpejLayer according to the current layer
        in the bpejMapLayerComboBox.
        
        """
        
        bpejLayer = self.bpejMapLayerComboBox.currentLayer()
        
        if bpejLayer != self.lastBpejLayer:
            self.lastBpejLayer = bpejLayer
    
    def _reset_bpej_layer(self):
        """Resets the BPEJ layer."""
        
        layers = self.iface.legendInterface().layers()
        
        if self.lastBpejLayer not in layers:
            self.set_bpej_layer(None)
    
    def _rollback_bpej_layer(self):
        """Rolls the BPEJ layer back."""
        
        if self.lastBpejLayer == None:
            self.set_bpej_layer(self.lastBpejLayer, False)
        else:
            self.lastBpejLayer = self.bpejMapLayerComboBox.currentLayer()
    
    def execute(self, layer):
        """Executes the analysis.
        
        Args:
            layer (QgsVectorLayer): A reference to the active layer.
        
        """
        
        try:
            editing = self.dW.check_editing()
            
            bpejLayer = self.bpejMapLayerComboBox.currentLayer()
            
            if bpejLayer == None:
                self.pW.set_text_statusbar.emit(u'Žádná vrstva BPEJ.', 10, True)
                return
            
            if bpejLayer.featureCount() == 0:
                self.pW.set_text_statusbar.emit(
                    u'Vrstva BPEJ neobsahuje žádný prvek.', 10, True)
                return
            
            bpejLayerCrs = bpejLayer.crs().authid()
            layerCrs = layer.crs().authid()
            
            if bpejLayerCrs != layerCrs:
                self.pW.set_text_statusbar.emit(
                    u'Aktivní vrstva a vrstva BPEJ nemají stejný '
                    u'souřadnicový systém.', 10, True)
                return
            
            bpejField = self.bpejFieldComboBox.currentField()
            
            if bpejField == u'':
                self.pW.set_text_statusbar.emit(
                    u'Není vybrán sloupec ceny.', 10, True)
                return
            
            self.pW.set_text_statusbar.emit(
                u'Provádím analýzu - oceňování podle BPEJ...', 0, False)
            
            layer.removeSelection()
            bpejLayer.removeSelection()
            
            editedBpejField = self._edit_bpej_field(bpejField, layer)
            
            unionFilePath = processing.runalg(
                'qgis:union',
                layer, bpejLayer, None)['OUTPUT']
            
            unionLayer = QgsVectorLayer(unionFilePath, 'unionLayer', 'ogr')
            
            expression = QgsExpression(
                "\"{}\" is null "
                "or "
                "\"{}\" is null "
                "or "
                "\"{}\" is null "
                "or "
                "\"{}\" != 2"
                .format(
                    editedBpejField,
                    self.dW.defaultMajorParNumberColumnName[:10],
                    self.dW.puCategoryColumnName[:10],
                    self.dW.puCategoryColumnName[:10]))
            
            self.dW.delete_features_by_expression(unionLayer, expression)
            
            if unionLayer.featureCount() != 0:
                multiToSingleFilePath = processing.runalg(
                    'qgis:multiparttosingleparts',
                    unionLayer, None)['OUTPUT']
                
                multiToSingleLayer = QgsVectorLayer(
                    multiToSingleFilePath, 'multiToSingleLayer', 'ogr')
                
                bpejCodePrices = self._get_bpej_code_prices()
                
                rowidColumnName = self.dW.rowidColumnName
                
                prices, missingBpejCodes, bpejCodeAreasPrices = \
                    self._calculate_feature_prices(
                        rowidColumnName, multiToSingleLayer,
                        editedBpejField, bpejCodePrices)
                
                priceFieldName = self.dW.puPriceColumnName
                priceFieldId = layer.fieldNameIndex(priceFieldName)
                
                bpejCodeAreaPricesFieldName = \
                    self.dW.puBpejCodeAreaPricesColumnName
                bpejCodeAreaPricesFielId = layer.fieldNameIndex(
                    bpejCodeAreaPricesFieldName)
                
                layer.startEditing()
                layer.updateFields()
                
                features = layer.getFeatures()
                
                for feature in features:
                    rowid = feature.attribute(rowidColumnName)
                    id = feature.id()
                    
                    price = prices[rowid]
                    
                    if price != 0:
                        layer.changeAttributeValue(id, priceFieldId, price)
                        
                        bpejCodeAreaPrices = bpejCodeAreasPrices[rowid]
                        
                        bpejCodeAreaPricesStr = self._get_bpej_string(
                            bpejCodeAreaPrices)
                        
                        layer.changeAttributeValue(
                            id, bpejCodeAreaPricesFielId, bpejCodeAreaPricesStr)
                
                layer.commitChanges()
                
                if editing:
                    self.iface.actionToggleEditing()
                
                if len(missingBpejCodes) != 0:
                    fields = bpejLayer.pendingFields()
                    
                    for field in fields:
                        if field.name() == bpejField:
                            bpejFieldTypeName = field.typeName()
                            break
                    
                    if bpejFieldTypeName.lower() == u'string':
                        missingBpejCodesStr = \
                            '\'' + '\', \''.join(missingBpejCodes) + '\''
                    else:
                        missingBpejCodesStr = ', '.join(missingBpejCodes)
                    
                    expression = QgsExpression(
                        "\"{}\" in ({})".format(bpejField, missingBpejCodesStr))
                    
                    self.dW.select_features_by_expression(bpejLayer, expression)
                    
                    featureCount = bpejLayer.selectedFeatureCount()
                    
                    duration = 15
                    
                    if featureCount == 1:
                        self.iface.messageBar().pushMessage(
                            u'BPEJ kód vybraného prvku ve vrstvě BPEJ '
                            u'nebyl nalezen.', QgsMessageBar.WARNING, duration)
                    elif featureCount > 1:
                        self.iface.messageBar().pushMessage(
                            u'BPEJ kódy vybraných prvků ve vrstvě BPEJ '
                            u'nebyly nalezeny.',
                            QgsMessageBar.WARNING, duration)
            
            self.pW.set_text_statusbar.emit(
                u'Analýza oceňování podle BPEJ úspěšně dokončena.', 20, False)
        except self.dW.puError:
            QgsApplication.processEvents()
        except:
            QgsApplication.processEvents()
            
            currentCheckAnalysisName = \
                self.pW.checkAnalysisComboBox.currentText()
            
            self.dW.display_error_messages(
                self.pW,
                u'Error executing "{}".'.format(currentCheckAnalysisName),
                u'Chyba při provádění "{}".'.format(currentCheckAnalysisName))
    
    def _edit_bpej_field(self, bpejField, layer):
        """Edits BPEJ field name according to the layer fields.
        
        Args:
            bpejField (str): A name of the BPEJ field.
            layer (QgsVectorLayer): A reference to the active layer.
        
        Returns:
            str: An edited BPEJ field name
        
        """
        
        bpejField = bpejField[:10]
        
        parFields = layer.pendingFields()
        
        for field in parFields:
            if bpejField.lower() == field.name().lower():
                if len(bpejField) <= 8:
                    bpejField = bpejField + '_2'
                    break
                elif len(bpejField) == 9:
                    bpejField = bpejField + '_'
                    break
                elif len(bpejField) == 10:
                    bpejField = bpejField[:8] + '_1'
                    break
        
        return bpejField
    
    def _get_bpej_code_prices(self):
        """Returns BPEJ code prices.
        
        Returns:
            dict: A dictionary with BPEJ codes as keys (int)
                and prices as values (float).
        
        """
        
        formatTimeStr = '%d.%m.%Y'
        
        bpejDir = QDir(self.pluginDir.path() + u'/data/bpej')
        
        bpejBaseName = u'SC_BPEJ'
        
        bpejZipFileName = bpejBaseName + u'.zip'
        
        bpejZipFilePath = bpejDir.filePath(bpejZipFileName)
        
        bpejCsvFileName = bpejBaseName + u'.csv'
        
        bpejCsvFilePath = bpejDir.filePath(bpejCsvFileName)
        
        upToDate = self._check_bpej_csv(bpejCsvFilePath, formatTimeStr)
        
        if not upToDate:
            testInternetUrl, bpejZipUrl = self._get_url()
            
            self._download_bpej_csv(
                testInternetUrl, bpejZipUrl, bpejZipFilePath, bpejCsvFileName)
        
        bpejCodePrices = self._read_bpej_csv(bpejCsvFilePath, formatTimeStr)
        
        return bpejCodePrices
    
    def _check_bpej_csv(self, bpejCsvFilePath, formatTimeStr):
        """Checks if the BPEJ CSV file is up-to-date.
        
        Args:
            bpejCsvFilePath (str): A full path to the BPEJ CSV file.
            formatTimeStr (str): A string for time formatting.
        
        Returns:
            bool: True when the BPEJ CSV file is up-to-date, False otherwise.
        
        """
        
        modificationEpochTime = os.path.getmtime(bpejCsvFilePath)
        
        modificationDateTime = datetime.fromtimestamp(modificationEpochTime)
        
        todayDateTime = datetime.now()
        
        bpejTodayDateTime = todayDateTime.replace(
            hour=03, minute=06, second=0, microsecond=0)
        
        if modificationDateTime > bpejTodayDateTime:
            return True
        else:
            return False
    
    def _get_url(self):
        """Returns URL.
        
        Returns an URL for testing the internet connection
        and an URL of the BPEJ ZIP file.
        
        Returns:
            str: An URL for testing the internet connection.
            str: An URL of the BPEJ ZIP file.
        
        """
        
        config = RawConfigParser()
        
        config.read(self.pluginDir.filePath(u'puplugin.cfg'))
        
        testInternetUrl = config.get('BPEJ', 'testinterneturl')
        bpejZipUrl = config.get('BPEJ', 'bpejzipurl')
        
        return testInternetUrl, bpejZipUrl
    
    def _download_bpej_csv(
            self,
            testInternetUrl, bpejZipUrl, bpejZipFilePath, bpejCsvFileName):
        """Downloads BPEJ CSV file and unzips it.
        
        Args:
            testInternetUrl (str): An URL for testing the internet connection.
            bpejZipUrl (str): An URL of the BPEJ ZIP file.
            bpejZipFilePath (str): A full path to the BPEJ ZIP file.
            bpejCsvFileName (str): A name of the BPEJ CSV file.
        
        Raises:
            dw.puError: When a connection to the CUZK website failed.
        
        """
        
        try:
            testInternetConnection = urllib.urlopen(testInternetUrl)
        except:
            return
        else:
            testInternetConnection.close()
        
        try:
            testBpejConnection = urllib.urlopen(bpejZipUrl)
        except:
            raise self.dW.puError(
                self.dW, self.pW,
                u'A Connection to "{}" failed.'.format(bpejZipUrl),
                u'Nepodařilo se připojit k "{}"'.format(bpejZipUrl))
        else:
            testBpejConnection.close()
            
            urllib.urlretrieve(bpejZipUrl, bpejZipFilePath)
            
            self._unzip_bpej_zip(bpejZipFilePath, bpejCsvFileName)
            
            os.remove(bpejZipFilePath)
    
    def _unzip_bpej_zip(self, bpejZipFilePath, bpejCsvFileName):
        """Unzips BPEJ ZIP file into the same directory.
        
        Args:
            bpejZipFilePath (str): A full path to the BPEJ ZIP file.
            bpejCsvFileName (str): A name of the BPEJ CSV file.
        
        """
        
        fileInfo = QFileInfo(bpejZipFilePath)
        
        bpejDir = fileInfo.absolutePath()
        
        bpejZip = zipfile.ZipFile(bpejZipFilePath, 'r')
        
        bpejZipContent = bpejZip.namelist()
        
        if len(bpejZipContent) != 1:
            bpejZip.close()
            
            raise self.dW.puError(
                self.dW, self.pW,
                u'The structure of the BPEJ ZIP file has changed. '
                u'The BPEJ ZIP file contains more than one file.',
                u'Struktura stahovaného BPEJ ZIP souboru se změnila.')
        
        bpejZipFirstMember = bpejZipContent[0]
        
        bpejZip.extract(bpejZipFirstMember, bpejDir)
        bpejZip.close()
        
        if bpejZipFirstMember != bpejCsvFileName:
            bpejDir = QDir(bpejDir)
            
            bpejZipFirstMemberFilePath = bpejDir.filePath(bpejZipFirstMember)
            
            bpejCsvFilePath = bpejDir.filePath(bpejCsvFileName)
            
            os.rename(bpejZipFirstMemberFilePath, bpejCsvFilePath)
    
    def _read_bpej_csv(self, bpejCsvFilePath, formatTimeStr):
        """Reads the BPEJ CSV file.
        
        Args:
            bpejCsvFilePath (str): A full path to the BPEJ CSV file.
            formatTimeStr (str): A string for time formatting.
        
        Returns:
            dict: A dictionary with BPEJ codes as keys (int)
                and prices as values (float).
        
        """
               
        with open(bpejCsvFilePath, 'rb') as bpejCsvFile:
            bpejCsvReader = csv.reader(bpejCsvFile, delimiter=';')
            
            columnNames = bpejCsvReader.next()
            
            codeColumnIndex = columnNames.index('KOD')
            priceColumnIndex = columnNames.index('CENA')
            validFromColumnIndex = columnNames.index('PLATNOST_OD')
            validToColumnIndex = columnNames.index('PLATNOST_DO')
            
            todayDate = datetime.now().date()
            
            bpejCodePrices = {}
            
            for row in bpejCsvReader:
                if len(row) == 0:
                    break
                
                validFromDateStr = row[validFromColumnIndex]
                validFromDate = datetime.strptime(
                    validFromDateStr, formatTimeStr).date()
                
                validToDateStr = row[validToColumnIndex]
                
                if validToDateStr == '':
                    validToDate = todayDate
                else:
                    validToDate = datetime.strptime(
                        validToDateStr, formatTimeStr).date()
                
                if validFromDate <= todayDate <= validToDate:
                    code = int(row[codeColumnIndex])
                    price = row[priceColumnIndex]
                    
                    bpejCodePrices[code] = float(price)
        
        return bpejCodePrices
    
    def _calculate_feature_prices(
            self,
            rowidColumnName, multiToSingleLayer, bpejField, bpejCodePrices):
        """Calculates feature prices.
        
        Args:
            rowidColumnName (str): A name of rowid column.
            multiToSingleLayer (QgsVectorLayer): A reference to the single
                features layer.
            bpejField (str): A name of the BPEJ field.
            bpejCodePrices (dict): A dictionary with BPEJ codes as keys (int)
                and prices as values (float).
        
        Returns:
            defaultdict: A defaultdict with rowids as keys (long)
                and prices as values (float).
            set: A set of BPEJ codes that are not in BPEJ SCV file.
            defaultdict: A defaultdict with rowids as keys (long)
                and defaultdicts as values.
                defaultdict: A defaultdict with BPEJ codes (without dots)
                    as keys (str) and defaultdicts as values.
                    defaultdict: A defaultdict with area and prices
                        as keys (str) and their values as values (float).
                    
        
        """
        
        prices = defaultdict(float)
        
        bpejCodeAreasPrices = defaultdict(
            lambda : defaultdict(lambda : defaultdict(float)))
        
        missingBpejCodes = set()
        
        features = multiToSingleLayer.getFeatures()
        
        for feature in features:
            rowid = feature.attribute(rowidColumnName)
            bpejCode = str(feature.attribute(bpejField))
            geometry = feature.geometry()
            
            editedBpejCode = int(bpejCode.replace('.', ''))
            
            if editedBpejCode in bpejCodePrices:
                bpejPrice = bpejCodePrices[editedBpejCode]
            else:
                bpejPrice = 0.0
                missingBpejCodes.add(bpejCode)
            
            if geometry != None:
                area = geometry.area()
                
                price = bpejPrice*area
                
                bpejCodeAreasPrices[rowid][editedBpejCode]['bpejPrice'] += \
                    bpejPrice
                bpejCodeAreasPrices[rowid][editedBpejCode]['area'] += area
        
        for rowid, bpejCode in bpejCodeAreasPrices.items():
            for editedBpejCode, values in bpejCode.items():
                values['roundedArea'] = round(values['area'])
                values['price'] = values['roundedArea']*values['bpejPrice']
                
                prices[rowid] += values['price']
        
        return (prices, missingBpejCodes, bpejCodeAreasPrices)
    
    def _get_bpej_string(self, bpejCodeAreaPrices):
        """Returns a BPEJ string.
        
        Args:
            bpejCodeAreaPrices (defaultdict): A defaultdict with BPEJ codes
                (without dots) as keys (str) and defaultdicts as values.
                defaultdict: A defaultdict with area and prices
                    as keys (str) and their values as values (float).
        
        Returns:
            str: A string that contains information about BPEJ.
                The string consists of strings
                '<BPEJ code>-<BPEJ price>-<rounded Area>-<price>'
                for each BPEJ code in the input defaultdict separated by ', '.
        
        """
        
        bpejCodeAreaPricesStr = ''
        
        for bpejCode, values in bpejCodeAreaPrices.items():
            bpejCodeAreaPricesStr += str(bpejCode)
            bpejCodeAreaPricesStr += '-'
            bpejCodeAreaPricesStr += str(values['bpejPrice'])
            bpejCodeAreaPricesStr += '-'
            bpejCodeAreaPricesStr += str(int(values['roundedArea']))
            bpejCodeAreaPricesStr += '-'
            bpejCodeAreaPricesStr += str(values['price'])
            bpejCodeAreaPricesStr += ', '
        
        bpejCodeAreaPricesStr = \
            bpejCodeAreaPricesStr.strip(', ')
        
        return bpejCodeAreaPricesStr


class BpejLabelPuCaWidget(PuCaWidget):
    """A label widget for 'BPEJ' analysis."""
    
    def _build_widgets(self):
        """Builds own widgets."""
        
        self.bpejLayerLabel = QLabel(self)
        self.bpejLayerLabel.setObjectName(u'bpejLayerLabel')
        self.bpejLayerLabel.setText(u'BPEJ:')
        self.bpejLayerLabel.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.vBoxLayout.addWidget(self.bpejLayerLabel)
        
        self.bpejPriceLabel = QLabel(self)
        self.bpejPriceLabel.setObjectName(u'bpejPriceLabel')
        self.bpejPriceLabel.setText(u'Sloupec kódu BPEJ:')
        self.bpejPriceLabel.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.vBoxLayout.addWidget(self.bpejPriceLabel)

