# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DistancePuCaWidget and DistanceLabelPuCaWidget
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

from PyQt4.QtGui import QLabel
from PyQt4.QtCore import Qt

from qgis.gui import QgsMapLayerComboBox, QgsMapLayerProxyModel
from qgis.core import *

from math import sqrt

from pucawidget import PuCaWidget


class DistancePuCaWidget(PuCaWidget):
    """A widget for 'distance' analysis."""
    
    def _build_widgets(self):
        """Builds own widgets."""
        
        self.lastRefPointLayer = None
        
        self.refPointMapLayerComboBox = QgsMapLayerComboBox(self)
        self.refPointMapLayerComboBox.setObjectName(
            u'refPointMapLayerComboBox')
        self.refPointMapLayerComboBox.setFilters(
            QgsMapLayerProxyModel.PointLayer)
        self.refPointMapLayerComboBox.activated.connect(
            self._set_last_ref_point_layer)
        QgsMapLayerRegistry.instance().layersAdded.connect(
            self._rollback_ref_point_layer)
        QgsMapLayerRegistry.instance().layersRemoved.connect(
            self._reset_ref_point_layer)
        self._set_ref_point_layer(self.lastRefPointLayer)
        self.vBoxLayout.addWidget(self.refPointMapLayerComboBox)
    
    def _set_ref_point_layer(self, refPointLayer, lastRefPointLayer=True):
        """Sets the reference point layer in the refPointMapLayerComboBox.
        
        Args:
            refPointLayer (QgsVectorLayer): A reference to the reference
                point layer.
            lastRefPointLayer (bool): True to set self.lastRefPointLayer,
                False otherwise.
        
        """
        
        if lastRefPointLayer:
            self.lastRefPointLayer = refPointLayer
        
        self.refPointMapLayerComboBox.setLayer(refPointLayer)
    
    def _set_last_ref_point_layer(self):
        """Sets the lastRefPointLayer.
        
        Sets the lastRefPointLayer according to the current layer
        in the refPointMapLayerComboBox.
        
        """
        
        refPointLayer = self.refPointMapLayerComboBox.currentLayer()
        
        if refPointLayer != self.lastRefPointLayer:
            self.lastRefPointLayer = refPointLayer
    
    def _reset_ref_point_layer(self):
        """Resets the reference point layer."""
        
        layers = self.iface.legendInterface().layers()
        
        if self.lastRefPointLayer not in layers:
            self._set_ref_point_layer(None)
    
    def _rollback_ref_point_layer(self):
        """Rolls the reference point layer back."""
        
        if self.lastRefPointLayer == None:
            self._set_ref_point_layer(self.lastRefPointLayer, False)
        else:
            self.lastRefPointLayer = \
                self.refPointMapLayerComboBox.currentLayer()
    
    def execute(self, layer):
        """Executes the analysis.
        
        Args:
            layer (QgsVectorLayer): A reference to the active layer.
        
        """
        
        try:
            editing = self.dW.check_editing()
            
            refPointLayer = self.refPointMapLayerComboBox.currentLayer()
            
            if refPointLayer == None:
                self.pW.set_text_statusbar.emit(
                    u'Žádná vrstva referenčního bodu.', 10, True)
                return
            
            refPointCount = refPointLayer.featureCount()
            
            refPointLayerCrs = refPointLayer.crs().authid()
            layerCrs = layer.crs().authid()
            
            if refPointLayerCrs != layerCrs:
                self.pW.set_text_statusbar.emit(
                    u'Aktivní vrstva a vrstva referenčního bodu nemají stejný '
                    u'souřadnicový systém.', 10, True)
                return
            
            if refPointCount != 1:
                self.pW.set_text_statusbar.emit(
                    u'Vrstva referenčního bodu neobsahuje právě jeden prvek.',
                    10, True)
                return
            
            layer.removeSelection()
            refPointLayer.removeSelection()
            
            features = self.dW.get_addressed_features(layer)
            
            self.pW.set_text_statusbar.emit(
                u'Provádím analýzu - měření vzdálenosti...', 0, False)
            
            refPointFeatures = refPointLayer.getFeatures()
            
            for feature in refPointFeatures:
                refPoint = feature.geometry().asPoint()
            
            puDistanceColumnName = self.dW.puDistanceColumnName
            
            fieldId = layer.fieldNameIndex(puDistanceColumnName)
            
            layer.startEditing()
            layer.updateFields()
            
            for feature in features:
                geometry = feature.geometry()
                
                if geometry != None:
                    id = feature.id()
                    originalDistance = feature.attribute(puDistanceColumnName)
                    
                    centroid = geometry.centroid().asPoint()
                    distanceDouble = sqrt(refPoint.sqrDist(centroid))
                    distance = int(round(distanceDouble))
                    
                    if distance != originalDistance:
                        layer.changeAttributeValue(id, fieldId, distance)
            
            layer.commitChanges()
            
            if editing:
                self.iface.actionToggleEditing()
            
            self.pW.set_text_statusbar.emit(
                u'Analýza měření vzdálenosti úspěšně dokončena.', 20, False)
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
    
    def _set_refPoint_layer(self):
        """Sets current reference point layer.
        
        Sets current reference point layer to None if the last reference point
        layer was None.
        
        """
        
        if self.lastRefPointLayer == None:
            self.refPointMapLayerComboBox.setLayer(self.lastRefPointLayer)
        else:
            self.lastRefPointLayer = \
                self.refPointMapLayerComboBox.currentLayer()


class DistanceLabelPuCaWidget(PuCaWidget):
    """A label widget for 'distance' analysis."""
    
    def _build_widgets(self):
        """Builds own widgets."""
        
        self.refPointLabel = QLabel(self)
        self.refPointLabel.setObjectName(u'refPointLabel')
        self.refPointLabel.setText(u'Referenční bod:')
        self.vBoxLayout.addWidget(self.refPointLabel)

