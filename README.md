# Evervibes

A static GitHub Pages site with a backend explainer as its landing page and a manga shelf on a separate page.

## Pages

- `index.html` is the backend explainer and discreet two-step code screen.
- `shelf.html` is the responsive manga shelf and reader.
- `manga-preview.html` previews the shelf locally.

## Adding manga

Drop ZIP archives into the existing `manga-zips` inbox and run `python prepare_mangas.py` from this folder. The importer sorts archives and pages, adds the new volume entries to `shelf.html`, and refreshes the preview.

## Publishing and access

Publish the repository with GitHub Pages. The code screen is a visual gate only: static pages and image URLs can be inspected or opened directly. Use server-side authentication and protected image storage for real access control.
