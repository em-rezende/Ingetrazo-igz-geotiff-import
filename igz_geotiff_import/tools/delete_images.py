# SPDX-License-Identifier: GPL-3.0-or-later
"""GeoTIFF Import — delete imported images."""

import os
import importlib.util as _ilu
import sys
from PySide6.QtWidgets import QMessageBox
from core.history import DeleteImagePlanesCommand


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
        QMessageBox.warning(app.window, tr("Delete Images"), tr("No scene available."))
        return

    imagens = getattr(scene, "image_planes", None)
    if not imagens:
        QMessageBox.information(
            app.window, tr("Delete Images"),
            tr("There are no imported images in the current scene.")
        )
        return

    n = len(imagens)
    if n == 1:
        nome = getattr(imagens[0], "name", "") or "unnamed"
        pergunta = f"{tr('Delete the imported image')} '{nome}'?"
    else:
        pergunta = f"{tr('Delete all')} {n} {tr('imported images?')}"

    resposta = QMessageBox.question(
        app.window, tr("Delete Images"),
        pergunta + "\n\n" + tr("This action can be undone with Ctrl+Z."),
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )
    if resposta != QMessageBox.Yes:
        return

    try:
        deleted = list(imagens)
        if not _core.execute(app, DeleteImagePlanesCommand(deleted)):
            QMessageBox.critical(
                app.window, tr("Delete Images"),
                tr("The operation was rolled back; the document is unchanged."))
            return

        # The active image cannot keep pointing at a plane that is gone; the
        # metadata stays, so undoing the deletion brings the labels back.
        if getattr(scene, "igz_active_image", None) in deleted:
            scene.igz_active_image = None
        rb_mod = _core.load_module("tools/rubber_band")
        rb_mod.refresh(app.window)

        QMessageBox.information(
            app.window, tr("Delete Images"),
            f"{n} {tr('image(s) deleted.')}\n\n{tr('You can undo with Ctrl+Z.')}"
        )
    except Exception as e:
        QMessageBox.critical(
            app.window, tr("Delete Images"),
            tr("Could not delete images:") + f"\n\n{type(e).__name__}: {e}"
        )