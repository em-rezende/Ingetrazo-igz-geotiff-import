# SPDX-License-Identifier: GPL-3.0-or-later
"""Warn the user when imported images use different UTM zones."""

import os
import importlib.util as _ilu
import sys
from PySide6.QtWidgets import QMessageBox


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


def run(app, params):
    scene = getattr(app, "scene", None)
    if scene is None:
        return
    imgs = getattr(scene, "image_planes", None) or []
    if not imgs:
        QMessageBox.information(app.window, tr("Check Zones"),
                                tr("There are no imported images."))
        return

    zones = {}
    for img in imgs:
        # ImagePlane has __slots__ — zone/EPSG live in the plugin metadata,
        # never as attributes of the plane itself.
        meta = _core.image_metadata(scene, img)
        zone = meta.get("utm_zone")
        if zone is None:
            continue
        key = (zone, meta.get("utm_epsg"))
        zones.setdefault(key, []).append(getattr(img, "name", "?") or "?")

    if not zones:
        QMessageBox.information(
            app.window, tr("Check Zones"),
            tr("The imported images carry no UTM zone information."))
        return

    if len(zones) <= 1:
        QMessageBox.information(
            app.window, tr("Check Zones"),
            tr("All images share the same UTM zone.") + f"\n\n{len(imgs)} " + tr("image(s) checked.")
        )
        return

    msg = tr("Images use different UTM zones and may not align:") + "\n\n"
    for (zone, epsg), names in zones.items():
        msg += f"  Zone {zone}, EPSG {epsg}: {len(names)} " + tr("image(s) checked.") + "\n"
        for n in names[:3]:
            msg += f"    - {n}\n"
        if len(names) > 3:
            msg += f"    ... +{len(names) - 3} more\n"
    QMessageBox.warning(app.window, tr("Check Zones"), msg)