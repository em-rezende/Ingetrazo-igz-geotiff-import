# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture the drawn map area (base-map tiles) as a georeferenced image plane.

The capture is taken from the viewport's own export pipeline
(``Viewport.render_image``, ``overlays=False``), projected back to screen with
the public ``Viewport.world_to_pixel`` API, and inserted with the host's
``AddImagePlaneCommand`` — one undo step, dirty flag included. The camera is
put in **Top Parallel** (orthographic, looking straight down) first, because a
perspective view would shear the tiles.
"""

import os
import importlib.util as _ilu
import sys
import math
import time
from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QPushButton, QLabel
from PySide6.QtGui import QVector3D, QImage, QPainter, QPolygonF, QColor
from PySide6.QtCore import QPointF, QPoint, QBuffer, QIODevice, Qt, QTimer
from core.history import AddImagePlaneCommand
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


def _get_polygon_from_scene(scene):
    """The selected area's corners in world metres, or ``None``.

    Accepts a selected face (the corners of its edges), selected edges, or
    three or more selected vertices — the three ways IngeTrazo lets a user mark
    an area. Duplicated corners are dropped before the outline is ordered.
    """
    lm = getattr(scene, "loose_mesh", None)
    sel = getattr(scene, "selection", None)
    if lm is None or not sel:
        return None

    pts = []

    def add(point):
        if point is None:
            return
        if not isinstance(point, QVector3D):
            try:
                point = QVector3D(point.x(), point.y(), point.z())
            except Exception:
                return
        if any((existing - point).lengthSquared() < 1e-12 for existing in pts):
            return
        pts.append(point)

    for face in getattr(lm, "faces", []):
        if face not in sel:
            continue
        for edge in getattr(face, "edges", []):
            add(getattr(edge, "a", None))
            add(getattr(edge, "b", None))

    for edge in getattr(lm, "edges", []):
        if edge in sel:
            add(getattr(edge, "a", None))
            add(getattr(edge, "b", None))

    for item in sel:
        if isinstance(item, QVector3D):
            add(item)

    if len(pts) < 3:
        return None

    # Order the corners around their centroid: the top view makes this the
    # outline the user drew, and a simple polygon is what the mask needs.
    center_x = sum(p.x() for p in pts) / len(pts)
    center_y = sum(p.y() for p in pts) / len(pts)
    pts.sort(key=lambda p: math.atan2(p.y() - center_y, p.x() - center_x))
    return pts


def _render_view(vp):
    """The view without interactive overlays, or ``None`` when GL is absent.

    ``Viewport.render_image`` is the host's own export path: it reuses the
    ``paintGL`` pipeline and leaves out the snap marker, hover and rubber band.
    The widget render is only a fallback for hosts without it — and it asks for
    the background alone, never ``DrawChildren``, so the plugin's orange
    rubber-band overlay cannot end up inside the capture.
    """
    render = getattr(vp, "render_image", None)
    if callable(render):
        try:
            image = render(vp.width(), vp.height(), overlays=False)
        except Exception:
            image = None
        if image is not None and not image.isNull():
            return image
    image = QImage(vp.width(), vp.height(), QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    try:
        vp.render(painter, QPoint(0, 0), vp.rect(), vp.RenderFlag.DrawWindowBackground)
    except Exception:
        return None
    finally:
        painter.end()
    return None if image.isNull() else image


def _execute_capture(app, scene, vp, polygon_pts):
    """Crop the rendered view to ``polygon_pts`` and insert it as a plane."""
    min_x_3d = min(p.x() for p in polygon_pts)
    max_x_3d = max(p.x() for p in polygon_pts)
    min_y_3d = min(p.y() for p in polygon_pts)
    max_y_3d = max(p.y() for p in polygon_pts)

    # 1. Renderiza a vista sem os overlays interativos
    render_img = _render_view(vp)
    if render_img is None:
        QMessageBox.critical(app.window, tr("Capture Map"), tr("Failed to render view."))
        return

    # 2. Projeta os pontos do polígono com a API pública world_to_pixel,
    #    escalando dos pixels lógicos do widget para os da imagem renderizada
    #    (render_image pode devolver outro tamanho).
    scale_x = render_img.width() / float(max(vp.width(), 1))
    scale_y = render_img.height() / float(max(vp.height(), 1))
    screen_points = []
    try:
        for p in polygon_pts:
            res = vp.world_to_pixel(p)
            if not res:
                raise ValueError("world_to_pixel failed for one of the points.")
            screen_points.append(QPointF(float(res[0]) * scale_x,
                                         float(res[1]) * scale_y))
    except Exception as e:
        QMessageBox.critical(app.window, tr("Capture Map"), tr("Failed to project points:") + f"\n{e}")
        return

    # 3. Máscara com os pontos exatos da tela
    mask = QImage(render_img.width(), render_img.height(), QImage.Format_ARGB32)
    mask.fill(Qt.transparent)
    painter = QPainter(mask)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(255, 255, 255, 255))
    painter.drawPolygon(QPolygonF(screen_points))
    painter.end()

    # 4. Aplica a máscara na renderização
    cropped_full = QImage(render_img.width(), render_img.height(), QImage.Format_ARGB32)
    cropped_full.fill(Qt.transparent)
    painter = QPainter(cropped_full)
    painter.drawImage(0, 0, render_img)
    painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    painter.drawImage(0, 0, mask)
    painter.end()

    # 5. Recorta a Bounding Box exata do polígono na tela
    x_min = int(min(sp.x() for sp in screen_points))
    x_max = int(max(sp.x() for sp in screen_points))
    y_min = int(min(sp.y() for sp in screen_points))
    y_max = int(max(sp.y() for sp in screen_points))

    x_min = max(0, x_min)
    y_min = max(0, y_min)
    x_max = min(render_img.width(), x_max)
    y_max = min(render_img.height(), y_max)

    final_img = cropped_full.copy(x_min, y_min, x_max - x_min, y_max - y_min)

    if final_img.width() < 1 or final_img.height() < 1:
        QMessageBox.warning(app.window, tr("Capture Map"), tr("The selected area is too small to be cropped."))
        return

    # 6. Salva no cache
    try:
        from core.texture import cache_image
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        final_img.save(buffer, "PNG")
        img_bytes = bytes(buffer.data())
        buffer.close()

        name = "Map_Capture_" + time.strftime("%Y%m%d_%H%M%S")
        cached_path = str(cache_image(img_bytes, name, "imported"))
    except Exception as e:
        QMessageBox.critical(app.window, tr("Capture Map"), tr("Failed to save capture:") + f"\n{e}")
        return

    # 7. Insere no mundo 3D
    width_3d = max_x_3d - min_x_3d
    height_3d = max_y_3d - min_y_3d

    new_origin = QVector3D(min_x_3d, min_y_3d, 0.0)
    new_u = QVector3D(width_3d, 0.0, 0.0)
    new_v = QVector3D(0.0, height_3d, 0.0)
    aspect = final_img.height() / float(final_img.width())

    try:
        new_img = ImagePlane(
            path=cached_path,
            origin=new_origin,
            u=new_u,
            v=new_v,
            aspect=aspect,
            name=name,
            layer=_core.LAYER_IMAGES,
            locked=True,
        )

        new_meta = {
            "pixel_scale": (width_3d / final_img.width(),
                            height_3d / final_img.height()),
            "image_size": (final_img.width(), final_img.height()),
            "near_origin": True,
            "original_path": cached_path,
        }

        # True UTM of the capture's lower-left corner, read from the scene
        # datum: it anchors lat/lon at the local origin (0,0,0), which is what
        # keeps a georeferenced model in float32-friendly coordinates.
        datum = getattr(scene, "georef", None)
        if datum is not None and hasattr(datum, "local_to_utm"):
            east, north, _alt = datum.local_to_utm(new_origin)
            northern = bool(getattr(datum, "northern", True))
            new_meta.update({
                "utm_origin": (east, north),
                "utm_epsg": (32600 if northern else 32700) + datum.zone,
                "utm_zone": datum.zone,
                "utm_northern": northern,
                "coord_system": "utm",
            })
            lat, lon, _z = datum.local_to_geodetic(new_origin)
            new_meta["wgs84_origin"] = (lat, lon)
        else:
            # No datum: the plane still lands correctly in local metres, and
            # the record says so instead of inventing a zone.
            new_meta.update({
                "utm_origin": (new_origin.x(), new_origin.y()),
                "utm_epsg": None,
                "utm_zone": None,
                "utm_northern": None,
                "coord_system": "local",
                "wgs84_origin": None,
            })

        # One undo step on the viewport's stack — Ctrl+Z removes the capture.
        if not _core.execute(app, AddImagePlaneCommand(new_img)):
            QMessageBox.critical(
                app.window, tr("Capture Map"),
                tr("The operation was rolled back; the document is unchanged."))
            return
        _core.set_image_metadata(scene, new_img, new_meta)
        scene.igz_active_image = new_img
        _core.load_module("tools/rubber_band").refresh(app.window)

        QMessageBox.information(app.window, tr("Capture Map"), tr("Map captured successfully!"))

    except Exception as e:
        import traceback
        traceback.print_exc()
        QMessageBox.critical(app.window, tr("Capture Map"), tr("Failed to insert capture into the scene:") + f"\n{e}")


def run(app, params):
    viewport = getattr(app, "viewport", None)
    scene = getattr(app, "scene", None)
    if scene is None and viewport is not None:
        scene = getattr(viewport, "scene", None)
    if scene is None or viewport is None:
        return

    tile_layer = getattr(scene, "tile_layer", None)
    if tile_layer is None:
        QMessageBox.information(app.window, tr("Capture Map"), tr("No active base map."))
        return

    polygon_pts = _get_polygon_from_scene(scene)
    if not polygon_pts or len(polygon_pts) < 3:
        QMessageBox.information(app.window, tr("Capture Map"), tr("Select the clipping polygon first."))
        return

    vp = viewport

    dlg = QDialog(app.window)
    dlg.setWindowTitle(tr("Capture Map"))
    dlg.setMinimumWidth(400)
    layout = QVBoxLayout(dlg)

    msg = QLabel(tr(
        "Capturing the map requires the camera to be in Top Orthographic mode.\n\n"
        "1. Click 'Prepare View' to adjust the camera.\n"
        "2. Click 'Capture Map' to crop."
    ))
    msg.setWordWrap(True)
    layout.addWidget(msg)

    btn_preparar = QPushButton(tr("Prepare View (Top Parallel)"))
    btn_capturar = QPushButton(tr("Capture Map"))
    btn_capturar.setEnabled(False)  # Só habilita depois de preparar

    layout.addWidget(btn_preparar)
    layout.addWidget(btn_capturar)

    def preparar_vista():
        cam = getattr(vp, "camera", None)
        if cam is None:
            return

        min_x_3d = min(p.x() for p in polygon_pts)
        max_x_3d = max(p.x() for p in polygon_pts)
        min_y_3d = min(p.y() for p in polygon_pts)
        max_y_3d = max(p.y() for p in polygon_pts)
        center_x = (min_x_3d + max_x_3d) / 2.0
        center_y = (min_y_3d + max_y_3d) / 2.0
        width_3d = max(max_x_3d - min_x_3d, 1e-6)
        height_3d = max(max_y_3d - min_y_3d, 1e-6)

        # Top Parallel: straight down, north up. OrbitCamera handles the exact
        # 90° pitch (its up_vector switches to the north axis), so the plan
        # does not roll.
        if hasattr(cam, "perspective"):
            cam.perspective = False
        if hasattr(cam, "two_point"):
            cam.two_point = False
        if hasattr(cam, "target"):
            cam.target = QVector3D(center_x, center_y, 0.0)
        if hasattr(cam, "pitch"):
            cam.pitch = math.radians(90.0)
        if hasattr(cam, "yaw"):
            cam.yaw = math.radians(-90.0)

        # Parallel framing is derived from the distance:
        # half_height = distance * tan(fov/2), half_width = half_height*aspect.
        # Fit both axes of the polygon with a 10 % margin, instead of guessing
        # a multiple of its longest side.
        if hasattr(cam, "distance"):
            aspect = max(float(getattr(cam, "aspect", 1.0) or 1.0), 1e-6)
            half_fov = math.tan(math.radians(float(getattr(cam, "fov_deg", 45.0))) / 2.0)
            fit_height = height_3d * 0.5
            fit_width = (width_3d * 0.5) / aspect
            cam.distance = max(fit_height, fit_width) / max(half_fov, 1e-6) * 1.1

        vp.update()
        btn_capturar.setEnabled(True)
        btn_preparar.setText(tr("View Ready!"))
        btn_preparar.setEnabled(False)

    def executar_captura():
        dlg.accept()
        QTimer.singleShot(100, lambda: _execute_capture(app, scene, vp, polygon_pts))

    btn_preparar.clicked.connect(preparar_vista)
    btn_capturar.clicked.connect(executar_captura)

    dlg.exec()