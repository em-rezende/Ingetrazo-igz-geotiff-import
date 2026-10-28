# SPDX-License-Identifier: GPL-3.0-or-later
"""Zoom to the active image."""

import os
import importlib.util as _ilu
import sys
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QVector3D


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


def run(app, params):
    scene = getattr(app, "scene", None)
    if scene is None:
        scene = app.viewport.scene if hasattr(app, "viewport") else None
    if scene is None:
        return

    imgs = getattr(scene, "image_planes", None) or []
    if not imgs:
        QMessageBox.information(
            app.window, tr("Zoom to Image"),
            tr("There are no imported images in the current scene.") + "\n\n" +
            tr("Use 'Import GeoTIFF' first."))
        return

    img = getattr(scene, "igz_active_image", None)
    if img is None:
        list_mod = _load_list()
        img = list_mod.ensure_active_image(app)
        if img is None:
            return

    try:
        pts = list(img.corners())
        if not pts:
            return
        xmin = min(p.x() for p in pts)
        xmax = max(p.x() for p in pts)
        ymin = min(p.y() for p in pts)
        ymax = max(p.y() for p in pts)
        zmin = min(p.z() for p in pts)
        zmax = max(p.z() for p in pts)
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        cz = (zmin + zmax) / 2.0
        dist = max(xmax - xmin, ymax - ymin, zmax - zmin) * 1.5 + 10.0
        vp = getattr(app, "viewport", None)
        cam = getattr(vp, "camera", None) if vp else None
        if cam is not None:
            if hasattr(cam, "target"):
                cam.target = QVector3D(cx, cy, cz)
            if hasattr(cam, "distance"):
                cam.distance = dist
            vp.update()
    except Exception as e:
        QMessageBox.warning(app.window, tr("Zoom to Image"), str(e))