# SPDX-License-Identifier: GPL-3.0-or-later
"""List all imported images with actions."""

import os
import importlib.util as _ilu
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QDialogButtonBox, QMessageBox, QLabel
)
from PySide6.QtGui import QVector3D, QColor
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


def get_active_image(scene):
    return getattr(scene, "igz_active_image", None)


def set_active_image(scene, img):
    try:
        scene.igz_active_image = img
    except Exception:
        pass


def ensure_active_image(app, prompt_if_missing=True):
    scene = getattr(app, "scene", None)
    if scene is None:
        return None
    img = get_active_image(scene)
    if img is not None:
        return img
    if not prompt_if_missing:
        return None
    imgs = getattr(scene, "image_planes", None) or []
    if not imgs:
        QMessageBox.information(app.window, tr("No images"),
                                tr("There are no imported images.") + "\n\n" +
                                tr("Use 'Import GeoTIFF' first."))
        return None
    run(app, {})
    return get_active_image(scene)


def _get_image_meta(scene, img):
    meta_dict = getattr(scene, "igz_image_metadata", None)
    if meta_dict is not None:
        meta = meta_dict.get(id(img))
        if meta is not None:
            return meta
    return {}


def run(app, params):
    scene = getattr(app, "scene", None)
    if scene is None:
        return
    imgs = getattr(scene, "image_planes", None) or []
    if not imgs:
        QMessageBox.information(app.window, tr("Images List"),
                                tr("There are no imported images."))
        return

    dlg = QDialog(app.window)
    dlg.setWindowTitle(tr("Imported Images"))
    dlg.setMinimumWidth(700)
    layout = QVBoxLayout(dlg)

    layout.addWidget(QLabel(f"<b>{len(imgs)}</b> " + tr("image(s) imported:")))

    table = QTableWidget()
    table.setColumnCount(6)
    table.setHorizontalHeaderLabels([
        tr("Name"), tr("UTM origin"), tr("EPSG"), tr("Size"),
        tr("World size"), tr("Status")
    ])
    table.setRowCount(len(imgs))
    for i, img in enumerate(imgs):
        meta = _get_image_meta(scene, img)
        name = getattr(img, "name", os.path.basename(getattr(img, "path", ""))) or "unnamed"
        utm = meta.get("utm_origin")
        if utm is None:
            origin = getattr(img, "origin", None)
            if origin is not None:
                utm = (origin.x(), origin.y())
        utm_str = f"({utm[0]:.1f}, {utm[1]:.1f})" if utm else "—"
        epsg = meta.get("utm_epsg")
        epsg_str = str(epsg) if epsg else "—"
        size = meta.get("image_size")
        size_str = f"{size[0]}×{size[1]}" if size else "—"
        ps = meta.get("pixel_scale")
        if ps and size:
            world = f"{size[0]*abs(ps[0]):.1f}×{size[1]*abs(ps[1]):.1f}"
        else:
            world = "—"
        is_active = (get_active_image(scene) is img)
        status = "★ ACTIVE" if is_active else "—"
        for col, val in enumerate([name, utm_str, epsg_str, size_str, world, status]):
            item = QTableWidgetItem(val)
            if is_active:
                item.setBackground(QColor(200, 255, 200))
            table.setItem(i, col, item)
    table.setColumnWidth(0, 160)
    table.setColumnWidth(1, 160)
    table.setColumnWidth(2, 60)
    table.setColumnWidth(3, 80)
    table.setColumnWidth(4, 100)
    table.setColumnWidth(5, 90)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    layout.addWidget(table)

    row_buttons = QHBoxLayout()
    btn_select = QPushButton(tr("Select"))
    btn_zoom = QPushButton(tr("Zoom"))
    btn_delete = QPushButton(tr("Delete"))
    btn_rubber = QPushButton(tr("Rubber Band"))
    for b in (btn_select, btn_zoom, btn_delete, btn_rubber):
        b.setMaximumWidth(120)
        b.setMinimumWidth(80)
    row_buttons.addWidget(btn_select)
    row_buttons.addWidget(btn_zoom)
    row_buttons.addWidget(btn_delete)
    row_buttons.addWidget(btn_rubber)
    layout.addLayout(row_buttons)

    def get_selected_image():
        row = table.currentRow()
        if row < 0 or row >= len(imgs):
            return None
        return imgs[row]

    def refresh_table():
        for i, im in enumerate(imgs):
            is_active = (get_active_image(scene) is im)
            status = "★ ACTIVE" if is_active else "—"
            item = table.item(i, 5)
            if item:
                item.setText(status)
                item.setBackground(QColor(200, 255, 200) if is_active else QColor(0, 0, 0, 0))

    def do_select():
        img = get_selected_image()
        if img is None:
            return
        set_active_image(scene, img)
        refresh_table()
        try:
            rb_mod = _load_local_rb()
            rb_mod.refresh(app.window)
        except Exception:
            pass

    def do_zoom():
        img = get_selected_image()
        if img is None:
            return
        set_active_image(scene, img)
        refresh_table()
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
            rb_mod = _load_local_rb()
            rb_mod.refresh(app.window)
        except Exception:
            pass

    def do_delete():
        img = get_selected_image()
        if img is None:
            return
        resp = QMessageBox.question(
            dlg, tr("Delete Image"),
            tr("Delete this image?") + "\n\n" + tr("This action can be undone with Ctrl+Z."),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if resp != QMessageBox.Yes:
            return
        row = table.currentRow()
        try:
            if not _core.execute(app, DeleteImagePlanesCommand([img])):
                QMessageBox.warning(
                    dlg, tr("Delete Image"),
                    tr("The operation was rolled back; the document is unchanged."))
                return
            if get_active_image(scene) is img:
                set_active_image(scene, None)
            if row >= 0:
                table.removeRow(row)
            _load_local_rb().refresh(app.window)
        except Exception as e:
            QMessageBox.warning(dlg, tr("Delete Image"), str(e))

    def do_toggle_rubber():
        try:
            rb_mod = _load_local_rb()
            ov = rb_mod._ensure_overlay(app.window)
            if ov is not None:
                novo_estado = not ov.is_visible()
                ov.set_visible(novo_estado)
                if novo_estado:
                    if getattr(scene, "igz_active_image", None) is None:
                        imgs_local = getattr(scene, "image_planes", None) or []
                        if imgs_local:
                            set_active_image(scene, imgs_local[0])
                            refresh_table()
        except Exception:
            pass

    btn_select.clicked.connect(do_select)
    btn_zoom.clicked.connect(do_zoom)
    btn_delete.clicked.connect(do_delete)
    btn_rubber.clicked.connect(do_toggle_rubber)

    btns = QDialogButtonBox(QDialogButtonBox.Close)
    btns.rejected.connect(dlg.reject)
    btns.accepted.connect(dlg.accept)
    layout.addWidget(btns)
    dlg.exec()


def _load_local_rb():
    return _core.load_module("tools/rubber_band")