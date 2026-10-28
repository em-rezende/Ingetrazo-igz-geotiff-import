# SPDX-License-Identifier: GPL-3.0-or-later
"""Reload an image from its source file (in case it changed on disk)."""

import os
import importlib.util as _ilu
import sys
from PySide6.QtWidgets import QMessageBox
from core.history import Command


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


def _invalidate_texture(image):
    """Ask the host to drop any cached texture for a plane (best effort)."""
    for name in ("invalidate_texture", "invalidate"):
        hook = getattr(image, name, None)
        if callable(hook):
            try:
                hook()
                return
            except Exception:
                pass
    texture = getattr(image, "texture", None)
    reload_hook = getattr(texture, "reload", None)
    if callable(reload_hook):
        try:
            reload_hook()
        except Exception:
            pass


class _ReloadPathCommand(Command):
    """Point image planes at freshly cached textures as ONE undo step.

    Reload re-encodes the file on disk and swaps ``ImagePlane.path``; the old
    path is kept so ``Ctrl+Z`` puts the previous texture back. Going through a
    private ``History`` would leave the viewport's stack (and the dirty flag)
    untouched — the edit would be real but undoable by nothing.
    """

    def __init__(self, changes):
        self._changes = [(image, str(new_path)) for image, new_path in changes]
        self._old = []

    def do(self, scene):
        self._old = [image.path for image, _new in self._changes]
        for image, new_path in self._changes:
            image.path = new_path
            _invalidate_texture(image)
        scene.version += 1

    def undo(self, scene):
        for (image, _new), old_path in zip(self._changes, self._old):
            image.path = old_path
            _invalidate_texture(image)
        scene.version += 1


def _get_original_path(scene, img):
    """The ``.tif`` on disk: from the plugin metadata, then the plane itself."""
    meta_dict = getattr(scene, "igz_image_metadata", None)
    if meta_dict:
        meta = meta_dict.get(id(img))
        if meta and "original_path" in meta:
            return meta["original_path"]

    if hasattr(img, "original_path") and img.original_path:
        return img.original_path
    if hasattr(img, "source_path") and img.source_path:
        return img.source_path

    return None


def run(app, params):
    scene = getattr(app, "scene", None)
    if scene is None:
        return
    imgs = getattr(scene, "image_planes", None) or []
    if not imgs:
        QMessageBox.information(app.window, tr("Reload Image"),
                                tr("There are no imported images."))
        return

    # --- NOVA LÓGICA DE SELEÇÃO ---
    # 1. Tenta pegar a imagem ativa (definida via Images List)
    active = getattr(scene, "igz_active_image", None)

    # 2. Tenta pegar seleção explícita (caso o IngeTrazo mude no futuro)
    sel = [img for img in imgs if img in (getattr(scene, "selection", None) or [])]

    selected = []
    if active:
        selected = [active]
    elif sel:
        selected = sel
    elif len(imgs) == 1:
        selected = [imgs[0]]

    if not selected:
        QMessageBox.information(
            app.window, tr("Reload Image"),
            tr("Please select an image in the 'Images List' dialog first."))
        return

    sucessos = 0
    erros = []
    changes = []

    for img in selected:
        caminho_original = _get_original_path(scene, img)

        if not caminho_original:
            erros.append(f"{getattr(img, 'name', 'Image')}: " +
                         tr("The original path is not saved in metadata. Re-import the image."))
            continue

        if not os.path.isfile(caminho_original):
            erros.append(f"{getattr(img, 'name', 'Image')}: " +
                         tr("Source file not found:") + f" '{caminho_original}'")
            continue

        try:
            from georef.geotiff import read_info, read_rgba, rgba_to_qimage
            from core.texture import cache_image
            from PySide6.QtCore import QBuffer, QIODevice

            # 1. Lê os metadados do original
            info = read_info(caminho_original)
            if not info:
                raise ValueError(tr("Could not read GeoTIFF metadata."))

            # 2. Lê os pixels e converte para QImage
            rgba, _ = read_rgba(info, max_px=4096)
            qimage = rgba_to_qimage(rgba)

            # 3. Salva no cache novamente
            buffer = QBuffer()
            buffer.open(QIODevice.WriteOnly)
            qimage.save(buffer, "PNG")
            img_bytes = bytes(buffer.data())
            buffer.close()

            # 4. Novo caminho de cache do ImagePlane. A troca é aplicada pela
            #    _ReloadPathCommand, para que Ctrl+Z restaure o caminho anterior.
            name = os.path.splitext(os.path.basename(caminho_original))[0]
            novo_cached_path = str(cache_image(img_bytes, name, "imported"))
            changes.append((img, novo_cached_path))
            sucessos += 1

        except Exception as e:
            import traceback
            traceback.print_exc()
            erros.append(f"{getattr(img, 'name', 'Image')}: {type(e).__name__}: {e}")

    if changes and not _core.execute(app, _ReloadPathCommand(changes)):
        QMessageBox.critical(
            app.window, tr("Reload Image"),
            tr("The operation was rolled back; the document is unchanged."))
        return

    if sucessos > 0 and not erros:
        QMessageBox.information(app.window, tr("Reload Image"),
                                f"{sucessos} {tr('image(s) reloaded from disk.')}")
    elif sucessos > 0 and erros:
        QMessageBox.warning(app.window, tr("Reload Image"),
                            f"{sucessos} {tr('image(s) reloaded from disk.')}\n\n" +
                            tr("Errors:") + "\n" + "\n".join(erros))
    else:
        QMessageBox.critical(app.window, tr("Reload Image"),
                             tr("Could not reload any image:") + "\n\n" + "\n".join(erros))