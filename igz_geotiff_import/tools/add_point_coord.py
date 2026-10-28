# SPDX-License-Identifier: GPL-3.0-or-later
"""Add coordinate labels at points clicked by the user on the active image."""

import os
import importlib.util as _ilu
import sys
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QVector3D, QCursor, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt, QPoint
from tools.base import Tool
from core.history import AddTextLabelCommand, AssignLayerCommand, CompoundCommand
from core.textlabel import TextLabel


def _load_core():
    """The plugin's shared ``core`` module (i18n, icons, history routing)."""
    mod = sys.modules.get("_igz_geotiff_core")
    if mod is not None:
        return mod
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core.py")
    spec = _ilu.spec_from_file_location("_igz_geotiff_core", path)
    mod = _ilu.module_from_spec(spec)
    sys.modules["_igz_geotiff_core"] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop("_igz_geotiff_core", None)
        raise
    return mod
_core = _load_core()
tr = _core.tr


def _load_list():
    return _core.load_module("tools/list_images")


def _load_add_coords():
    return _core.load_module("tools/add_coordinates")


LAYER_LABELS = "IGZ_GeoTIFF_Labels"


def _build_crosshair_cursor():
    pm = QPixmap(32, 32)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    try:
        pen = QColor(255, 165, 0)
        p.setPen(Qt.NoPen)
        p.setBrush(pen)
        p.drawRect(15, 0, 2, 12)
        p.drawRect(15, 20, 2, 12)
        p.drawRect(0, 15, 12, 2)
        p.drawRect(20, 15, 12, 2)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)
        p.drawEllipse(QPoint(16, 16), 6, 6)
    finally:
        p.end()
    return QCursor(pm, 16, 16)


class AddPointCoordinateTool(Tool):
    name = "Add Point Coordinate"
    shortcut = None
    description = "Add coordinate labels at clicked points on the active image."
    uses_snap = False

    def __init__(self, main_window, img, scene):
        self._mw = main_window
        self._img = img
        self._scene = scene
        self._cursor = _build_crosshair_cursor()
        self._created_labels = 0

    def on_activate(self, viewport):
        try:
            viewport.setCursor(self._cursor)
        except Exception:
            pass
        viewport.flash_status(tr("Add Point Coordinate active. Click to place labels. ESC to finish."), 5000)

    def on_deactivate(self, viewport):
        try:
            viewport.unsetCursor()
        except Exception:
            pass
        try:
            from tools.select import SelectTool
            viewport.set_active_tool(SelectTool())
        except Exception:
            pass

    def on_hover(self, ctx):
        try:
            if self._mw.viewport:
                self._mw.viewport.setCursor(self._cursor)
        except Exception:
            pass

    def on_click(self, ctx):
        world = ctx.world
        try:
            if self._mw.viewport:
                self._mw.viewport.setCursor(self._cursor)
        except Exception:
            pass
        self._create_label(world)

    def on_cancel(self, viewport):
        try:
            from tools.select import SelectTool
            viewport.set_active_tool(SelectTool())
        except Exception:
            viewport.set_active_tool(None)

    def on_key(self, viewport, key, modifiers):
        if key == Qt.Key_Escape:
            self.on_cancel(viewport)
            return True
        return False

    def status_clause(self):
        return tr("click to place labels • ESC to finish")

    def _create_label(self, point_3d):
        scene = self._mw.viewport.scene
        add_coords = _load_add_coords()
        meta = add_coords._get_image_meta(scene, self._img)
        coord_system = meta.get("coord_system", "utm")
        text = add_coords._point_coord(scene, self._img, point_3d, coord_system)
        if text is None:
            return

        anchor = QVector3D(point_3d.x(), point_3d.y(), point_3d.z())
        offset = QVector3D(0.0, 0.0, 1.0)
        try:
            label = TextLabel(anchor=anchor, offset=offset, text=text, layer=LAYER_LABELS)
            # One undo step per label, on the viewport's own stack (Ctrl+Z).
            if not _core.execute(self._mw, CompoundCommand([
                AddTextLabelCommand(label),
                AssignLayerCommand([label], LAYER_LABELS),
            ])):
                QMessageBox.warning(
                    self._mw, tr("Add Point Coordinate"),
                    tr("The operation was rolled back; the document is unchanged."))
                return
            self._created_labels += 1
            self._mw.viewport.flash_status(f"{tr('Point added:')} {text.replace(chr(10), ' ')}", 3000)
        except Exception as e:
            QMessageBox.warning(self._mw, tr("Add Point Coordinate"), str(e))


def run(app, params):
    scene = getattr(app, "scene", None)
    if scene is None:
        scene = app.viewport.scene if hasattr(app, "viewport") else None
    if scene is None:
        return

    imgs = getattr(scene, "image_planes", None) or []
    if not imgs:
        QMessageBox.information(
            app.window, tr("Add Point Coordinate"),
            tr("There are no imported images in the current scene.") + "\n\n" +
            tr("Use 'Import GeoTIFF' first."))
        return

    img = getattr(scene, "igz_active_image", None)
    if img is None:
        list_mod = _load_list()
        img = list_mod.ensure_active_image(app)
        if img is None:
            return

    add_coords = _load_add_coords()
    meta = add_coords._get_image_meta(scene, img)
    utm_origin = meta.get("utm_origin")
    origin_local = getattr(img, "origin", None)
    if utm_origin is None and origin_local is None:
        QMessageBox.warning(
            app.window, tr("Add Point Coordinate"),
            tr("The active image has no georeferencing metadata."))
        return

    vp = getattr(app, "viewport", None)
    if vp is None:
        return

    tool = AddPointCoordinateTool(app.window, img, scene)
    vp.set_active_tool(tool)