# SPDX-License-Identifier: GPL-3.0-or-later
"""Add coordinate text labels on top of the active image."""

import os
import importlib.util as _ilu
import sys
import math
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QMessageBox
)
from PySide6.QtGui import QVector3D
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


LAYER_LABELS = "IGZ_GeoTIFF_Labels"


def _utm_to_wgs84(easting, northing, zone, northern):
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)
    k0 = 0.9996
    if not northern:
        northing = northing - 10000000.0
    x = easting - 500000.0
    y = northing
    m = y / k0
    mu = m / (a * (1.0 - e2 / 4.0 - 3.0 * e2**2 / 64.0 - 5.0 * e2**3 / 256.0))
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))
    phi1 = (mu
            + (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0) * math.sin(2.0 * mu)
            + (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0) * math.sin(4.0 * mu)
            + (151.0 * e1**3 / 96.0) * math.sin(6.0 * mu)
            + (1097.0 * e1**4 / 512.0) * math.sin(8.0 * mu))
    sin_phi1 = math.sin(phi1)
    cos_phi1 = math.cos(phi1)
    tan_phi1 = math.tan(phi1)
    n1 = a / math.sqrt(1.0 - e2 * sin_phi1**2)
    t1 = tan_phi1**2
    c1 = e2 / (1.0 - e2) * cos_phi1**2
    r1 = a * (1.0 - e2) / (1.0 - e2 * sin_phi1**2)**1.5
    d = x / (n1 * k0)
    lat = phi1 - (n1 * tan_phi1 / r1) * (
        d**2 / 2.0
        - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1**2 - 9.0 * e2) * d**4 / 24.0
        + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1**2 - 252.0 * e2 - 3.0 * c1**2) * d**6 / 720.0
    )
    lon = (d
           - (1.0 + 2.0 * t1 + c1) * d**3 / 6.0
           + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1**2 + 8.0 * e2 + 24.0 * t1**2) * d**5 / 120.0) / cos_phi1
    return math.degrees(lat), math.degrees(lon) + (zone - 1) * 6.0 - 180.0 + 3.0


def _web_mercator_to_wgs84(x, y):
    R = 6378137.0
    lon = (x / R) * (180.0 / math.pi)
    lat = (2.0 * math.atan(math.exp(y / R)) - (math.pi / 2.0)) * (180.0 / math.pi)
    return lat, lon


def _get_image_meta(scene, img):
    meta_dict = getattr(scene, "igz_image_metadata", None)
    if meta_dict is not None:
        meta = meta_dict.get(id(img))
        if meta is not None:
            return meta
    return {
        "utm_origin": getattr(img, "utm_origin", None),
        "utm_epsg": getattr(img, "utm_epsg", None),
        "utm_zone": getattr(img, "utm_zone", None),
        "utm_northern": getattr(img, "utm_northern", True),
        "coord_system": getattr(img, "coord_system", "utm"),
    }


def _point_coord(scene, img, point_local, coord_system):
    datum = getattr(scene, "georef", None)
    meta = _get_image_meta(scene, img)
    utm_zone = meta.get("utm_zone")
    utm_northern = meta.get("utm_northern", True)
    utm_epsg = meta.get("utm_epsg")

    utm = None
    if datum is not None:
        try:
            pt = QVector3D(point_local.x(), point_local.y(), point_local.z())
            utm = datum.local_to_utm(pt)
            if utm is not None:
                utm = (utm[0], utm[1])
        except Exception:
            pass

    if utm is None:
        utm_origin = meta.get("utm_origin")
        origin_local = getattr(img, "origin", None)
        if utm_origin is not None and origin_local is not None:
            dx = point_local.x() - origin_local.x()
            dy = point_local.y() - origin_local.y()
            utm = (utm_origin[0] + dx, utm_origin[1] + dy)

    if utm is None:
        return None

    if coord_system == "wgs84":
        if utm_epsg == 3857 or utm_zone is None:
            try:
                lat, lon = _web_mercator_to_wgs84(utm[0], utm[1])
                return f"Lat: {lat:.6f}\nLon: {lon:.6f}"
            except Exception:
                pass
        elif utm_zone is not None:
            try:
                lat, lon = _utm_to_wgs84(utm[0], utm[1], utm_zone, utm_northern)
                return f"Lat: {lat:.6f}\nLon: {lon:.6f}"
            except Exception:
                pass

    return f"E: {utm[0]:.1f}\nN: {utm[1]:.1f}"


def run(app, params):
    scene = getattr(app, "scene", None)
    if scene is None:
        scene = app.viewport.scene if hasattr(app, "viewport") else None
    if scene is None:
        return

    imgs = getattr(scene, "image_planes", None) or []
    if not imgs:
        QMessageBox.information(
            app.window, tr("Add Coordinates"),
            tr("There are no imported images in the current scene.") + "\n\n" +
            tr("Use 'Import GeoTIFF' first."))
        return

    img = getattr(scene, "igz_active_image", None)
    if img is None:
        list_mod = _load_list()
        img = list_mod.ensure_active_image(app)
        if img is None:
            return

    meta = _get_image_meta(scene, img)
    utm_origin = meta.get("utm_origin")
    origin_local = getattr(img, "origin", None)
    if utm_origin is None and origin_local is None:
        QMessageBox.warning(
            app.window, tr("Add Coordinates"),
            tr("This image has no georeferencing metadata."))
        return

    coord_system = meta.get("coord_system", "utm")

    dlg = QDialog(app.window)
    dlg.setWindowTitle(tr("Add Coordinates"))
    layout = QVBoxLayout(dlg)
    form = QFormLayout()
    spin = QDoubleSpinBox()
    spin.setRange(1.0, 10000.0)
    spin.setDecimals(1)
    spin.setValue(50.0)
    spin.setSuffix(" m")
    form.addRow(QLabel(tr("Label spacing:")), spin)
    layout.addLayout(form)
    btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    layout.addWidget(btns)
    if dlg.exec() != QDialog.Accepted:
        return

    corners = list(img.corners())
    if len(corners) < 4:
        return

    labels = []
    for corner in corners:
        text = _point_coord(scene, img, corner, coord_system)
        if text is None:
            continue
        anchor = QVector3D(corner.x(), corner.y(), corner.z())
        offset = QVector3D(0.0, 0.0, 1.0)
        labels.append(TextLabel(anchor=anchor, offset=offset,
                                text=text, layer=LAYER_LABELS))

    labels_created = len(labels)
    if labels:
        # One undo step: the labels plus the layer that holds them. The layer
        # is created by AssignLayerCommand (never by appending it by hand), so
        # undoing the labels takes the layer with it.
        if not _core.execute(app, CompoundCommand(
            [AddTextLabelCommand(lbl) for lbl in labels]
            + [AssignLayerCommand(labels, LAYER_LABELS)]
        )):
            QMessageBox.critical(
                app.window, tr("Add Coordinates"),
                tr("The operation was rolled back; the document is unchanged."))
            return

    QMessageBox.information(
        app.window, tr("Add Coordinates"),
        f"{labels_created} " + tr("label(s) created on the image.") +
        "\n\n" + tr("Layer:") + f" {LAYER_LABELS}" +
        "\n" + tr("Coordinate system:") + f" {coord_system.upper()}")