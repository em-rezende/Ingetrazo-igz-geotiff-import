# SPDX-License-Identifier: GPL-3.0-or-later
"""GeoTIFF Import — IngeTrazo plugin entry point.

IngeTrazo loads this package by file path (``core.extensions`` imports it as
``ingetrazo_plugin_igz_geotiff_import``) and calls :func:`setup` once with a
``views.extension_api.ExtensionApp``. The plugin contributes:

* a **GeoTIFF Import** tool bar, and
* the **Extensions ▸ GeoTIFF Import** submenu (``app.add_menu``).

Tool modules live in ``tools/`` and are imported by absolute file path with
:mod:`importlib.util` — the same rule the host applies to plugins: a plugin
directory never lands on ``sys.path``, so no file of ours can shadow a stdlib
module for the whole application.
"""

from __future__ import annotations

import importlib.util
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_local(name):
    """Import ``name`` (relative to this folder) by absolute file path.

    The module is registered under a private, valid module name and reused on
    every later call, so a tool imported both here and from another tool is
    one module object — and one copy of :mod:`core` — not two.
    """
    path = os.path.join(_HERE, *name.split("/")) + ".py"
    mod_name = "_igz_geotiff_" + name.replace("/", "_")
    cached = sys.modules.get(mod_name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot build an import spec for " + path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(mod_name, None)
        raise
    return mod


_core = _load_local("core")
_tr = _core.tr
_load_icon = _core.load_icon
__version__ = _core.__version__


def setup(app) -> None:
    """Register the tool bar and the ``Extensions ▸ GeoTIFF Import`` submenu.

    Called once by IngeTrazo (``core.extensions``) with a
    ``views.extension_api.ExtensionApp`` — a module-level ``setup(app)`` is the
    documented contract for package plugins. Each action calls its tool
    module's ``run(app, params)``; every edit goes through the viewport history
    (see ``core.execute``), so ``Ctrl+Z`` and the dirty flag keep working.
    """
    window = app.window
    toolbar = QToolBar(_tr("GeoTIFF Import"), window)
    toolbar.setObjectName("igz_geotiff_import_toolbar")
    toolbar.setWindowTitle(_tr("GeoTIFF Import"))

    # Tool modules (imported by absolute file path — see _load_local)
    importer_mod = _load_local("tools/geotiff_importer")
    capture_mod = _load_local("tools/capture_map")
    delete_mod = _load_local("tools/delete_images")
    zoom_mod = _load_local("tools/zoom_to_image")
    list_mod = _load_local("tools/list_images")
    check_mod = _load_local("tools/check_zones")
    reload_mod = _load_local("tools/reload_image")
    coords_mod = _load_local("tools/add_coordinates")
    grid_mod = _load_local("tools/coord_grid")
    reproj_mod = _load_local("tools/reproject_image")
    point_coord_mod = _load_local("tools/add_point_coord")
    crop_mod = _load_local("tools/crop_image")

    # The rubber-band overlay that outlines the active image
    rb_mod = _load_local("tools/rubber_band")
    rb_mod._ensure_overlay(window)

    # Buttons, in the order they appear on the tool bar
    buttons = [
        ("geotiff_import",    "Import GeoTIFF",       importer_mod.run),
        ("geotiff_list",      "Images List",          list_mod.run),
        ("geotiff_zoom",      "Zoom to Image",        zoom_mod.run),
        ("geotiff_rubber",    "Toggle Rubber Band",   rb_mod.toggle_visible),
        ("geotiff_warning",   "Check Zones",          check_mod.run),
        ("geotiff_reload",    "Reload Image",         reload_mod.run),
        ("geotiff_coords",    "Add Coordinates",      coords_mod.run),
        ("geotiff_point",     "Add Point Coordinate", point_coord_mod.run),
        ("geotiff_grid",      "Coordinate Grid",      grid_mod.run),
        ("geotiff_reproject", "Reproject Image",      reproj_mod.run),
        ("geotiff_crop",      "Crop Image",           crop_mod.run),
        ("geotiff_capture",   "Capture Map",          capture_mod.run),
        ("geotiff_delete",    "Delete Images",        delete_mod.run),
    ]

    # One QAction per tool, shared by the tool bar and the menu: one
    # connection, one shortcut and one source of translated labels.
    actions = []
    for icon_name, label, func in buttons:
        action = QAction(_load_icon(icon_name, window), _tr(label), window)
        action.setToolTip(_tr(label))
        action.setStatusTip(_tr(label))
        action.triggered.connect(lambda _checked=False, f=func: f(app, {}))
        actions.append(action)
        toolbar.addAction(action)

    add_toolbar = getattr(window, "addToolBar", None)
    if callable(add_toolbar):
        add_toolbar(Qt.TopToolBarArea, toolbar)

    # Extensions ▸ GeoTIFF Import (ExtensionApp.add_menu). A host without it
    # keeps the tool bar alone instead of failing to load the extension.
    add_menu = getattr(app, "add_menu", None)
    submenu = None
    if callable(add_menu):
        try:
            submenu = add_menu(_tr("GeoTIFF Import"))
        except Exception:
            submenu = None
    if submenu is not None:
        for action in actions:
            submenu.addAction(action)