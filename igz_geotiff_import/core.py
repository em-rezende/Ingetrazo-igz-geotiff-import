# SPDX-License-Identifier: GPL-3.0-or-later
"""GeoTIFF Import — core utilities (i18n, icons, history routing)."""

from __future__ import annotations

import importlib.util
import json
import os
import sys

from PySide6.QtGui import QIcon, QPalette

__version__ = "1.4.0"

_HERE = os.path.dirname(os.path.abspath(__file__))
_ICONS_DIR = os.path.join(_HERE, "icons")
_I18N_DIR = os.path.join(_HERE, "i18n")

#: Document layer names are document data and are never translated: originals
#: and map captures land on the first, crop results on the second.
LAYER_IMAGES = "IGZ_GeoTIFF_Images"
LAYER_CROPPED = "IGZ_GeoTIFF_Cropped_Images"

_SOURCE_LANG = "en"
_catalog = {}
_catalog_cache = {}
_active_lang = None
_icon_cache = {}


def plugin_dir() -> str:
    """Absolute path of the plugin package (``…/igz_geotiff_import``)."""
    return _HERE


def load_module(name: str):
    """Import ``name`` (relative to the plugin folder) by absolute file path.

    Mirrors the rule IngeTrazo applies to plugins: a private module name, an
    absolute path and never ``sys.path``. The module is registered in
    ``sys.modules`` so the same file imported from two tools is one module
    (and one copy of its state); it is popped again if it fails, so a
    half-initialised module is never reused.
    """
    mod_name = "_igz_geotiff_" + name.replace("/", "_")
    cached = sys.modules.get(mod_name)
    if cached is not None:
        return cached
    path = os.path.join(_HERE, *name.split("/")) + ".py"
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


# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------

def _plugin_lang() -> str:
    try:
        from core.i18n import current_language
        return current_language() or _SOURCE_LANG
    except Exception:
        return _SOURCE_LANG


def _load_catalog(lang: str) -> dict:
    if lang in _catalog_cache:
        return _catalog_cache[lang]
    catalog = {}
    try:
        with open(os.path.join(_I18N_DIR, lang + ".json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        catalog = {str(k): str(v) for k, v in data.items() if not str(k).startswith("_")}
    except Exception:
        catalog = {}
    _catalog_cache[lang] = catalog
    return catalog


def tr(text: str, **kwargs) -> str:
    """Translate ``text`` with the plugin catalog, then with IngeTrazo's own.

    Keys are the English source strings; a missing key falls back to the
    application catalog and finally to the source string itself, so an
    untranslated label never breaks a dialog.
    """
    global _catalog, _active_lang
    lang = _plugin_lang()
    if lang != _active_lang:
        _active_lang = lang
        _catalog = {} if lang == _SOURCE_LANG else _load_catalog(lang)
    out = _catalog.get(text)
    if out is None:
        try:
            from core.i18n import tr as app_tr
            out = app_tr(text)
        except Exception:
            out = text
    if kwargs:
        try:
            out = out.format(**kwargs)
        except Exception:
            out = text.format(**kwargs)
    return out


def load_icon(base_name: str, window) -> QIcon:
    """Theme-aware SVG icon: ``_light.svg`` on dark backgrounds, else ``.svg``.

    The palette of ``window`` decides; a missing variant falls back to the
    other one, and a missing pair yields an empty icon instead of raising.
    """
    if not base_name or not os.path.isdir(_ICONS_DIR):
        return QIcon()
    if base_name.endswith(".svg"):
        base_name = base_name[:-4]
    is_dark = True
    try:
        if window is not None:
            bg = window.palette().color(QPalette.Window)
            is_dark = bg.lightness() < 128
    except Exception:
        pass
    key = (base_name, is_dark)
    cached = _icon_cache.get(key)
    if cached is not None:
        return cached
    candidates = (
        [base_name + "_light.svg", base_name + ".svg"] if is_dark
        else [base_name + ".svg", base_name + "_light.svg"]
    )
    icon = QIcon()
    for name in candidates:
        path = os.path.join(_ICONS_DIR, name)
        if os.path.isfile(path):
            icon = QIcon(path)
            break
    _icon_cache[key] = icon
    return icon


# ---------------------------------------------------------------------------
# Image metadata
# ---------------------------------------------------------------------------

def image_metadata(scene, image) -> dict:
    """The metadata record this plugin keeps for ``image`` (always a dict).

    ``core.image_plane.ImagePlane`` declares ``__slots__``, so the georeference
    details cannot ride on the plane itself: they live in
    ``scene.igz_image_metadata`` keyed by ``id(image)``. A missing record is an
    empty dict, never ``None`` — callers read keys without guarding.
    """
    store = getattr(scene, "igz_image_metadata", None)
    if not isinstance(store, dict):
        return {}
    return store.get(id(image)) or {}


def set_image_metadata(scene, image, metadata) -> dict:
    """Store a copy of ``metadata`` for ``image``; return the live store."""
    store = getattr(scene, "igz_image_metadata", None)
    if not isinstance(store, dict):
        store = {}
        scene.igz_image_metadata = store
    store[id(image)] = dict(metadata)
    return store


# ---------------------------------------------------------------------------
# History routing
# ---------------------------------------------------------------------------

def history_for(app):
    """The viewport's undo stack — the one ``Ctrl+Z`` drives.

    A plugin must never build its own ``History`` for an edit: a detached
    stack mutates the document while the viewport's stack, the dirty flag and
    the ``*`` in the title stay untouched. The scene-local fallback exists only
    for hosts that expose no viewport history at all.
    """
    viewport = getattr(app, "viewport", None)
    history = getattr(viewport, "history", None) if viewport is not None else None
    if history is not None:
        return history
    scene = getattr(app, "scene", None)
    if scene is None and viewport is not None:
        scene = getattr(viewport, "scene", None)
    from core.history import History
    return History(scene)


def execute(app, command) -> bool:
    """Run ``command`` on the document history and refresh the viewport.

    Returns ``False`` when the host rolled the command back (``History``
    catches the exception, restores the mesh and records ``last_error``) or
    when the command declined to happen (``CommandRejected``). IngeTrazo's
    ``History.execute`` never raises, so callers must check this value before
    claiming success or binding metadata to objects that may not exist.
    """
    history = history_for(app)
    history.execute(command)
    viewport = getattr(app, "viewport", None)
    notify = getattr(viewport, "notify_scene_changed", None)
    if callable(notify):
        notify()
    return not (getattr(history, "last_error", None)
                or getattr(history, "last_rejected", None))