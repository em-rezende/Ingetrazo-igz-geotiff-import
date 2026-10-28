# SPDX-License-Identifier: GPL-3.0-or-later
"""Rubber band overlay for the active image."""

import os
import importlib.util as _ilu
import sys
from PySide6.QtWidgets import QWidget, QMessageBox
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF
from PySide6.QtCore import Qt, QPointF, QEvent


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


class RubberBandOverlay(QWidget):
    def __init__(self, viewport, main_window):
        super().__init__(viewport)
        self._vp = viewport
        self._mw = main_window
        self._visible = True
        self._last_scene = None
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        viewport.installEventFilter(self)
        self._resize_to_parent()
        self.show()
        self.raise_()

    def _resize_to_parent(self):
        if self._vp is not None:
            self.setGeometry(0, 0, self._vp.width(), self._vp.height())

    def eventFilter(self, obj, ev):
        if obj is self._vp:
            if ev.type() == QEvent.Resize:
                self._resize_to_parent()
            elif ev.type() in (QEvent.MouseMove, QEvent.Wheel,
                               QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
                current_scene = getattr(self._vp, "scene", None)
                if current_scene is not self._last_scene:
                    self._last_scene = current_scene
                self.update()
        return False

    def set_visible(self, visible):
        self._visible = visible
        self.setVisible(visible)

    def is_visible(self):
        return self._visible

    def paintEvent(self, _ev):
        if not self._visible:
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            if (self._vp is not None and
                (self.width() != self._vp.width() or self.height() != self._vp.height())):
                self._resize_to_parent()

            scene = getattr(self._vp, "scene", None)
            if scene is None:
                return

            if scene is not self._last_scene:
                self._last_scene = scene

            img = getattr(scene, "igz_active_image", None)
            if img is None:
                return

            image_planes = getattr(scene, "image_planes", None) or []
            if img not in image_planes:
                return

            try:
                corners = list(img.corners())
                if len(corners) < 4:
                    return

                pts = []
                for c in corners:
                    p = self._vp.world_to_pixel(c)
                    if p is None:
                        return
                    pts.append(QPointF(float(p[0]), float(p[1])))

                poly = QPolygonF(pts)
                pen = QPen(QColor(255, 165, 0, 220))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.setBrush(QColor(255, 165, 0, 40))
                painter.drawPolygon(poly)

                painter.setPen(QPen(QColor(255, 165, 0, 240)))
                painter.drawText(pts[0] + QPointF(4, -4), tr("★ ACTIVE"))
            except Exception:
                pass
        finally:
            painter.end()


_OVERLAY = None


def _ensure_overlay(main_window):
    vp = getattr(main_window, "viewport", None)
    if vp is None:
        return None

    if hasattr(vp, "igz_rubber_band_overlay"):
        ov = getattr(vp, "igz_rubber_band_overlay")
        try:
            _ = ov.isVisible()
            return ov
        except RuntimeError:
            pass

    try:
        ov = RubberBandOverlay(vp, main_window)
        vp.igz_rubber_band_overlay = ov
        return ov
    except Exception:
        return None


def refresh(main_window):
    ov = _ensure_overlay(main_window)
    if ov is not None:
        ov.update()


def toggle_visible(app, params):
    scene = getattr(app, "scene", None)
    if scene is None:
        scene = app.viewport.scene if hasattr(app, "viewport") else None
    if scene is None:
        return

    imgs = getattr(scene, "image_planes", None) or []
    if not imgs:
        QMessageBox.information(
            app.window, tr("Rubber Band"),
            tr("There are no imported images in the current scene.") + "\n\n" +
            tr("Use 'Import GeoTIFF' first."))
        return

    ov = _ensure_overlay(app.window)
    if ov is None:
        return

    novo_estado = not ov.is_visible()
    ov.set_visible(novo_estado)

    if novo_estado:
        img = getattr(scene, "igz_active_image", None)
        if img is None:
            try:
                scene.igz_active_image = imgs[0]
            except Exception:
                pass

    state = tr("ON") if novo_estado else tr("OFF")
    QMessageBox.information(app.window, tr("Rubber Band"), tr("Rubber band is now:") + f" {state}")