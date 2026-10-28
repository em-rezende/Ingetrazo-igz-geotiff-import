# SPDX-License-Identifier: GPL-3.0-or-later
"""Draw a coordinate grid over the active image."""

import os
import importlib.util as _ilu
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
    QDoubleSpinBox, QMessageBox, QLabel
)
from PySide6.QtGui import QVector3D
from core.history import AddEdgeCommand, AssignLayerCommand, Command


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
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "list_images.py")
    spec = _ilu.spec_from_file_location("_igz_geotiff_tools_list_images", path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LAYER_GRID = "IGZ_GeoTIFF_Grid"


class _GridLinesCommand(Command):
    """Draw the whole grid and tag it with its layer as ONE undo step.

    ``AddEdgeCommand`` and ``AssignLayerCommand`` are the host's own commands;
    composing them here — instead of pushing one command per line — keeps a
    hundred-line grid one ``Ctrl+Z`` away, and tags the very edges the mesh
    created. Inventing a private ``History`` would have made none of it
    undoable at all.
    """

    def __init__(self, segments, layer):
        self._segments = [(QVector3D(a), QVector3D(b)) for a, b in segments]
        self._layer = layer
        self._edge_cmds = []
        self._layer_cmd = None

    def do(self, scene):
        self._edge_cmds = [AddEdgeCommand(a, b, merge=False) for a, b in self._segments]
        for cmd in self._edge_cmds:
            cmd.do(scene)
        edges = [cmd.edge for cmd in self._edge_cmds
                 if getattr(cmd, "edge", None) is not None]
        if edges:
            self._layer_cmd = AssignLayerCommand(edges, self._layer)
            self._layer_cmd.do(scene)
        scene.version += 1

    def undo(self, scene):
        if self._layer_cmd is not None:
            self._layer_cmd.undo(scene)
            self._layer_cmd = None
        for cmd in reversed(self._edge_cmds):
            cmd.undo(scene)
        self._edge_cmds = []
        scene.version += 1


def run(app, params):
    scene = getattr(app, "scene", None)
    if scene is None:
        scene = app.viewport.scene if hasattr(app, "viewport") else None
    if scene is None:
        return

    imgs = getattr(scene, "image_planes", None) or []
    if not imgs:
        QMessageBox.information(
            app.window, tr("Coordinate Grid"),
            tr("There are no imported images in the current scene.") + "\n\n" +
            tr("Use 'Import GeoTIFF' first."))
        return

    img = getattr(scene, "igz_active_image", None)
    if img is None:
        list_mod = _load_list()
        img = list_mod.ensure_active_image(app)
        if img is None:
            return

    corners = list(img.corners())
    if len(corners) < 4:
        return

    dlg = QDialog(app.window)
    dlg.setWindowTitle(tr("Coordinate Grid"))
    layout = QVBoxLayout(dlg)
    form = QFormLayout()
    spin = QDoubleSpinBox()
    spin.setRange(0.1, 10000.0)
    spin.setDecimals(1)
    spin.setValue(100.0)
    spin.setSuffix(" m")
    form.addRow(QLabel(tr("Grid spacing:")), spin)
    layout.addLayout(form)
    btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    layout.addWidget(btns)
    if dlg.exec() != QDialog.Accepted:
        return
    step = spin.value()

    origin = img.origin
    u = img.u
    v = img.v
    if origin is None or u is None or v is None:
        return

    ulen = (u.x()**2 + u.y()**2) ** 0.5
    vlen = (v.x()**2 + v.y()**2) ** 0.5
    if ulen < 1e-6 or vlen < 1e-6:
        return

    ux, uy = u.x() / ulen, u.y() / ulen
    vx, vy = v.x() / vlen, v.y() / vlen

    edges = []
    z = origin.z() + 0.1
    n = int(ulen / step) + 1
    for i in range(n + 1):
        t = i * step
        if t > ulen:
            break
        p1 = QVector3D(origin.x() + ux * t, origin.y() + uy * t, z)
        p2 = QVector3D(origin.x() + ux * t + vx * vlen,
                       origin.y() + uy * t + vy * vlen, z)
        edges.append((p1, p2))
    n = int(vlen / step) + 1
    for j in range(n + 1):
        t = j * step
        if t > vlen:
            break
        p1 = QVector3D(origin.x() + vx * t, origin.y() + vy * t, z)
        p2 = QVector3D(origin.x() + vx * t + ux * ulen,
                       origin.y() + vy * t + uy * ulen, z)
        edges.append((p1, p2))

    created_count = len(edges)
    if not _core.execute(app, _GridLinesCommand(edges, LAYER_GRID)):
        QMessageBox.critical(
            app.window, tr("Coordinate Grid"),
            tr("The operation was rolled back; the document is unchanged."))
        return

    QMessageBox.information(
        app.window, tr("Coordinate Grid"),
        f"{created_count} " + tr("grid line(s) drawn.") +
        "\n\n" + tr("Layer:") + f" {LAYER_GRID}")