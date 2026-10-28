# SPDX-License-Identifier: GPL-3.0-or-later
"""GeoTIFF Import — importer logic com Datum automático."""

import os
import sys
import math
import importlib.util as _ilu
from PySide6.QtWidgets import (
    QFileDialog, QMessageBox, QDialog, QVBoxLayout,
    QRadioButton, QGroupBox, QDialogButtonBox, QLabel
)
from PySide6.QtGui import QVector3D
from PySide6.QtCore import QStandardPaths


_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_core():
    """The plugin's shared ``core`` module (i18n, icons, history routing)."""
    mod = sys.modules.get("_igz_geotiff_core")
    if mod is not None:
        return mod
    path = os.path.join(_HERE, "..", "core.py")
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

LAYER_IMAGES = _core.LAYER_IMAGES


# ---------------------------------------------------------------------------
# Conversões geodésicas
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


def _web_mercator_to_wgs84(x, y):
    R = 6378137.0
    lon = (x / R) * (180.0 / math.pi)
    lat = (2.0 * math.atan(math.exp(y / R)) - (math.pi / 2.0)) * (180.0 / math.pi)
    return lat, lon


def _coords_to_latlon(x, y, epsg, zone, northern):
    """Converte qualquer sistema suportado (UTM ou Web Mercator) para lat/lon."""
    if epsg == 3857 or zone is None:
        return _web_mercator_to_wgs84(x, y)
    return _utm_to_wgs84(x, y, zone, northern)


# ---------------------------------------------------------------------------
# Datum
# ---------------------------------------------------------------------------

def _ensure_datum(app, scene, lat, lon):
    datum = getattr(scene, "georef", None)
    if datum is not None:
        return datum

    resp = QMessageBox.question(
        app.window, tr("Configure Datum"),
        tr("The scene has no Datum configured.") + "\n\n" +
        tr("Use the location of this image as the scene anchor?") + "\n\n" +
        f"Lat: {lat:.6f}\nLon: {lon:.6f}\n\n" +
        tr("This will keep the model near the origin and preserve the georeference."),
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes
    )
    if resp != QMessageBox.Yes:
        return None

    try:
        from georef.datum import SceneDatum
        datum = SceneDatum(lat=lat, lon=lon)
        scene.georef = datum
        return datum
    except Exception as e:
        QMessageBox.warning(app.window, tr("Configure Datum"),
                            tr("Could not create the Datum:") + f"\n{type(e).__name__}: {e}")
        return None


# ---------------------------------------------------------------------------
# Construção da ImagePlane
# ---------------------------------------------------------------------------

def _build_image(app, scene, path, info, near_origin, coord_system, datum):
    """Constrói um ImagePlane a partir de um GeoTiffInfo."""
    from PySide6.QtGui import QVector3D
    from PySide6.QtCore import QBuffer, QIODevice

    tx = list(info.transform)
    scale_x = tx[0]
    x_origin = tx[2]
    scale_y = tx[4]
    y_origin_top = tx[5]
    width_px = info.width
    height_px = info.height

    # ─── 1. UTM/WebMercator dos 4 cantos ───
    utm_x0 = x_origin
    utm_y0 = y_origin_top + height_px * scale_y
    utm_x1 = x_origin + width_px * abs(scale_x)
    utm_y1 = utm_y0
    utm_x2 = utm_x0
    utm_y2 = y_origin_top

    # ─── 2. Hemisfério ───
    zone = info.zone
    if info.epsg == 32600 + (zone or 0):
        northern = True
    elif info.epsg == 32700 + (zone or 0):
        northern = False
    else:
        northern = info.northern if info.northern is not None else True

    # ─── 3. Conversão para lat/lon (funções locais do próprio módulo) ───
    def _to_latlon(x, y):
        if info.epsg == 3857 or zone is None:
            return _web_mercator_to_wgs84(x, y)
        else:
            return _utm_to_wgs84(x, y, zone, northern)

    lat0, lon0 = _to_latlon(utm_x0, utm_y0)
    lat1, lon1 = _to_latlon(utm_x1, utm_y1)
    lat2, lon2 = _to_latlon(utm_x2, utm_y2)

    # ─── 4. Conversão para local (via datum) ───
    def _to_local(lat, lon):
        if datum is not None:
            try:
                local = datum.geodetic_to_local(lat, lon, 0.0)
                return (local.x(), local.y())
            except Exception:
                pass
        return (0.0, 0.0)

    lx0, ly0 = _to_local(lat0, lon0)
    lx1, ly1 = _to_local(lat1, lon1)
    lx2, ly2 = _to_local(lat2, lon2)

    # ─── 5. Vetores u e v (com base nos cantos) ───
    u_world = QVector3D(lx1 - lx0, ly1 - ly0, 0.0)
    v_world = QVector3D(lx2 - lx0, ly2 - ly0, 0.0)
    origin = QVector3D(lx0, ly0, 0.0)

    # ─── 6. Cacheia a textura em PNG/WebP ───
    cached_path = path
    try:
        from georef.geotiff import read_rgba, rgba_to_qimage
        from core.texture import cache_image

        rgba, _ = read_rgba(info, max_px=4096)
        qimage = rgba_to_qimage(rgba)

        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        qimage.save(buffer, "PNG")
        img_bytes = bytes(buffer.data())
        buffer.close()

        name = os.path.splitext(os.path.basename(path))[0]
        cached_path_obj = cache_image(img_bytes, name, "imported")
        cached_path = str(cached_path_obj)
    except Exception:
        # The original file stays as the texture source; the import can go on.
        cached_path = path

    # ─── 7. Aspect corrigido (altura / largura) ───
    aspect = height_px / width_px if width_px > 0 else 1.0

    # ─── 8. Cria o ImagePlane ───
    from core.image_plane import ImagePlane
    image = ImagePlane(
        path=cached_path,
        origin=origin,
        u=u_world,
        v=v_world,
        aspect=aspect,
        name=os.path.basename(path),
        layer=LAYER_IMAGES,
        locked=True,
    )

    # ─── 9. Guarda os metadados no scene ───
    _core.set_image_metadata(scene, image, {
        "utm_origin": (utm_x0, utm_y0),
        "utm_epsg": info.epsg,
        "utm_zone": info.zone,
        "utm_northern": northern,
        "pixel_scale": (scale_x, scale_y),
        "image_size": (width_px, height_px),
        "near_origin": near_origin,
        "coord_system": coord_system,
        "wgs84_origin": (lat0, lon0),
        "original_path": path,
    })

    return image
    
    
# ---------------------------------------------------------------------------
# Diálogo
# ---------------------------------------------------------------------------

def _ask_options(app, infos, datum_exists):
    dlg = QDialog(app.window)
    dlg.setWindowTitle(tr("GeoTIFF Import Options"))
    dlg.setMinimumWidth(550)
    layout = QVBoxLayout(dlg)

    n = len(infos)
    if n == 1:
        path, info = infos[0]
        tx = list(info.transform)
        info_text = (
            f"<b>{tr('GeoTIFF info:')}</b><br>"
            f"{tr('File:')} {os.path.basename(path)}<br>"
            f"{tr('Size:')} {info.width} × {info.height} px<br>"
            f"{tr('Origin UTM:')} ({tx[2]:.2f}, {tx[5]:.2f})<br>"
            f"{tr('EPSG:')} {info.epsg or 'N/A'} | "
            f"{tr('Zone:')} {info.zone or 'N/A'}"
        )
    else:
        info_text = f"<b>{n} {tr('files selected.')}</b>"

    lbl = QLabel(info_text)
    lbl.setWordWrap(True)
    layout.addWidget(lbl)

    if not datum_exists:
        aviso_datum = QLabel(
            f"<b>{tr('Note:')}</b> " +
            tr("The scene has no Datum configured. You will be asked to create one.")
        )
        aviso_datum.setWordWrap(True)
        aviso_datum.setStyleSheet("color: #2c7be5;")
        layout.addWidget(aviso_datum)

    group_coord = QGroupBox(tr("Coordinate system for labels"))
    layout_coord = QVBoxLayout(group_coord)
    rb_utm_label = QRadioButton(tr("UTM (East/North, meters)"))
    rb_wgs_label = QRadioButton(tr("WGS84 (Latitude/Longitude, degrees)"))
    rb_utm_label.setChecked(True)
    layout_coord.addWidget(rb_utm_label)
    layout_coord.addWidget(rb_wgs_label)
    layout.addWidget(group_coord)

    btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    layout.addWidget(btns)

    if dlg.exec() != QDialog.Accepted:
        return None
    return {
        "near_origin": True,  # sempre True (sempre usa o Datum)
        "coord_system": "utm" if rb_utm_label.isChecked() else "wgs84",
    }
    
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(app, params):
    scene = getattr(app, "scene", None)
    if scene is None:
        scene = getattr(getattr(app, "viewport", None), "scene", None)
    if scene is None:
        return

    docs = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
    if not docs:
        docs = os.path.expanduser("~")

    paths, _ = QFileDialog.getOpenFileNames(
        app.window,
        tr("Import Georeferenced Image"),
        docs,
        tr("GeoTIFF / TIFF") + " (*.tif *.tiff *.tiff64);;"
        + tr("BigTIFF") + " (*.btf *.bigtiff);;"
        + tr("All supported images") + " (*.tif *.tiff *.tiff64 *.btf *.bigtiff);;"
        + tr("All files") + " (*)"
    )
    if not paths:
        return

    from georef.geotiff import read_info, unsupported_reason

    infos = []
    erros = []
    for path in paths:
        try:
            info = read_info(path)
            motivo = unsupported_reason(info)
            if motivo:
                erros.append(f"{os.path.basename(path)}: {motivo}")
                continue
            if info.transform is None:
                erros.append(f"{os.path.basename(path)}: {tr('no georeferencing transform')}")
                continue
            infos.append((path, info))
        except Exception as e:
            erros.append(f"{os.path.basename(path)}: {type(e).__name__}: {e}")

    if not infos:
        QMessageBox.critical(
            app.window, tr("GeoTIFF Import"),
            tr("No valid GeoTIFF files were found.") + "\n\n" + "\n".join(erros[:10])
        )
        return

    if erros:
        QMessageBox.warning(
            app.window, tr("GeoTIFF Import"),
            tr("Some files were skipped:") + "\n\n" + "\n".join(erros[:10])
        )

    datum = getattr(scene, "georef", None)
    datum_exists = datum is not None

    opts = _ask_options(app, infos, datum_exists)
    if opts is None:
        return

    # Se não tem datum, cria usando o centroide das imagens
    if datum is None and infos:
        latlons = []
        for path, info in infos:
            tx = list(info.transform)
            utm_x = tx[2]
            utm_y = tx[5] + info.height * tx[4]
            zone = info.zone
            if info.epsg == 32600 + (zone or 0):
                northern = True
            elif info.epsg == 32700 + (zone or 0):
                northern = False
            else:
                northern = info.northern if info.northern is not None else True
            lat, lon = _coords_to_latlon(utm_x, utm_y, info.epsg, zone, northern)
            latlons.append((lat, lon))

        if latlons:
            # Média das coordenadas
            avg_lat = sum(p[0] for p in latlons) / len(latlons)
            avg_lon = sum(p[1] for p in latlons) / len(latlons)
            # Imagem mais próxima da média
            best_idx = min(range(len(latlons)), key=lambda i: (latlons[i][0]-avg_lat)**2 + (latlons[i][1]-avg_lon)**2)
            datum = _ensure_datum(app, scene, latlons[best_idx][0], latlons[best_idx][1])
            if datum is None:
                return

    # Constrói as imagens
    imagens = []
    for path, info in infos:
        try:
            img = _build_image(
                app, scene, path, info,
                opts["near_origin"], opts["coord_system"], datum
            )
            imagens.append(img)
        except Exception as e:
            erros.append(f"{os.path.basename(path)}: {type(e).__name__}: {e}")

    if not imagens:
        QMessageBox.critical(
            app.window, tr("GeoTIFF Import"),
            tr("Could not create any image plane.") + "\n\n" + "\n".join(erros[:10])
        )
        return

    from core.history import AddImagePlaneCommand, CompoundCommand

    try:
        # One undo step for the whole import: N planes added together, the
        # layer created by the host's own command (and removed by its undo).
        applied = _core.execute(app, CompoundCommand(
            [AddImagePlaneCommand(img) for img in imagens]))
        if not applied:
            QMessageBox.critical(
                app.window, tr("GeoTIFF Import"),
                tr("The operation was rolled back; the document is unchanged."))
            return
        scene.igz_active_image = imagens[-1]
        rb_mod = _core.load_module("tools/rubber_band")
        rb_mod.refresh(app.window)

        n = len(imagens)
        msg = (
            f"{n} {tr('image(s) imported successfully!')}\n\n"
            f"{tr('Positioning:')} " +
            (tr("Near origin (0,0,0)") if opts["near_origin"] else tr("Real UTM position (for mosaics)")) +
            "\n" + tr("Coordinate system for labels") + ": " + opts["coord_system"].upper() + "\n"
        )
        if erros:
            msg += f"\n{len(erros)} {tr('file(s) skipped.')}"
        QMessageBox.information(app.window, tr("GeoTIFF Import"), msg)

    except Exception as e:
        import traceback
        traceback.print_exc()
        QMessageBox.critical(
            app.window, tr("GeoTIFF Import"),
            tr("Error inserting images:") + f"\n\n{type(e).__name__}: {e}"
        )