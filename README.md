# IngeTrazo · GeoTIFF Import

GeoTIFF import and GIS toolkit extension for [IngeTrazo](https://github.com/ingelibre/ingetrazo):
georeferenced orthophotos anchored at the scene datum, coordinate labels, UTM
reprojection, coordinate grids, polygon cropping, **map-tile capture** and an
image manager — all undoable with `Ctrl+Z`.

**Version 1.0.0** · GPL-3.0-or-later · Tested with IngeTrazo 0.5.8 (Windows / Linux)

| Documentation | |
| :--- | :--- |
| English | [`igz_geotiff_import/README.md`](igz_geotiff_import/README.md) |
| Português (Brasil) | [`igz_geotiff_import/README_ptBR.md`](igz_geotiff_import/README_ptBR.md) |

![The GeoTIFF Import toolbar with a georeferenced orthophoto](igz_geotiff_import/screenshots/igz_geotiff_import.png)

## Install

1. Download or clone this repository.
2. Copy the **`igz_geotiff_import`** folder into IngeTrazo's plugins directory:
   - **Windows:** `%APPDATA%\ingetrazo\plugins\`
   - **Linux:** `~/.local/share/ingetrazo/plugins/`
   - (or use **Extensions ▸ Open plugins folder** inside IngeTrazo).
3. Restart IngeTrazo. The **GeoTIFF Import** tool bar and the
   **Extensions ▸ GeoTIFF Import** submenu appear.

No external Python packages are required: the extension runs on IngeTrazo's
embedded interpreter and uses its `georef.geotiff`, `core.texture`,
`core.image_plane` and the official history commands.

## What is in this repository

```text
.
├── igz_geotiff_import/     # the extension itself (install this folder)
│   ├── __init__.py         # setup(app): tool bar + Extensions submenu
│   ├── core.py             # i18n (tr), icons, metadata, history routing
│   ├── tools/              # 13 tool modules, loaded by absolute path
│   ├── icons/              # SVG icons, standard and _light variants
│   ├── i18n/               # en, pt-BR, es, fr, de, it, zh-CN
│   ├── screenshots/
│   ├── README.md
│   └── README_ptBR.md
├── Desenvolvimento/        # local working files (git-ignored)
├── LICENSE
├── THIRD-PARTY.md
└── .gitignore
```

## License

GPL-3.0-or-later — the same license as IngeTrazo. See [`LICENSE`](LICENSE) and
[`THIRD-PARTY.md`](THIRD-PARTY.md).

Copyright (C) 2026 Ezequiel M. Rezende.
