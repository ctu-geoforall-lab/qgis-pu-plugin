# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DockWidget
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

from PyQt4.QtGui import (QDockWidget, QWidget, QSizePolicy, QGridLayout,
                         QFrame, QFileDialog)
from PyQt4.QtCore import pyqtSignal, QDir, QSettings, QFileInfo

from qgis.gui import QgsMessageBar
from qgis.core import *
from qgis.utils import QGis

import traceback
import sys
import os
import platform

from statusbar import StatusBar
from toolbar import ToolBar
from stackedwidget import StackedWidget


class DockWidget(QDockWidget):
    """The main widget of the plugin."""
    
    def __init__(self, iface, pluginDir, name):
        """Constructor.
        
        Args:
            iface (QgisInterface): A reference to the QgisInterface.
            pluginDir (QDir): A plugin directory.
            name (str): A name of the plugin.
        
        """
        
        self.iface = iface
        self.pluginDir = pluginDir
        self.name = name
        
        super(DockWidget, self).__init__()
        
        self._setup_self()
       
    def _setup_self(self):
        """Sets up self."""
        
        # SpatiaLite fix - start
        if QGis.QGIS_VERSION < '2.18.5':
            self.fixedSqliteDriver = False
        else:
            self.fixedSqliteDriver = True
        # SpatiaLite fix - end
        
        self.puMajorParNumberColumnName = 'PU_KMENOVE_CISLO_PAR'
        self.puMinorParNumberColumnName = 'PU_PODDELENI_CISLA_PAR'
        self.puBasisScaleColumnName = 'PU_MERITKO_PODKLADU'
        
        self.editablePuColumns = (
            self.puMajorParNumberColumnName,
            self.puMinorParNumberColumnName,
            self.puBasisScaleColumnName)
        
        self.puCategoryColumnName = 'PU_KATEGORIE'
        self.puAreaColumnName = 'PU_VYMERA_PARCELY'
        self.puAreaAbsDifferenceColumnName = 'PU_VYMERA_PARCELY_ABS_ROZDIL'
        self.puAreaLimitDeviationColumnName = 'PU_VYMERA_PARCELY_MEZNI_ODCHYLKA'
        self.puDistanceColumnName = 'PU_VZDALENOST'
        self.puPriceColumnName = 'PU_CENA'
        self.puBpejCodeAreaPricesColumnName = 'PU_BPEJ_BPEJCENA_VYMERA_CENA'
        
        self.visiblePuColumns = self.editablePuColumns + \
            (self.puCategoryColumnName,
             self.puAreaColumnName,
             self.puAreaAbsDifferenceColumnName,
             self.puAreaLimitDeviationColumnName,
             self.puDistanceColumnName,
             self.puPriceColumnName,
             self.puBpejCodeAreaPricesColumnName)
        
        self.puAreaMaxQualityCodeColumnName = 'PU_VYMERA_PARCELY_MAX_KODCHB_KOD'
        self.puIdColumnName = 'PU_ID'
        
        self.allPuColumns = self.visiblePuColumns + \
            (self.puAreaMaxQualityCodeColumnName,
             self.puIdColumnName)
        
        self.defaultMajorParNumberColumnName = 'KMENOVE_CISLO_PAR'
        self.defaultMinorParNumberColumnName = 'PODDELENI_CISLA_PAR'
        self.deafultAreaColumnName = 'VYMERA_PARCELY'
        
        self.visibleDefaultColumns = (
            self.defaultMajorParNumberColumnName,
            self.defaultMinorParNumberColumnName,
            self.deafultAreaColumnName)
        
        self.allVisibleColumns = \
            self.visiblePuColumns + self.visibleDefaultColumns
        
        # SpatiaLite fix - start
        if not self.fixedSqliteDriver:
            self.rowidColumnName = 'ogc_fid'
        else:
            self.rowidColumnName = 'rowid'
        # SpatiaLite fix - end
        
        self.idColumnName = 'ID'
        self.ogrfidColumnName = 'ogr_fid'
        
        self.uniqueDefaultColumns = (
            self.rowidColumnName,
            self.idColumnName,
            self.ogrfidColumnName)
        
        self.allDefaultColumns = \
            self.visibleDefaultColumns + self.uniqueDefaultColumns
        
        self.requiredColumns = \
            self.allPuColumns + self.allDefaultColumns
        
        self.parLayerCode = 'PAR'
        
        self.sobrLayerCode = 'SOBR'
        self.spolLayerCode = 'SPOL'
        
        self.vertexLayerCodes = (self.sobrLayerCode, self.spolLayerCode)
        
        self.dWName = u'dockWidget'
        
        self.settings = QSettings(self)
        
        self.setObjectName(self.dWName)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        
        self.widget = QWidget(self)
        self.widget.setObjectName(u'widget')
        self.setWidget(self.widget)
        
        self.gridLayout = QGridLayout(self.widget)
        self.gridLayout.setObjectName(u'gridLayout')
        
        self.setWindowTitle(self.name)
        
        self._build_widgets()
    
    def _build_widgets(self):
        """Builds own widgets."""
        
        self.lastActiveLayer = None
        self._disconnect_connect_from_to_iface()
        self.iface.currentLayerChanged.connect(
            self._disconnect_connect_from_to_iface)
        
        QgsMapLayerRegistry.instance().legendLayersAdded.connect(
            self._check_added_perimeter_layer)
        
        self.toolBar = ToolBar(
            self, self.dWName, self.iface, self.pluginDir)
        self.gridLayout.addWidget(self.toolBar, 0, 0, 1, 1)
        
        self.statusBar = StatusBar(
            self, self.dWName, self.iface, self.pluginDir)
        self.gridLayout.addWidget(self.statusBar, 2, 0, 1, 1)
        
        self.frame = QFrame(self)
        self.frame.setObjectName(u'frame')
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.gridLayout.addWidget(self.frame, 1, 0, 1, 1)
        
        self.stackedWidget = StackedWidget(
            self, self.dWName, self.iface, self.pluginDir)
        self.gridLayout.addWidget(self.stackedWidget, 1, 0, 1, 1)
        
        # self.gridLayout.setColumnStretch(1, 1)
    
    def display_error_messages(
            self,
            sender,
            engLogMessage, czeStatusBarMessage=None, czeMessageBarMessage=None,
            duration=20):
        """Displays error messages.
        
        Displays error messages in the Log Messages Tab, the statusBar
        and the Message Bar.
        
        Args:
            sender (QWidget): A reference to the sender widget.
            engLogMessage (str): A message in the 'PU Plugin' Log Messages Tab.
            czeStatusBarMessage (str): A message in the statusBar.
            czeMessageBarMessage (str): A message in the Message Bar.
            duration (int): A duration of the message in the Message Bar
                in seconds.
        
        """
        
        warning = True
        if sender:
            sender.set_text_statusbar.emit(u'', 1, warning)
        
        pluginName = self.name
        
        QgsMessageLog.logMessage(engLogMessage, pluginName)
        
        type, value, puTraceback = sys.exc_info()
        
        if type:
            puTraceback = traceback.format_exc()
            QgsMessageLog.logMessage(puTraceback, pluginName)
        
        if czeStatusBarMessage and sender:
            sender.set_text_statusbar.emit(
                czeStatusBarMessage, duration, warning)
        
        if czeMessageBarMessage:
            self.iface.messageBar().pushMessage(
                pluginName,
                czeMessageBarMessage,
                QgsMessageBar.WARNING,
                duration)
    
    class puError(Exception):
        """A custom exception."""
        
        def __init__(
                self,
                dW, sender,
                engLogMessage,
                czeStatusBarMessage=None,
                czeMessageBarMessage=None,
                duration=20):
            """Constructor.
            
            Args:
                dW (QWidget): A reference to the dock widget.
                sender (QWidget): A reference to the sender widget.
                engLogMessage (str): A message in the 'PU Plugin' Log Messages
                    Tab.
                czeStatusBarMessage (str): A message in the statusBar.
                czeMessageBarMessage (str): A message in the Message Bar.
                duration (int): A duration of the message in the Message Bar
                    in seconds.
                
            """
            
            super(Exception, self).__init__(dW)
            
            dW.display_error_messages(
                sender,
                engLogMessage, czeStatusBarMessage, czeMessageBarMessage,
                duration)
    
    def _get_settings(self, key):
        """Returns a value for the settings key.
        
        Args:
            key (str): A settings key.
                
        Returns:
            str: A value for the settings key.
        
        """
        
        value = self.settings.value(key, '')
        
        return value
    
    def _set_settings(self, key, value):
        """Sets the value for the settings key.
        
        Args:
            key (str): A settings key.
            value (str): A value to be set.
        
        """
        
        self.settings.setValue(key, value)
    
    def open_file_dialog(self, title, filters, existence):
        """Opens a file dialog.
        
        Args:
            title (str): A title of the file dialog.
            filters (str): Available filter(s) of the file dialog.
            existence (bool):
                True when the file has to exist
                (QFileDialog.getOpenFileNameAndFilter).
                False when the file does not have to exist
                (QFileDialog.getSaveFileNameAndFilter).
        
        Returns:
            str: A path to the selected file.
        
        """
        
        sender = self.sender().objectName()
        
        lastUsedFilePath = self._get_settings(sender + '-' + 'lastUsedFilePath')
        lastUsedFilter = self._get_settings(sender + '-' + 'lastUsedFilter')
        
        if existence:
            filePath, usedFilter = QFileDialog.getOpenFileNameAndFilter(
                self, title, lastUsedFilePath, filters, lastUsedFilter)
        else:
            filePath, usedFilter = QFileDialog.getSaveFileNameAndFilter(
                self, title, lastUsedFilePath, filters, lastUsedFilter)
            
            fileInfo = QFileInfo(filePath)
            
            if platform.system() == u'Linux' and fileInfo.suffix() != u'shp':
                filePath = QDir(fileInfo.absolutePath())\
                    .filePath(fileInfo.completeBaseName() + u'.shp')
        
        if filePath and usedFilter:
            self._set_settings(sender + '-' + 'lastUsedFilePath', filePath)
            self._set_settings(sender + '-' + 'lastUsedFilter', usedFilter)
        
        return filePath
    
    def set_field_value_for_features(
            self, layer, features, field, value, startCommit=True):
        """Sets the field value for the given features.
        
        Args:
            layer (QgsVectorLayer): A reference to the layer.
            features (QgsFeatureIterator): A feature iterator.
            field (str): A name of the field.
            value (int): A value to be set.
            startCommit (bool): True for start editing and commit changes,
                False otherwise.
        
        """
        
        fieldId = layer.fieldNameIndex(field)
        
        if startCommit:
            layer.startEditing()
        
        layer.updateFields()
        
        for feature in features:
            if feature.attribute(field) != value:
                id = feature.id()
                layer.changeAttributeValue(id, fieldId, value)
        
        if startCommit:
            layer.commitChanges()
        
        QgsApplication.processEvents()
    
    def check_layer(self, sender=None, layer=False):
        """Checks the active or the given layer.
        
        If layer is False, the active layer is taken.
        
        First it checks if there is a layer, then if the layer is valid,
        then if the layer is vector and finally if the active layer contains
        all required columns.
        
        Emitted messages are for checking the active layer.
        In other words, when sender is not None, layer should be False,
        otherwise emitted messages will not make sense.
        
        Args:
            sender (object): A reference to the sender object. 
            layer (QgsVectorLayer): A reference to the layer.
        
        Returns:
            bool: True when there is a vector layer that contains
                all required columns, False otherwise.
            QgsVectorLayer: A reference to the layer.
        
        """
        
        if layer == False:
            layer = self.iface.activeLayer()
        
        duration = 10
        warning = True
        
        if not layer:
            if sender:
                sender.set_text_statusbar.emit(
                    u'Žádná aktivní vrstva.', duration, warning)
            successLayer = (False, layer)
            return successLayer
        
        if not layer.isValid():
            if sender:
                sender.set_text_statusbar.emit(
                    u'Aktivní vrstva není platná.', duration, warning)
            successLayer = (False, layer)
            return successLayer
        
        if not layer.type() == 0:
            if sender:
                sender.set_text_statusbar.emit(
                    u'Aktivní vrstva není vektorová.', duration, warning)
            successLayer = (False, layer)
            return successLayer
        
        fieldNames = [field.name().upper() for field in layer.pendingFields()]
        
        if not all(column.upper() in fieldNames \
                   for column in self.requiredColumns):
            if sender:
                sender.set_text_statusbar.emit(
                    u'Aktivní vrstva není VFK.', duration, warning)
            successLayer = (False, layer)
            return successLayer
        
        successLayer = (True, layer)
        return successLayer
    
    def check_perimeter_layer(self, perimeterLayer, layer=None, sender=None):
        """Checks the perimeter layer.
        
        Checks if the perimeter layer is vector, if it has the same CRS
        as the given layer and if it contains all required columns.
        
        Args:
            perimeterLayer (QgsVectorLayer): A reference to the perimeter layer.
            layer (QgsVectorLayer): A reference to the layer.
            sender (object): A reference to the sender object.
        
        Returns:
            bool: True when the perimeter layer is vector, it has the same CRS
                as the given layer and it contains all required columns.
        
        """
        
        duration = 10
        warning = True
        
        if not perimeterLayer:
            if sender:
                sender.set_text_statusbar.emit(
                    u'Žádná vrstva obvodu.', duration, warning)
            return False
        
        if not perimeterLayer.type() == 0:
            if sender:
                sender.set_text_statusbar.emit(
                    u'Vrstva obvodu není vektorová.', duration, warning)
            return False
        
        if not perimeterLayer.wkbType() == QGis.WKBPolygon:
            if sender:
                sender.set_text_statusbar.emit(
                    u'Vrstva obvodu není polygonová.', duration, warning)
            return False
        
        if layer:
            perimeterLayerCrs = perimeterLayer.crs().authid()
            layerCrs = layer.crs().authid()
            
            if perimeterLayerCrs != layerCrs:
                if sender:
                    sender.set_text_statusbar.emit(
                        u'Aktivní vrstva a vrstva obvodu nemají stejný '
                        u'souřadnicový systém.', duration, warning)
                return False
        
        perimeterFieldNames = \
            [field.name().upper() for field in perimeterLayer.pendingFields()]
        
        if all(column.upper() in perimeterFieldNames \
                   for column in self.requiredColumns):
            if sender:
                sender.set_text_statusbar.emit(
                    u'Vrstvu parcel nelze použít jako vrstvu obvodu.',
                    duration, warning)
            return False
        
        if not all(column.upper()[:10] in perimeterFieldNames \
                   for column in self.requiredColumns):
            if sender:
                sender.set_text_statusbar.emit(
                    u'Vrstva obvodu není obvod vytvořený PU Pluginem.',
                    duration, warning)
            return False
        
        return True
    
    def check_loaded_layers(self, filePath):
        """Checks if the given layer is already loaded.
        
        Args:
            filePath (str): A full path of the file to be checked.
        
        Returns:
            QgsVectorLayer: A reference to the layer with the same source as
                the given path, None when there is not such a layer.
        
        """
        
        layers = self.iface.legendInterface().layers()
        
        loadedLayer = None
        
        for layer in layers:
            if os.path.normpath(filePath) == os.path.normpath(layer.source()):
                loadedLayer = layer
                break
        
        return loadedLayer
    
    def check_editing(self):
        """Checks if editing is enabled.
        
        Returns:
            bool: True when editing is enabled, False otherwise.
        
        """
        
        if self.stackedWidget.editPuWidget.toggleEditingAction.isChecked():
            return True
        else:
            return False
    
    def select_features_by_field_value(self, layer, field, value):
        """Selects features in the given layer by the field value.
        
        Args:
            layer (QgsVectorLayer): A reference to the layer.
            field (str): A name of the field.
            value (str) A value of the field.
        
        """
        
        expression = QgsExpression("\"{}\" = {}".format(field, value))
        
        features = layer.getFeatures(QgsFeatureRequest(expression))
        
        ids = [feature.id() for feature in features]
        
        layer.selectByIds(ids)
    
    def select_features_by_expression(self, layer, expression):
        """Selects features in the given layer by the expression.
        
        Args:
            layer (QgsVectorLayer): A reference to the layer.
            expression (QgsExpression): An expression.
        
        """
        
        features = layer.getFeatures(QgsFeatureRequest(expression))
        
        ids = [feature.id() for feature in features]
        
        layer.selectByIds(ids)
    
    def delete_features_by_expression(
            self, layer, expression, startCommit=True):
        """Deletes features from the given layer by the expression.
        
        Args:
            layer (QgsVectorLayer): A reference to the layer.
            expression (QgsExpression): An expression.
            startCommit (bool): True for start editing and commit changes,
                False otherwise.
        
        """
        
        features = layer.getFeatures(QgsFeatureRequest(expression))
        
        ids = [feature.id() for feature in features]
        
        if startCommit:
            layer.startEditing()
        
        layer.deleteFeatures(ids)
        
        if startCommit:
            layer.commitChanges()
    
    def get_addressed_features(self, layer):
        """Returns addressed features from the given layer.
        
        categoryValue - description:
            0 - mimo obvod
            1 - v obvodu - neřešené
            2 - v obvodu - řešené
        
        Args:
            layer (QgsVectorLayer): A reference to the layer.
        
        Returns:
            QgsFeatureIterator: An iterator of addressed features.
        
        """
        
        expression = QgsExpression(
            "\"{}\" = 2".format(self.puCategoryColumnName))
        
        features = layer.getFeatures(QgsFeatureRequest(expression))
        
        return features
    
    def set_layer_style(self, layer, qmlFileBaseName):
        """Sets layer style according to the given QML file base name.
        
        Args:
            layer (QgsVectorLayer): A reference to the layer.
            qmlFileBaseName (str): A QML file base name.
        
        """
        
        qmlDir = QDir(self.pluginDir.path() + u'/data/qml')
        style = qmlDir.filePath(qmlFileBaseName + u'.qml')
        
        layer.loadNamedStyle(style)
    
    def disconnect_from_iface(self):
        """Disconnects functions from the QgsInterface."""
        
        self._disconnect_connect_from_to_iface(False)
        
        self.iface.currentLayerChanged.disconnect(
            self._disconnect_connect_from_to_iface)
        
        QgsMapLayerRegistry.instance().legendLayersAdded.disconnect(
            self._check_added_perimeter_layer)
        
        QgsApplication.processEvents()
        
    def _disconnect_connect_from_to_iface(self, connection=True):
        """Disconnects (and connects) functions from (to) iface.
        
        Args:
            connection (bool): True for connecting to iface,
                False for not connecting.
        
        """
        
        try:
            succes, layer = self.check_layer(None, self.lastActiveLayer)
            
            if succes:
                layer.beforeCommitChanges.disconnect(
                    self._ensure_unique_field_values)
                
                layer.committedGeometriesChanges.disconnect(
                    self._update_perimeter_layer)
                    
                layer.committedFeaturesRemoved.disconnect(
                    self._update_perimeter_layer)
            
            succes, self.lastActiveLayer = self.check_layer(None)
            
            if succes and connection:
                self.lastActiveLayer.beforeCommitChanges.connect(
                    self._ensure_unique_field_values)
                
                self.lastActiveLayer.committedGeometriesChanges.connect(
                    self._update_perimeter_layer)
                    
                self.lastActiveLayer.committedFeaturesRemoved.connect(
                    self._update_perimeter_layer)
        except:
            self.display_error_messages(
                None,
                u'Error connecting/disconnecting '
                u'function that ensures unique field values.')
    
    def _ensure_unique_field_values(self):
        """Ensures that field values are unique.
        
        Sets following fields to None for new features:
            rowid
            ID
            ogr_fid
        
        """
        
        try:
            layer = self.iface.activeLayer()
            
            selectedFeaturesIds = layer.selectedFeaturesIds()
                
            features = layer.getFeatures()
            
            groupedRowids = {}
            
            for feature in features:
                rowid = feature.attribute(self.rowidColumnName)
                
                if rowid not in groupedRowids:
                    groupedRowids[rowid] = 1
                else:
                    groupedRowids[rowid] += 1
            
            rowidFieldId = layer.fieldNameIndex(self.rowidColumnName)
            idFieldId = layer.fieldNameIndex(self.idColumnName)
            ogrfidFieldId = layer.fieldNameIndex(self.ogrfidColumnName)
            
            for key, value in groupedRowids.iteritems():
                if value > 1:
                    self.select_features_by_field_value(
                        layer, self.rowidColumnName, key)
                    
                    oldFeatures = []
                    newFeatures = []
                    
                    features = layer.selectedFeatures()
                    
                    for i in xrange(len(features)):
                        if i == 0:
                            continue
                        
                        originalFeature = features[i]
                        
                        oldFeatures.append(originalFeature.id())
                        
                        newFeature = QgsFeature()
                        newFeature.setGeometry(originalFeature.geometry())
                        newFeature.setAttributes(originalFeature.attributes())
                        newFeature.setAttribute(rowidFieldId, None)
                        newFeature.setAttribute(idFieldId, None)
                        newFeature.setAttribute(ogrfidFieldId, None)
                        
                        newFeatures.append(newFeature)
                    
                    layer.deleteFeatures(oldFeatures)
                    layer.addFeatures(newFeatures)
            
            QgsApplication.processEvents()
            
            layer.selectByIds(selectedFeaturesIds)
        except:
            self.display_error_messages(
                self.stackedWidget.currentWidget(),
                u'Error in function that ensures unique field values.')
    
    def _update_perimeter_layer(self):
        """Updates the perimeter layer."""
        
        self.stackedWidget.editPuWidget.update_perimeter_layer()
    
    def _check_added_perimeter_layer(self):
        """Checks if a perimeter layer was added.
        
        If so, sets the perimeter layer style.
        
        """
        
        try:      
            layers = self.iface.legendInterface().layers()
            
            for layer in layers:
                if self.check_perimeter_layer(layer):
                    self.set_layer_style(layer, 'perimeter')
                    self.stackedWidget\
                        .editPuWidget.set_perimeter_layer_table_config(layer)
                    
                    if not self.stackedWidget\
                        .editPuWidget.check_perimeter_map_layer_combo_box():
                        self.stackedWidget\
                            .editPuWidget.set_perimeter_layer(layer, False)
                        self.stackedWidget\
                            .editPuWidget.sync_perimeter_map_layer_combo_box()
        except:
            self.display_error_messages(
                None,
                u'Error in function that checks '
                u'if a perimeter layer was added.')

