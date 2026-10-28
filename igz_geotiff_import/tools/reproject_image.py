# SPDX-License-Identifier: GPL-3.0-or-later
"""Reproject the active image's coordinate reference (UTM zone / hemisphere).

The image keeps its position in the local model (near the origin 0,0,0).
Only the georeferencing metadata (utm_origin / utm_zone / utm_epsg) is
updated, and any UTM coordinate labels belonging to this plugin are
rewritten to show values in the new zone. Latitude/longitude labels are
left untouched, because lat/lon does not depend on the UTM zone.
"""

import os
import importlib.util as _ilu
import sys
import math
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
    QSpinBox, QComboBox, QMessageBox, QLabel
)
from core.history import Command


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


# ---------------------------------------------------------------------------
# Conversões geodésicas (mesmas já usadas no plugin)
# ---------------------------------------------------------------------------

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


def _wgs84_to_utm(lat, lon, zone, northern):
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = f * (2.0 - f)
    k0 = 0.9996
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lon0 = math.radians((zone - 1) * 6.0 - 180.0 + 3.0)
    n = a / math.sqrt(1.0 - e2 * math.sin(lat_rad)**2)
    t = math.tan(lat_rad)**2
    c = e2 / (1.0 - e2) * math.cos(lat_rad)**2
    A = (lon_rad - lon0) * math.cos(lat_rad)
    e4 = e2 * e2
    e6 = e4 * e2
    m = a * ((1.0 - e2/4.0 - 3.0*e4/64.0 - 5.0*e6/256.0) * lat_rad
             - (3.0*e2/8.0 + 3.0*e4/32.0 + 45.0*e6/1024.0) * math.sin(2.0*lat_rad)
             + (15.0*e4/256.0 + 45.0*e6/1024.0) * math.sin(4.0*lat_rad)
             - (35.0*e6/3072.0) * math.sin(6.0*lat_rad))
    easting = k0 * n * (A + (1.0 - t + c) * A**3/6.0
                        + (5.0 - 18.0*t + t*t + 72.0*c - 58.0*e2) * A**5/120.0) + 500000.0
    northing = k0 * (m + n * math.tan(lat_rad) * (A*A/2.0
                     + (5.0 - t + 9.0*c + 4.0*c*c) * A**4/24.0
                     + (61.0 - 58.0*t + t*t + 600.0*c - 330.0*e2) * A**6/720.0))
    if not northern:
        northing += 10000000.0
    return easting, northing


def _web_mercator_to_wgs84(x, y):
    R = 6378137.0
    lon = (x / R) * (180.0 / math.pi)
    lat = (2.0 * math.atan(math.exp(y / R)) - (math.pi / 2.0)) * (180.0 / math.pi)
    return lat, lon


def _wgs84_to_web_mercator(lat, lon):
    R = 6378137.0
    x = math.radians(lon) * R
    y = math.log(math.tan(math.pi / 4.0 + math.radians(lat) / 2.0)) * R
    return x, y


# ---------------------------------------------------------------------------
# Metadados
# ---------------------------------------------------------------------------

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
    }


def _utm_of_local_point(scene, img, meta, point_local):
    """Return (easting, northing) in the image's current UTM zone for a
    point given in local (model) coordinates."""
    datum = getattr(scene, "georef", None)
    if datum is not None:
        try:
            from PySide6.QtGui import QVector3D
            pt = QVector3D(point_local.x(), point_local.y(), point_local.z())
            utm = datum.local_to_utm(pt)
            if utm is not None:
                return float(utm[0]), float(utm[1])
        except Exception:
            pass

    utm_origin = meta.get("utm_origin")
    origin_local = getattr(img, "origin", None)
    if utm_origin is not None and origin_local is not None:
        dx = point_local.x() - origin_local.x()
        dy = point_local.y() - origin_local.y()
        return utm_origin[0] + dx, utm_origin[1] + dy
    return None


def _latlon_of_local_point(scene, img, meta, point_local):
    """Return (lat, lon) in WGS84 for a point given in local coordinates,
    using the image's *current* CRS."""
    epsg = meta.get("utm_epsg")
    zone = meta.get("utm_zone")
    northern = meta.get("utm_northern", True)

    datum = getattr(scene, "georef", None)
    if datum is not None:
        try:
            from PySide6.QtGui import QVector3D
            pt = QVector3D(point_local.x(), point_local.y(), point_local.z())
            result = datum.local_to_geodetic(pt)
            if result is not None:
                lat, lon = float(result[0]), float(result[1])
                return lat, lon
        except Exception:
            pass

    utm = _utm_of_local_point(scene, img, meta, point_local)
    if utm is None:
        return None
    if epsg == 3857 or zone is None:
        return _web_mercator_to_wgs84(utm[0], utm[1])
    return _utm_to_wgs84(utm[0], utm[1], zone, northern)


# ---------------------------------------------------------------------------
# Reescrita dos rótulos
# ---------------------------------------------------------------------------

def _iter_labels(scene):
    """Yield every TextLabel owned by this plugin's label layer."""
    for attr in ("labels", "text_labels", "textlabels"):
        collection = getattr(scene, attr, None)
        if collection:
            for lbl in list(collection):
                if getattr(lbl, "layer", None) == LAYER_LABELS:
                    yield lbl
            return
    # Fallback: some builds keep them inside layers
    for lyr in getattr(scene, "layers", []) or []:
        if getattr(lyr, "name", None) != LAYER_LABELS:
            continue
        for item in getattr(lyr, "items", []) or []:
            if hasattr(item, "anchor") and hasattr(item, "text"):
                yield item


def _label_rewrites(scene, img, old_meta, new_meta, coord_system_hint=None):
    """``[(label, new_text)]`` for the UTM labels this plugin owns.

    * The local anchor of each label is unchanged (the label stays put).
    * lat/lon labels are not touched (lat/lon is CRS-independent).
    * UTM labels are re-derived from the anchor and the new metadata.

    Nothing is mutated here: the caller wraps each pair in the host's
    ``EditTextLabelCommand`` so the rewrite undoes with the metadata swap, in
    one step.
    """
    add_coords = _load_add_coords()
    rewrites = []

    new_zone = new_meta.get("utm_zone")
    new_northern = new_meta.get("utm_northern", True)
    new_epsg = new_meta.get("utm_epsg")

    for label in _iter_labels(scene):
        anchor = getattr(label, "anchor", None)
        if anchor is None:
            continue
        old_text = getattr(label, "text", "") or ""
        # Detect if this label is lat/lon (leave it alone).
        if old_text.lstrip().lower().startswith(("lat", "lon")):
            continue

        # Compute lat/lon from the anchor using the OLD CRS.
        latlon = _latlon_of_local_point(scene, img, old_meta, anchor)
        if latlon is None:
            continue
        lat, lon = latlon

        # Compute new UTM in the destination zone.
        if new_epsg == 3857 or new_zone is None:
            new_e, new_n = _wgs84_to_web_mercator(lat, lon)
        else:
            new_e, new_n = _wgs84_to_utm(lat, lon, new_zone, new_northern)

        rewrites.append((label, f"E: {new_e:.1f}\nN: {new_n:.1f}"))

    return rewrites


class _ImageMetadataCommand(Command):
    """Swap this plugin's metadata record for one image, undoably.

    The record lives in ``scene.igz_image_metadata`` (document data) rather than
    in a core history table, so it needs a tiny command of its own to share the
    reproject's single undo step with the label rewrites.
    """

    def __init__(self, image, metadata):
        self._image = image
        self._new = dict(metadata)
        self._old = None

    def do(self, scene):
        store = getattr(scene, "igz_image_metadata", None)
        if not isinstance(store, dict):
            store = {}
            scene.igz_image_metadata = store
        if self._old is None:
            self._old = dict(store.get(id(self._image), {}))
        store[id(self._image)] = dict(self._new)
        scene.version += 1

    def undo(self, scene):
        store = getattr(scene, "igz_image_metadata", None)
        if isinstance(store, dict) and self._old is not None:
            store[id(self._image)] = dict(self._old)
        scene.version += 1


# ---------------------------------------------------------------------------
# Diálogo
# ---------------------------------------------------------------------------

def _ask_reproject_options(app, src_zone, src_northern):
    dlg = QDialog(app.window)
    dlg.setWindowTitle(tr("Reproject Image"))
    dlg.setMinimumWidth(400)
    layout = QVBoxLayout(dlg)

    lbl = QLabel(
        tr("Change the coordinate reference of the active image.") + "\n\n" +
        tr("The image will stay in place; only its georeference "
           "(and its coordinate labels) will be updated.") + "\n\n" +
        tr("Source UTM zone:") + f" {src_zone}  " +
        tr("Source hemisphere:") + f" {'N' if src_northern else 'S'}"
    )
    lbl.setWordWrap(True)
    layout.addWidget(lbl)

    form = QFormLayout()

    spin_src_zone = QSpinBox()
    spin_src_zone.setRange(1, 60)
    spin_src_zone.setValue(src_zone)
    form.addRow(QLabel(tr("Source UTM zone:")), spin_src_zone)

    combo_src_hemi = QComboBox()
    combo_src_hemi.addItems([tr("Northern"), tr("Southern")])
    combo_src_hemi.setCurrentIndex(0 if src_northern else 1)
    form.addRow(QLabel(tr("Source hemisphere:")), combo_src_hemi)

    spin_dst_zone = QSpinBox()
    spin_dst_zone.setRange(1, 60)
    spin_dst_zone.setValue(src_zone)
    form.addRow(QLabel(tr("Target UTM zone:")), spin_dst_zone)

    combo_dst_hemi = QComboBox()
    combo_dst_hemi.addItems([tr("Northern"), tr("Southern")])
    combo_dst_hemi.setCurrentIndex(0 if src_northern else 1)
    form.addRow(QLabel(tr("Target hemisphere:")), combo_dst_hemi)

    layout.addLayout(form)

    btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    layout.addWidget(btns)

    if dlg.exec() != QDialog.Accepted:
        return None

    src_z = spin_src_zone.value()
    dst_z = spin_dst_zone.value()
    src_n = (combo_src_hemi.currentIndex() == 0)
    dst_n = (combo_dst_hemi.currentIndex() == 0)

    if src_z == dst_z and src_n == dst_n:
        QMessageBox.information(
            app.window, tr("Reproject Image"),
            tr("Source and target are identical. Nothing to do."))
        return None

    return {
        "src_zone": src_z,
        "src_northern": src_n,
        "dst_zone": dst_z,
        "dst_northern": dst_n,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(app, params):
    scene = getattr(app, "scene", None)
    if scene is None:
        scene = app.viewport.scene if hasattr(app, "viewport") else None
    if scene is None:
        return

    imgs = getattr(scene, "image_planes", None) or []
    if not imgs:
        QMessageBox.information(
            app.window, tr("Reproject Image"),
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
    if utm_origin is None and origin_local is not None:
        # No metadata yet: assume the current local origin *is* the UTM origin.
        utm_origin = (origin_local.x(), origin_local.y())

    if utm_origin is None:
        QMessageBox.warning(
            app.window, tr("Reproject Image"),
            tr("This image has no origin."))
        return

    src_zone = meta.get("utm_zone")
    src_northern = meta.get("utm_northern", True)

    if src_zone is None:
        src_zone = 23
    if not isinstance(src_zone, int):
        try:
            src_zone = int(src_zone)
        except Exception:
            src_zone = 23

    opts = _ask_reproject_options(app, src_zone, src_northern)
    if opts is None:
        return

    # Snapshot of the old metadata so labels can be recomputed with the OLD CRS.
    old_meta = dict(meta)
    old_meta.setdefault("utm_origin", utm_origin)
    old_meta.setdefault("utm_zone", src_zone)
    old_meta.setdefault("utm_northern", src_northern)
    old_meta.setdefault("utm_epsg", meta.get("utm_epsg"))

    # The image's *local origin* stays where it is. Recompute which UTM
    # coordinate that local point has in the destination CRS.
    origin_local = getattr(img, "origin", None)
    latlon = _latlon_of_local_point(scene, img, old_meta, origin_local)
    if latlon is None:
        QMessageBox.warning(
            app.window, tr("Reproject Image"),
            tr("Could not determine the geographic position of the image."))
        return
    lat, lon = latlon

    if opts["dst_zone"] is not None:
        new_e, new_n = _wgs84_to_utm(lat, lon, opts["dst_zone"], opts["dst_northern"])
    else:
        new_e, new_n = _wgs84_to_web_mercator(lat, lon)

    new_meta = dict(meta)
    new_meta["utm_origin"] = (new_e, new_n)
    new_meta["utm_zone"] = opts["dst_zone"]
    new_meta["utm_northern"] = opts["dst_northern"]
    new_meta["utm_epsg"] = (32600 if opts["dst_northern"] else 32700) + opts["dst_zone"]
    new_meta["wgs84_origin"] = (lat, lon)

    # One undoable step: the metadata swap plus every UTM label rewrite.
    # NOTE: img.origin is intentionally NOT touched.
    try:
        from core.history import CompoundCommand, EditTextLabelCommand

        rewrites = _label_rewrites(scene, img, old_meta, new_meta,
                                   coord_system_hint=meta.get("coord_system", "utm"))
        commands = [_ImageMetadataCommand(img, new_meta)]
        commands.extend(EditTextLabelCommand(label, text) for label, text in rewrites)
        if not _core.execute(app, CompoundCommand(commands)):
            QMessageBox.critical(
                app.window, tr("Reproject Image"),
                tr("The operation was rolled back; the document is unchanged."))
            return

        QMessageBox.information(
            app.window, tr("Reproject Image"),
            tr("Image re-referenced to zone") + f" {opts['dst_zone']} " +
            f"({'N' if opts['dst_northern'] else 'S'}).\n\n" +
            tr("Position preserved. Coordinate labels updated."))
    except Exception as e:
        import traceback
        traceback.print_exc()
        QMessageBox.critical(
            app.window, tr("Reproject Image"),
            tr("Error re-referencing image:") + f"\n\n{type(e).__name__}: {e}")