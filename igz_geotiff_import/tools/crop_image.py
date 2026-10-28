# SPDX-License-Identifier: GPL-3.0-or-later
"""Crop the active GeoTIFF image using a drawn polygon."""

import os
import importlib.util as _ilu
import sys
from PySide6.QtWidgets import QMessageBox
from PySide6.QtGui import QVector3D, QImage, QPolygonF, QPainter, QColor
from PySide6.QtCore import QPointF, QBuffer, QIODevice, Qt
from core.history import AddImagePlaneCommand, CompoundCommand, DeleteImagePlanesCommand
from core.image_plane import ImagePlane


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

LAYER_CROPPED = _core.LAYER_CROPPED


def _load_list():
    return _core.load_module("tools/list_images")


def _get_image_meta(scene, img):
    meta_dict = getattr(scene, "igz_image_metadata", None)
    if meta_dict is not None:
        return meta_dict.get(id(img), {})
    return {}


def _get_polygon_from_scene(scene, img):
    """Busca agressiva por um polígono que esteja sobre a imagem ativa."""
    lm = getattr(scene, "loose_mesh", None)
    if lm is None:
        return None

    faces = getattr(lm, "faces", [])

    sel = getattr(scene, "selection", None)
    if sel:
        for f in faces:
            if f in sel:
                return list(getattr(f, "vertices", []))

        v_pts = [v for v in sel if hasattr(v, "x")]
        if len(v_pts) >= 3:
            return v_pts

    if faces:
        center_x = img.origin.x() + (img.u.x() + img.v.x()) * 0.5
        center_y = img.origin.y() + (img.u.y() + img.v.y()) * 0.5

        for f in faces:
            pts = list(getattr(f, "vertices", []))
            if len(pts) >= 3:
                poly = QPolygonF([QPointF(p.x(), p.y()) for p in pts])
                if poly.containsPoint(QPointF(center_x, center_y), Qt.OddEvenFill):
                    return pts

                fx = sum(p.x() for p in pts) / len(pts)
                fy = sum(p.y() for p in pts) / len(pts)
                if (min(img.origin.x(), img.origin.x()+img.u.x(), img.origin.x()+img.v.x()) <= fx <=
                    max(img.origin.x(), img.origin.x()+img.u.x(), img.origin.x()+img.v.x())):
                    return pts
    return None


def _perform_crop(app, scene, img, polygon_pts):
    """Executa a matemática de recorte com QImage."""
    meta = _get_image_meta(scene, img)
    img_size = meta.get("image_size")
    if not img_size:
        QMessageBox.warning(app.window, tr("Crop Image"), tr("Image size metadata missing."))
        return
    width_px, height_px = img_size

    origin = img.origin
    u = img.u
    v = img.v
    u_len_sq = u.x()**2 + u.y()**2 + u.z()**2
    v_len_sq = v.x()**2 + v.y()**2 + v.z()**2

    if u_len_sq < 1e-6 or v_len_sq < 1e-6:
        return

    uv_poly = []
    min_u, max_u = 1.0, 0.0
    min_v, max_v = 1.0, 0.0

    for pt in polygon_pts:
        dp = pt - origin
        u_coord = (dp.x() * u.x() + dp.y() * u.y() + dp.z() * u.z()) / u_len_sq
        v_coord = (dp.x() * v.x() + dp.y() * v.y() + dp.z() * v.z()) / v_len_sq

        u_coord = max(0.0, min(1.0, u_coord))
        v_coord = max(0.0, min(1.0, v_coord))

        uv_poly.append(QPointF(u_coord, v_coord))
        min_u = min(min_u, u_coord)
        max_u = max(max_u, u_coord)
        min_v = min(min_v, v_coord)
        max_v = max(max_v, v_coord)

    x_min = int(min_u * width_px)
    x_max = int(max_u * width_px)
    y_min = int((1.0 - max_v) * height_px)
    y_max = int((1.0 - min_v) * height_px)

    # Recorte com QImage nativo
    try:
        original = QImage(img.path)
        if original.isNull():
            raise ValueError("Could not load image from cache.")

        if original.format() != QImage.Format_ARGB32:
            original = original.convertToFormat(QImage.Format_ARGB32)

        cache_w, cache_h = original.width(), original.height()
        scale_x = cache_w / float(width_px)
        scale_y = cache_h / float(height_px)

        # 1. Cria a máscara poligonal
        mask = QImage(cache_w, cache_h, QImage.Format_ARGB32)
        mask.fill(Qt.transparent)
        painter = QPainter(mask)
        painter.setRenderHint(QPainter.Antialiasing)
        qpoly = QPolygonF()
        for pt in uv_poly:
            qpoly.append(QPointF(pt.x() * cache_w, (1.0 - pt.y()) * cache_h))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 255))
        painter.drawPolygon(qpoly)
        painter.end()

        # 2. Aplica a máscara
        cropped_full = QImage(cache_w, cache_h, QImage.Format_ARGB32)
        cropped_full.fill(Qt.transparent)
        painter = QPainter(cropped_full)
        painter.drawImage(0, 0, original)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, mask)
        painter.end()

        # 3. Corta a bounding box exata do polígono
        cx_min = int(x_min * scale_x)
        cx_max = int(x_max * scale_x)
        cy_min = int(y_min * scale_y)
        cy_max = int(y_max * scale_y)
        final_img = cropped_full.copy(cx_min, cy_min, cx_max - cx_min, cy_max - cy_min)

        if final_img.width() < 1 or final_img.height() < 1:
            raise ValueError(tr("The selected area is too small to be cropped."))

        # 4. Salva no cache do IngeTrazo
        from core.texture import cache_image
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        final_img.save(buffer, "PNG")
        img_bytes = bytes(buffer.data())
        buffer.close()

        name = os.path.splitext(os.path.basename(getattr(img, "name", "image")))[0] + "_cropped"
        cached_path = str(cache_image(img_bytes, name, "imported"))

    except Exception as e:
        QMessageBox.critical(app.window, tr("Crop Image"),
                             tr("Failed to process image:") + f"\n{type(e).__name__}: {e}")
        return

    # --- MATEMÁTICA DE POSICIONAMENTO 3D ---
    new_origin_x = origin.x() + u.x() * min_u + v.x() * min_v
    new_origin_y = origin.y() + u.y() * min_u + v.y() * min_v
    new_origin_z = origin.z() + u.z() * min_u + v.z() * min_v

    width_ratio = max_u - min_u
    height_ratio = max_v - min_v

    new_u = QVector3D(u.x() * width_ratio, u.y() * width_ratio, u.z() * width_ratio)
    new_v = QVector3D(v.x() * height_ratio, v.y() * height_ratio, v.z() * height_ratio)

    new_aspect = final_img.height() / float(final_img.width()) if final_img.width() > 0 else 1.0

    try:
        new_img = ImagePlane(
            path=cached_path,
            origin=QVector3D(new_origin_x, new_origin_y, new_origin_z),
            u=new_u, v=new_v, aspect=new_aspect,
            name=getattr(img, "name", "Cropped") + " (Cropped)",
            layer=LAYER_CROPPED,
            locked=True,
        )

        new_meta = dict(meta)
        if "utm_origin" in new_meta:
            u_step = (u_len_sq ** 0.5) * min_u
            v_step = (v_len_sq ** 0.5) * min_v
            new_meta["utm_origin"] = (new_meta["utm_origin"][0] + u_step, new_meta["utm_origin"][1] + v_step)
        new_meta["image_size"] = (int(final_img.width() / scale_x), int(final_img.height() / scale_y))
        new_meta["original_path"] = cached_path

        # Pergunta ao usuário se deseja apagar a imagem original
        resp = QMessageBox.question(
            app.window, tr("Crop Image"),
            tr("Image cropped successfully!") + "\n\n" +
            tr("Do you want to delete the original image?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        apagar_original = (resp == QMessageBox.Yes)

        # ONE undo step for the whole crop: the new plane appears and, when
        # asked, the original disappears. Both are the host's own commands;
        # AddImagePlaneCommand also creates the crop layer and takes it back
        # on undo.
        commands = [AddImagePlaneCommand(new_img)]
        if apagar_original:
            commands.append(DeleteImagePlanesCommand([img]))
        if not _core.execute(app, CompoundCommand(commands)):
            QMessageBox.critical(
                app.window, tr("Crop Image"),
                tr("The operation was rolled back; the document is unchanged."))
            return

        _core.set_image_metadata(scene, new_img, new_meta)
        scene.igz_active_image = new_img
        rb_mod = _core.load_module("tools/rubber_band")
        rb_mod.refresh(app.window)
    except Exception as e:
        import traceback
        traceback.print_exc()
        QMessageBox.critical(app.window, tr("Crop Image"),
                             tr("Failed to create new image plane:") + f"\n{type(e).__name__}: {e}")


def run(app, params):
    scene = getattr(app, "scene", None)
    if scene is None:
        scene = app.viewport.scene if hasattr(app, "viewport") else None
    if scene is None:
        return

    img = getattr(scene, "igz_active_image", None)
    if img is None:
        list_mod = _load_list()
        img = list_mod.ensure_active_image(app)
        if img is None:
            return

    polygon_pts = _get_polygon_from_scene(scene, img)

    if not polygon_pts:
        QMessageBox.information(
            app.window, tr("Crop Image"),
            tr("No polygon found over the image.\n\n"
               "Please draw a polygon (or rectangle) over the active image "
               "and try again.")
        )
        return

    _perform_crop(app, scene, img, polygon_pts)