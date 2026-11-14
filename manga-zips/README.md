# Manga ZIP inbox

Drop one ZIP per manga volume into this folder. Then run this from the website folder:

```powershell
python prepare_mangas.py
```

The importer sorts ZIP filenames naturally (for example `volume2.zip` before `volume10.zip`) and sorts image names within each ZIP. It creates `mN-cover.jpg` and `mN-001.jpg`, `mN-002.jpg`, and so on, starting after the highest manga number already in the website folder. It also updates the volume list and page counts in `index.html` automatically, then generates `manga-preview.html` with the full shelf and a scrollable reader. ZIPs are moved to `processed/` after a successful import. Open `manga-preview.html` in a browser to review the shelf and new pages.

Supported source images: JPG, PNG, WebP, GIF, BMP, and TIFF. Non-JPEG images are converted to JPEG and require Pillow (`python -m pip install Pillow`). If no image is named like a cover, the first naturally sorted page is also used as the shelf cover.
