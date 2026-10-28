# igz_geotiff_import — GeoTIFF Import & GIS Toolkit for IngeTrazo

**English** · [Português (Brasil)](README_ptBR.md)

A robust, full-featured toolbar extension for [IngeTrazo](https://github.com/ingelibre/ingetrazo) designed to import, manage, annotate, and georeference **GeoTIFF images** (UTM and Web Mercator).

Unlike standard image importers, this plugin seamlessly places orthophotos and satellite imagery at their correct spatial positions by anchoring the scene's `SceneDatum`. It preserves geographic fidelity while keeping the 3D camera stable near the local origin `(0,0,0)`, preventing the notorious float32 jitter caused by raw UTM coordinates.

This plugin provides a complete suite of GIS-like tools inside IngeTrazo: coordinate labeling, UTM zone reprojection (without moving the geometry), coordinate grids, interactive point coordinate placement, image cropping with layer management, **map tile capture**, and a centralized image management panel.

- **Author:** Ezequiel M. Rezende
- **Version:** 1.4.0 (Added **Capture Map** for tile-layer screenshots)
- **Tested with:** IngeTrazo 0.5.8 (Windows / Linux)
- **License:** GPL-3.0-or-later — same as IngeTrazo

---

![IngeTrazo with the "GeoTIFF Import" toolbar and a georeferenced orthophoto](screenshots/igz_geotiff_import.png)

*The **GeoTIFF Import** toolbar. On screen: a UTM orthophoto anchored in the local frame, the **Imported Images** list detailing UTM origin and EPSG, the orange **rubber-band** outlining the active image, and the **Add Coordinates** labels at each corner.*

---

## Installation

### Manual Installation
1. Download or clone this repository.
2. Locate IngeTrazo's plugins folder:
   - **Linux:** `~/.local/share/ingetrazo/plugins/`
   - **Windows:** `%APPDATA%\ingetrazo\plugins\`
   - (Or use **Extensions ▸ Open plugins folder** inside IngeTrazo).
3. Move the unpacked **`igz_geotiff_import`** folder into that plugins directory.
4. Restart IngeTrazo.

The **GeoTIFF Import** toolbar will appear in the top area, and an **Extensions ▸ GeoTIFF Import** submenu will be created.

### Dependencies
**No external Python packages are required.** The importer natively utilizes IngeTrazo's internal `georef.geotiff` module (to read metadata and pixels) and `core.texture.cache_image` (to cache the image for the 3D viewport). The **Capture Map** tool uses only `PySide6` (`QImage`, `QPainter`, `QBuffer`) and IngeTrazo's native `viewport.world_to_pixel`. You do not need to install `GDAL`, `PIL`, `numpy`, `tifffile`, or any other third-party library. The plugin runs entirely on IngeTrazo's embedded Python interpreter.

---

## How to Use Each Tool

Below is the detailed step-by-step guide on how to interact with each of the thirteen tools available in the toolbar.

### 1. Import GeoTIFF
* **What it does:** Brings the georeferenced image into the scene and inserts it into the `IGZ_GeoTIFF_Images` layer.
* **How to use:**
  1. Click the **Import GeoTIFF** button.
  2. Select one or more `.tif`/`.tiff` files from disk.
  3. A window will appear showing the metadata (EPSG, UTM Zone, size). Choose whether future labels will use **UTM** (meters) or **WGS84** (Latitude/Longitude).
  4. If this is the first image in the scene, IngeTrazo will ask whether to anchor the Datum at the image's location. Click **Yes**.
  5. The image will appear near the origin `(0,0,0)` and is ready to use.

### 2. Images List
* **What it does:** Opens a management panel with all imported images (originals, cropped, and map captures).
* **How to use:**
  1. Click **Images List**.
  2. You will see a table with **Name**, **UTM origin**, **EPSG**, **Size**, **World size**, and **Status** (★ ACTIVE).
  3. Select a row and use the buttons below:
     * **Select:** Makes the image active (highlighted in green).
     * **Zoom:** Zooms to and activates the image.
     * **Delete:** Deletes the selected image.
     * **Rubber Band:** Toggles the orange outline.

### 3. Zoom to Image
* **What it does:** Moves the 3D camera to perfectly frame the active image on screen.
* **How to use:** Select an image (via *Images List*) and click the **Zoom to Image** button. If no image is active, the plugin will open the list automatically for you to choose.

### 4. Toggle Rubber Band
* **What it does:** Turns on or off a bright orange line that outlines the active image.
* **How to use:** Click the button. The outline updates in real time during model rotation (Orbit) and panning (Pan).

### 5. Check Zones
* **What it does:** Checks whether there are images in the scene using different UTM zones.
* **How to use:** Click the button. If all images are in the same zone, a confirmation message appears. If there is a mix (e.g., Zone 23S and 22S), the plugin will warn you, since mosaics across different zones do not align perfectly without prior reprojection.

### 6. Reload Image
* **What it does:** Reloads the image from the original file on disk (`.tif`).
* **How to use:** Select the image (via *Images List*) and click **Reload Image**. It will find the original `.tif` file at the saved path (`original_path`), rebuild the texture, and update the scene without moving the image. This is useful if you edited the orthophoto in QGIS.
* **Note:** If the image is a crop (`Cropped`), Reload will reload the crop's own cached PNG, preserving the size and position at the moment of cropping. The original full-resolution `.tif` is **not** recoverable unless it was kept on disk (i.e., you answered **No** to the "delete original?" prompt during cropping).

### 7. Add Coordinates
* **What it does:** Creates text labels at the four corners of the active image.
* **How to use:**
  1. Select the active image.
  2. Click **Add Coordinates**.
  3. Confirm the dialog. **Note:** the "Label spacing" field is currently reserved for future use; labels are always placed at the four corners of the image.
  4. Labels will appear in the `IGZ_GeoTIFF_Labels` layer. The text will be in UTM (e.g., `E: 609770.7 / N: 7797202.6`) or WGS84, depending on what was chosen during import.

### 8. Add Point Coordinate
* **What it does:** Activates an interactive tool to mark coordinates at specific points on the image.
* **How to use:**
  1. Click **Add Point Coordinate**.
  2. The cursor will change to an orange crosshair.
  3. Click anywhere on the image. A label with the exact coordinate of that pixel will be created.
  4. Keep clicking to add as many points as you like.
  5. Press **ESC** (or switch to the Select tool) to finish.

### 9. Coordinate Grid
* **What it does:** Draws a grid of lines over the image.
* **How to use:**
  1. Select the image.
  2. Click **Coordinate Grid**.
  3. Enter the spacing in meters (e.g., 100 m).
  4. The grid will be drawn and grouped into the `IGZ_GeoTIFF_Grid` layer.

### 10. Reproject Image
* **What it does:** Changes the geographic reference (e.g., from UTM 23S to 22S) without moving the image in space.
* **How to use:**
  1. With the image active, click **Reproject Image**.
  2. In the dialog, confirm the Source Zone, Source Hemisphere, Target Zone, and Target Hemisphere.
  3. Click OK. The image will remain at exactly the same screen pixel, but all metadata and labels will be recalculated for the new zone.

### 11. Crop Image
* **What it does:** Crops the active image using a polygon or rectangle drawn over it. The crop is moved to the `IGZ_GeoTIFF_Cropped_Images` layer.
* **How to use:**
  1. Select the active image (via *Images List*).
  2. Use IngeTrazo's native drawing tool (Rectangle or Polygon) to draw the crop area over the image.
  3. Click **Crop Image**.
  4. The plugin will extract the area and create a new, perfectly aligned image plane.
  5. A window will ask: *"Do you want to delete the original image?"*. The default is **Yes**; choose **No** to keep both. The whole operation (creating the crop + optionally deleting the original) happens in a single `Ctrl+Z` step.

### 12. Capture Map
* **What it does:** Captures (screenshot) the area of a polygon/rectangle drawn over the **base map (tile layer)** and inserts it into the scene as a new georeferenced image, perfectly aligned to the drawn rectangle.
* **How to use:**
  1. Draw a polygon or rectangle with IngeTrazo's native drawing tool over the base map. **Select it**.
  2. Click the **Capture Map** button.
  3. In the dialog, click **Prepare View (Top Parallel)**. The camera moves to an **orthographic top view** centered on the polygon (`pitch = 90°`, `yaw = −90°` so north stays up and the plan is not rolled); the distance is computed to fit both axes of the polygon with a 10 % margin. Capture is enabled only after this step.
  4. Click **Capture Map**. The view is rendered through the viewport's own export path (`Viewport.render_image(..., overlays=False)`), masked exactly by the polygon (projected with `viewport.world_to_pixel`), cropped to its bounding box, and saved to cache. If the projected polygon is smaller than **1 × 1 pixel**, the capture aborts with a warning.
  5. A new locked `ImagePlane` (`locked=True`) is created in the `IGZ_GeoTIFF_Images` layer, becomes the **active image**, and its metadata is stored in `igz_image_metadata`. The insertion uses the host's `AddImagePlaneCommand`, so a single **Ctrl+Z** removes the capture and marks the document dirty exactly once.
* **Note:** An active `scene.tile_layer` and a selected polygon with at least 3 vertices are required.

### 13. Delete Images
* **What it does:** Removes all georeferenced images from the scene.
* **How to use:** Click **Delete Images**, confirm the deletion, and if you change your mind, press **Ctrl+Z** to undo.

---

## Math and Logic (Deep Dive)

Below is the technical explanation of how each Python file (attached to the plugin) operates behind the scenes.

### 1. `core.py` (i18n, Icons, Metadata and History Routing)
* **Logic:** Acts as the plugin's utility center — a single module instance shared by every tool.
* **Math/Programming:**
  * **i18n:** Intercepts the host language (`core.i18n.current_language()`) and loads the matching JSON (`pt-BR.json`, `es.json`, …), falling back to IngeTrazo's own `core.i18n.tr` and finally to the English source string.
  * **Icons:** `load_icon` detects the toolbar brightness with `QPalette.Window.lightness() < 128` and picks `<name>_light.svg` on dark themes or `<name>.svg` on light ones (cached per name/theme).
  * **Module loading:** `load_module(name)` imports a file relative to the plugin folder by absolute path with `importlib.util`, registering it under a private name — the same rule IngeTrazo applies to plugins (`sys.path` is never touched).
  * **Metadata:** `image_metadata` / `set_image_metadata` read and write `scene.igz_image_metadata[id(image)]`, since `ImagePlane.__slots__` leaves no room for extra attributes.
  * **History:** `history_for(app)` returns `app.viewport.history` (falling back to a scene-local `History` only when a host has none) and `execute(app, command)` runs a command there and notifies the viewport — the one road every mutation in this plugin takes.

### 2. `__init__.py` (Entry Point)
* **Logic:** The plugin orchestrator, following the documented `setup(app)` contract for package extensions.
* **Programming:** Dynamically imports every tool module by absolute path (`importlib.util`) and builds **one `QAction` per tool**, shared by the `QToolBar` and the *Extensions ▸ GeoTIFF Import* submenu — one connection, one translated label and one tooltip. The toolbar is registered on `app.window` (`Qt.TopToolBarArea`) and the menu through `app.add_menu(...)`. The rubber-band overlay widget is pre-installed on the viewport at `setup()` time, so it is available independently of whether the toolbar toggle has been clicked. `__version__` is re-exported from `core`.

### 3. `geotiff_importer.py` (Import)
* **Logic:** The plugin's geodetic heart.
* **Math:**
  * **Reading:** Reads the transformation matrix (`info.transform`), which contains the pixel scale (pixel size in meters) and the tiepoint (UTM coordinate of the top-left corner).
  * **UTM -> WGS84 Conversion:** Implements Snyder's equations for the Transverse Mercator projection. Computes the meridian arc (`m`), the footpoint latitude (`mu`), and uses Taylor series (`e1`, `phi1`) to find the real latitude and longitude.
  * **Local Anchoring:** Takes the lat/lon and uses `SceneDatum` to project into the local 3D space. This prevents the model from being thrown 600,000 meters from the origin (which would cause float32 precision loss in OpenGL). For **batch imports**, the plugin computes the centroid of all images' lat/lon, then picks the image **closest to that centroid** to use as the Datum anchor, so the whole batch lands near the origin.
  * **Layer and Texture:** Reads the pixels, applies the `height_px / width_px` ratio, creates the texture, and uploads it to the GPU via `core.texture.cache_image`. The `ImagePlane` is assigned to the `IGZ_GeoTIFF_Images` layer and the original `.tif` file path is saved in the `original_path` metadata.

### 4. `zoom_to_image.py` (Framing)
* **Logic:** Camera adjustment.
* **Math:** Computes the image's geometric center `(xmin+xmax)/2`. The camera distance is set to `max(width, height, depth) * 1.5 + 10.0` to ensure the image fits entirely on screen with a 50% margin.

### 5. `list_images.py` (Manager)
* **Logic:** A `QDialog` with a `QTableWidget`.
* **Programming:** Reads the `scene.igz_image_metadata` dictionary using `id(img)` as the key. Organizes the data into a table (Name, UTM origin, EPSG, Size, World size, Status) and allows the user to trigger commands (Zoom, Delete) directly. Deletions go through the host's `DeleteImagePlanesCommand` on `viewport.history`, guaranteeing `Ctrl+Z`; the dialog also clears the active image when it deletes that plane.

### 6. `rubber_band.py` (Selection Overlay)
* **Logic:** A transparent, mouse-click-through overlay widget (`QWidget`).
* **Math:** It intercepts the viewport's `paintEvent`. For each of the image's 4 corners (in 3D space), it uses `viewport.world_to_pixel(corner)` to project to 2D screen space. Then, it draws an orange polygon via `QPainter.drawPolygon`. Since it redraws every frame, the line perfectly follows camera rotation.

### 7. `check_zones.py` (Zone Checker)
* **Logic:** Mosaic integrity validation.
* **Programming:** Scans all `image_planes` and reads each one's `(utm_zone, utm_epsg)` from `scene.igz_image_metadata[id(img)]` (the plane itself has `__slots__` and carries no CRS attributes). If there is more than one distinct pair, it builds a message listing the conflicts; if there is only one, it confirms everything is consistent; if no image carries zone metadata, it says so instead of claiming success.

### 8. `reload_image.py` (Reload)
* **Logic:** Update without deletion, operating directly on the original file.
* **Programming:**
  * Looks up the original path in `igz_image_metadata` (key `original_path`). If it doesn't exist, shows an error.
  * Reads the `.tif` file with `georef.geotiff` and rebuilds the cache with `core.texture.cache_image`.
  * Updates `img.path` to the new cache through a plugin command (`_ReloadPathCommand`) on the viewport history, keeping the previous path so `Ctrl+Z` restores the old texture.
  * If the image is a crop (whose `original_path` points to the crop's PNG), it reloads itself without deforming the image. **However**, the original full-resolution `.tif` is not recoverable from a crop unless it was kept on disk.

### 9. `add_coordinates.py` (Corner Labels)
* **Logic:** Mathematical conversion of local 3D coordinates to UTM/WGS84 text.
* **Math:**
  * Uses the `datum.local_to_utm(pt)` function to find the real coordinates.
  * If the system is WGS84, applies the inverse UTM formula to find latitude and longitude.
  * Creates `TextLabel` objects anchored in 3D space, but with a `Z + 1.0` offset to float slightly above the image, making them easier to read. They are added to the `IGZ_GeoTIFF_Labels` layer.
  * **Note:** the "Label spacing" field in the dialog is currently reserved for future use; labels are always placed at the four corners of the image.

### 10. `add_point_coord.py` (Interactive Tool)
* **Logic:** A subclass of IngeTrazo's native `Tool`.
* **Programming:**
  * Replaces the cursor with a programmatically drawn `QPixmap` (an orange crosshair).
  * Intercepts `on_click(ctx)`. The `ctx.world` already provides the exact 3D coordinate of the click (accounting for depth and camera perspective).
  * Passes that 3D point to the same mathematical conversion function from `add_coordinates.py`, generating an individual label.

### 11. `coord_grid.py` (Coordinate Grid)
* **Logic:** Procedural line generation.
* **Math:**
  * Takes the image's origin (`img.origin`) and its direction vectors `u` (X axis) and `v` (Y axis).
  * Normalizes these vectors to find the image's azimuth in space (since the image may be rotated).
  * Iterates from `0` to the total length (`ulen` and `vlen`) in steps equal to the spacing (`step`).
  * Creates the lines with `AddEdgeCommand`, adding them to the `IGZ_GeoTIFF_Grid` layer.

### 12. `reproject_image.py` (CRS Change Without Moving the Image)
* **Logic:** Spatial position preservation and metadata update.
* **Math and Algorithm (The Great Innovation):**
  1. **Origin Preservation:** The `img.origin` point (where the image is in the local 3D model) **is not changed**.
  2. **Geodetic Extraction:** The plugin determines the real Latitude and Longitude of that `img.origin` point in the current Datum. It first tries `datum.local_to_geodetic(pt)`; if unavailable, it falls back to `datum.local_to_utm(pt)` followed by `_utm_to_wgs84(...)`.
  3. **Computation in the New Zone:** Takes that lat/lon and applies the Transverse Mercator formulas from `_wgs84_to_utm` for the **new target zone** (e.g., Zone 22S). This yields a new `(Easting, Northing)` pair.
  4. **Metadata Update:** The `igz_image_metadata` dictionary is updated with the new `utm_origin`, `utm_zone`, and `epsg`. The entire image "believes" it is now in the new zone, but its geometric space has not changed.
  5. **Label Rewrite:** The code scans all `TextLabel`s in the `IGZ_GeoTIFF_Labels` layer. **Lat/lon labels are detected by text prefix** (`Lat`, `Lon`, case-insensitive) and left untouched, since they do not depend on the UTM zone. **UTM labels** are re-derived from their 3D anchor using the new metadata and rewritten as `label.text = f"E: {new_e:.1f}\nN: {new_n:.1f}"`.
  6. **Safe Undo:** Metadata and texts are grouped in a `CompoundCommand` — an `EditTextLabelCommand` for each rewritten label plus a small command that swaps the `igz_image_metadata` record. A single `Ctrl+Z` restores the old metadata and the old texts in one go.

### 13. `crop_image.py` (Crop with Spatial Preservation and Layers)
* **Logic:** Crops the texture while keeping local and geographic coordinates perfectly aligned, promoting layer organization.
* **Math and Algorithm:**
  1. **3D to UV Conversion:** Reads the vertices of the drawn polygon and projects them orthogonally onto the original image's plane using the Dot Product (`u_coord = (dp · u) / |u|²`). The result is a bounding box from 0.0 to 1.0.
  2. **Mask and Crop:** Instead of using `Pillow`, the plugin uses native `QImage` and `QPainter`. It draws the polygon onto an alpha-channel mask and uses `CompositionMode_DestinationIn` to erase everything outside the polygon. Then it crops the bounding box.
  3. **Anchoring:** The new `ImagePlane` is anchored at the **bottom-left corner** of the polygon. The new `u` and `v` vectors are computed by multiplying the original vectors by the proportional difference (e.g., `max_u - min_u`). This ensures the cropped image occupies exactly the rectangle drawn in 3D space, without "floating" or misaligning.
  4. **Layer and Metadata:** The new plane is inserted into the `IGZ_GeoTIFF_Cropped_Images` layer. Its `original_path` is set to its own cache path (so a future `Reload` won't load the large `.tif` file and squeeze the image). The user is asked whether to delete the original image (**default: Yes**). Creating the new plane and deleting the old one are handed to a single `CompoundCommand` of the host's `AddImagePlaneCommand` / `DeleteImagePlanesCommand`, so the whole crop is one `Ctrl+Z` step.

### 14. `capture_map.py` (Map Capture)
* **Logic:** Converts the area drawn over the **base map (tile layer)** into a new georeferenced `ImagePlane`, aligned to the selected polygon.
* **Programming and Math:**
  * **Validation:** Requires an active `scene.tile_layer` and a selected polygon (min. 3 vertices). Vertices are extracted from the selected `loose_mesh` faces and edges, sorted by angle around the centroid to guarantee correct closure.
  * **Prepare View:** Moves the camera to an **orthographic top view** centered on the polygon's center. Computes `center = ((min_x+max_x)/2, (min_y+max_y)/2)`, `pitch = 90°` and `yaw = −90°` (in **radians**, as IngeTrazo expects), and a distance that fits the polygon on both axes: `distance = max(height/2, (width/2)/aspect) / tan(fov/2) × 1.1`. Only then is the capture button enabled.
  * **Off-screen Render:** Uses `Viewport.render_image(width, height, overlays=False)` — the host's own export pipeline, which renders the GL scene into an FBO without the snap marker, hover or the plugin's orange rubber band. If a host lacks that API, it falls back to `viewport.render(...)`, asking for the background only (never `DrawChildren`, so the overlay cannot leak into the picture).
  * **3D → 2D Projection:** For each polygon vertex, uses `viewport.world_to_pixel(p)` to obtain the exact screen coordinates, scaled from widget logical pixels to the rendered image size when they differ. If the API fails, it aborts with an error.
  * **Mask and Compositing:** Draws the projected polygon onto a mask (`QPainter.Antialiasing`) and applies it with `CompositionMode_DestinationIn`, erasing everything outside the polygon.
  * **Bounding Box:** Crops the `final_img` from the `min/max` of the screen points (clamped to `[0, width/height]`). If the crop is **< 1 px**, it warns and aborts.
  * **Cache:** Serializes the PNG into a `QBuffer` and saves it via `core.texture.cache_image(img_bytes, name, "imported")`, with a timestamped name (`Map_Capture_YYYYMMDD_HHMMSS`).
  * **Insertion into the World:** Creates a new `ImagePlane` with `origin = (min_x, min_y, 0)` (bottom-left corner of the 3D polygon), `u = (width_3d, 0, 0)`, and `v = (0, height_3d, 0)`. The `aspect = height_px / width_px` ratio is preserved. The image is **`locked=True`** (does not drift with the ground plane) and inserted into the `IGZ_GeoTIFF_Images` layer.
  * **Metadata:** Reads the scene's `SceneDatum` — which anchors lat/lon at the local origin `(0,0,0)` — and stores the **true UTM** of the bottom-left corner (`utm_origin`, via `datum.local_to_utm`), `utm_zone`, `utm_northern`, `utm_epsg` (32600/32700 + zone), `wgs84_origin` (via `datum.local_to_geodetic`), `pixel_scale` (metres per pixel of the capture), `image_size`, `near_origin`, and `original_path` (the cached PNG) in `igz_image_metadata[id(new_img)]`. Without a datum it stores local metres and `coord_system="local"` instead of inventing a CRS.
  * **Undo:** A single `AddImagePlaneCommand` on `viewport.history` — the same stack `Ctrl+Z` drives. The command creates the layer and removes it again on undo, so the document, the dirty flag and the title's `*` stay consistent.

### 15. `delete_images.py` (Deletion)
* **Logic:** Clean removal of every imported image, with history.
* **Programming:** Groups all `image_planes` into a single `DeleteImagePlanesCommand` executed on `viewport.history` (never a private stack), so the official IngeTrazo command keeps the Undo/Redo tree — and the document's dirty flag — impeccable. Deleting the active image clears the plugin's active-image reference.

---

## Architecture & File Structure

```text
<plugins>/
└── igz_geotiff_import/
    ├── __init__.py              # setup(app): toolbar + Extensions menu
    ├── core.py                  # i18n (tr), icons, metadata, history routing
    ├── README.md
    ├── README_ptBR.md
    ├── screenshots/             # Images used by both READMEs
    │   └── igz_geotiff_import.png
    ├── icons/                   # SVG icons (light/dark themes)
    │   ├── geotiff_import.svg / _light.svg
    │   ├── geotiff_capture.svg / _light.svg
    │   ├── geotiff_list.svg / _light.svg
    │   ├── geotiff_zoom.svg / _light.svg
    │   ├── geotiff_rubber.svg / _light.svg
    │   ├── geotiff_warning.svg / _light.svg
    │   ├── geotiff_reload.svg / _light.svg
    │   ├── geotiff_coords.svg / _light.svg
    │   ├── geotiff_point.svg / _light.svg
    │   ├── geotiff_grid.svg / _light.svg
    │   ├── geotiff_reproject.svg / _light.svg
    │   ├── geotiff_crop.svg / _light.svg
    │   └── geotiff_delete.svg / _light.svg
    ├── i18n/                    # JSON translation catalogs (same key set)
    │   └── en.json, pt-BR.json, de.json, es.json, fr.json, it.json, zh-CN.json
    └── tools/
        ├── __init__.py          # Package marker (tools load by absolute path)
        ├── geotiff_importer.py  # Core logic for reading and positioning
        ├── capture_map.py       # Tile-layer capture to a new ImagePlane
        ├── zoom_to_image.py     # Camera framing
        ├── list_images.py       # Image management dialog
        ├── rubber_band.py       # Viewport overlay
        ├── check_zones.py       # CRS mismatch warning
        ├── reload_image.py      # File re-reader
        ├── add_coordinates.py   # Corner labeling
        ├── add_point_coord.py   # Interactive labeling tool
        ├── coord_grid.py        # Grid edge generation
        ├── reproject_image.py   # Zone/UPS reprojection logic
        ├── crop_image.py        # Polygon cropping with layer and CRS preservation
        └── delete_images.py     # Undoable batch deletion
```

At the repository root (outside the installable package): `LICENSE`,
`THIRD-PARTY.md`, `.gitignore` and the `Desenvolvimento/` working folder
(local only, never committed).

---

## Georeferencing & Metadata Details

When an image is imported (or captured from the tile layer), it stores its original georeferencing in `scene.igz_image_metadata[id(image)]`.

| Key | Meaning |
| :--- | :--- |
| `utm_origin` | `(x, y)` in the image's native CRS |
| `utm_epsg` | EPSG code (e.g., 31983 for UTM 23S, 3857 for Web Mercator) |
| `utm_zone` | UTM zone (1–60), or `None` for Web Mercator |
| `utm_northern` | `True` for the northern hemisphere, `False` for southern |
| `pixel_scale` | `(scale_x, scale_y)` from the GeoTIFF transform |
| `image_size` | `(width_px, height_px)` |
| `near_origin` | Always `True` (the plugin always uses the Datum) |
| `coord_system` | `"utm"` or `"wgs84"` (chosen during import) |
| `wgs84_origin` | `(lat, lon)` of the bottom-left corner |
| `original_path` | Absolute path to the source `.tif` file (or the cropped/captured cache) |

> **Note on `Capture Map`:** the capture's metadata is derived from the scene's `SceneDatum` (`datum.local_to_utm` / `datum.local_to_geodetic`), so `utm_origin` and `wgs84_origin` are **real coordinates** of the polygon's bottom-left corner in the datum's zone — nothing is hardcoded. `pixel_scale` is the capture's metres-per-pixel, and `original_path` points to the cached PNG (not a `.tif`), so `Reload` re-reads that PNG. When the scene has no datum, the record keeps local metres and sets `coord_system="local"`.

---

## The Undo/Redo Architecture

Every mutation in this plugin (Import, **Capture Map**, Delete, Reproject, Labels, Grid, Crop) is routed through IngeTrazo's command layer and executed on **`viewport.history`** — the same stack `Ctrl+Z` drives. No tool builds a private `History`: a detached stack would change the document while leaving the viewport's stack, the dirty flag and the title's `*` untouched. `core.execute(app, command)` is the single place that routes a command and calls `viewport.notify_scene_changed()`.

Multi-file imports, cropping (including the optional deletion of the original image), coordinate-label batches, grids, reprojections and **map captures** are composed from the host's own commands (`AddImagePlaneCommand`, `DeleteImagePlanesCommand`, `AddTextLabelCommand`, `AddEdgeCommand`, `AssignLayerCommand`, `EditTextLabelCommand`), grouped by `CompoundCommand` where several are involved. Each tool therefore lands on the viewport's history as **one** step: a single `Ctrl+Z` reverts the whole operation, and the document's dirty flag follows.

---

## Known Limitations

The following behaviors are **intentional or current limitations** of version 1.4.0. They are documented here so users are not surprised by the results:

- **`Capture Map` — needs a datum for UTM metadata:** with a `SceneDatum` the record carries the true UTM/WGS84 coordinates; without one it stores local metres and `coord_system="local"` (the image still lands correctly in the scene).
- **`Capture Map` — resolution follows the view:** the capture is rendered at the viewport's pixel size, so zoom in before capturing when you need more detail.
- **`Capture Map` — `Prepare View` changes the camera:** it forces orthographic projection, `pitch = 90°`, `yaw = −90°` (north up, no roll) and centers the camera on the polygon. Any manual rotation is replaced — that is what makes the tiles capture without shear.
- **`Capture Map` — minimum size:** If the projected polygon is smaller than 1 × 1 pixel on screen, the capture aborts with a warning.
- **`Add Coordinates` — "Label spacing" is reserved:** The field exists in the dialog but is not yet used. Labels are always placed at the four corners of the active image.
- **`Reproject Image` — lat/lon label detection is textual:** Labels are considered "lat/lon" (and left untouched) only if their text starts with `Lat` or `Lon` (case-insensitive). Labels using other prefixes (e.g., `L:`, `Y:`, or localized equivalents) will be incorrectly rewritten as UTM. If you need custom formats, edit the labels manually after reprojection.
- **`Reload Image` — crops are not full-resolution:** After cropping, `original_path` points to the crop's cached PNG. `Reload` re-reads that PNG, not the original `.tif`. To recover full resolution, keep the original `.tif` on disk (i.e., answer **No** to the "delete original?" prompt during cropping) and re-import it.
- **i18n — Chinese catalog filename:** The catalog is shipped as `zh-CN.json` (ISO 639-1). If your IngeTrazo build reports a different language code via `core.i18n.current_language()` (e.g., `zh-Hans`, `zh-CH`, `zh_TW`), rename the file accordingly or the plugin will fall back to English for Chinese users.

---

## Compatibility with the IngeTrazo Plugin API

According to [`docs/plugins.md`](https://github.com/ingelibre/ingetrazo/blob/main/docs/plugins.md), the plugin API is not yet stable in the 0.x series. This plugin follows the official guidelines for package extensions:

- a module-level `setup(app)` receiving a `views.extension_api.ExtensionApp` (`app.window`, `app.viewport`, `app.scene`, `app.add_menu`);
- absolute-path loading with `importlib.util` (a plugin directory never enters `sys.path`);
- fault tolerance: nothing raises while IngeTrazo is starting, and tools report errors in dialogs.

It also relies on some stable internal symbols of IngeTrazo (tested with 0.5.8):

- `georef.geotiff` and `georef.datum.SceneDatum` (metadata, pixels, local ↔ geodetic)
- `core.texture.cache_image` (texture caching)
- `core.image_plane.ImagePlane` (3D plane base class)
- `core.history` (undo/redo commands: `AddImagePlaneCommand`, `DeleteImagePlanesCommand`, `AddEdgeCommand`, `AssignLayerCommand`, `AddTextLabelCommand`, `EditTextLabelCommand`, `CompoundCommand`)
- `core.layers` and `core.textlabel` (layer and text management)
- `views.viewport.Viewport` (`history`, `notify_scene_changed`, `world_to_pixel`, `render_image`)

---

## License

GPL-3.0-or-later — the same license as IngeTrazo.

Copyright (C) 2026 Ezequiel M. Rezende.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License, version 3 or later, as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful, but **without any warranty**; without even the implied warranty of **merchantability** or **fitness for a particular purpose**. See the GNU General Public License for more details.

See <https://www.gnu.org/licenses/gpl-3.0.html>.

