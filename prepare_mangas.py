#!/usr/bin/env python3
"""Import manga ZIPs from manga-zips/ into the website's image naming format."""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import zipfile
import json
import os
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent
INBOX = ROOT / "manga-zips"
PROCESSED = INBOX / "processed"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
COVER_WORDS = {"cover", "front", "folder", "thumbnail"}
PREVIEW_PATH = ROOT / "manga-preview.html"


def natural_key(value: str) -> list[object]:
    """Sort names like 1, 2, 10 instead of 1, 10, 2."""
    return [(0, int(part)) if part.isdigit() else (1, part.casefold())
            for part in re.split(r"(\d+)", value)]


def is_hidden_or_metadata(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return any(part.startswith(".") or part == "__MACOSX" for part in path.parts)


def is_cover(name: str) -> bool:
    parts = PurePosixPath(name.replace("\\", "/")).parts
    stem = PurePosixPath(parts[-1]).stem.casefold()
    words = set(re.split(r"[^a-z0-9]+", stem))
    parent_words = {part.casefold() for part in parts[:-1]}
    return bool((words | parent_words) & COVER_WORDS)


def write_as_jpeg(data: bytes, source_name: str, destination: Path) -> None:
    suffix = Path(source_name).suffix.casefold()
    if suffix in {".jpg", ".jpeg"}:
        destination.write_bytes(data)
        return

    try:
        from PIL import Image
        from io import BytesIO
    except ImportError as exc:
        raise RuntimeError(
            f"{source_name} is {suffix or 'not a JPEG'}; install Pillow to convert it "
            "(python -m pip install Pillow), then run the importer again."
        ) from exc

    try:
        with Image.open(BytesIO(data)) as image:
            if getattr(image, "is_animated", False):
                image.seek(0)
            if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                converted = background
            else:
                converted = image.convert("RGB")
            converted.save(destination, format="JPEG", quality=92, optimize=True)
    except Exception as exc:
        raise RuntimeError(f"Could not decode image {source_name}: {exc}") from exc


def existing_manga_number() -> int:
    pattern = re.compile(r"^m(\d+)-cover\.jpg$", re.IGNORECASE)
    numbers = []
    for path in ROOT.iterdir():
        match = pattern.match(path.name)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0)


VOLUME_ARRAY_RE = re.compile(r"const volumes\s*=\s*\[(.*?)\]\s*;", re.DOTALL)
VOLUME_ENTRY_RE = re.compile(r"\{\s*id\s*:\s*(\d+)\s*,\s*pages\s*:\s*(\d+)\s*\}")


def read_shelf_volumes(html: str) -> list[tuple[int, int]]:
    matches = list(VOLUME_ARRAY_RE.finditer(html))
    if len(matches) != 1:
        raise RuntimeError("could not find exactly one `const volumes = [...]` list in shelf.html")
    body = matches[0].group(1)
    entries = [(int(match.group(1)), int(match.group(2))) for match in VOLUME_ENTRY_RE.finditer(body)]
    remainder = VOLUME_ENTRY_RE.sub("", body).strip(" \t\r\n,")
    if remainder or not entries:
        raise RuntimeError("the volumes list has an unexpected format; update it to `{ id: N, pages: N }` entries")
    expected_ids = list(range(1, len(entries) + 1))
    if [volume_id for volume_id, _ in entries] != expected_ids:
        raise RuntimeError("the shelf volumes must be numbered consecutively from Manga 1")
    return entries


def update_shelf_html(html: str, volumes: list[tuple[int, int]]) -> str:
    match = VOLUME_ARRAY_RE.search(html)
    if not match:
        raise RuntimeError("could not find the volumes list in shelf.html")
    rows = ",\n".join(f"      {{ id: {volume_id}, pages: {page_count} }}"
                       for volume_id, page_count in volumes)
    replacement = f"const volumes = [\n{rows}\n    ];"
    return html[:match.start()] + replacement + html[match.end():]


def build_preview(volumes: list[tuple[int, int]]) -> str:
    """Build a local, responsive shelf preview with a scrollable image reader."""
    volume_data = [{"id": volume_id, "pages": page_count} for volume_id, page_count in volumes]
    cards = "\n".join(
        f'''<li class="card"><button class="open" type="button" data-index="{index}">
<img src="m{volume_id}-cover.jpg" alt="Manga {volume_id} cover" loading="lazy">
<span class="info"><strong>Manga {volume_id}</strong><small>{page_count} pages</small></span>
</button></li>'''
        for index, (volume_id, page_count) in enumerate(volumes)
    )
    data = json.dumps(volume_data)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#11100f"><title>Manga Shelf Preview</title>
<style>
:root{{--bg:#11100f;--panel:#1b1917;--ink:#f4eee6;--muted:#aaa39b;--line:#38332e;--accent:#e9a86b;color-scheme:dark}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{width:min(1180px,calc(100% - 32px));margin:auto}}header{{padding:clamp(30px,8vw,70px) 0 24px;border-bottom:1px solid var(--line)}}
.eyebrow{{color:var(--accent);font-size:.75rem;letter-spacing:.16em;text-transform:uppercase;font-weight:700}}
h1{{font:500 clamp(2.5rem,8vw,4.5rem)/1.05 Georgia,serif;letter-spacing:-.04em;margin:8px 0}}
p{{color:var(--muted);margin:8px 0 0}}header a{{display:inline-block;margin-top:14px;color:var(--accent)}}
ol{{list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(165px,1fr));gap:18px;padding:0;margin:24px 0 60px}}
.card{{overflow:hidden;background:var(--panel);border:1px solid var(--line);border-radius:9px}}
.open{{width:100%;padding:0;border:0;background:none;color:inherit;text-align:left;cursor:pointer}}
.open img{{display:block;width:100%;aspect-ratio:.72;object-fit:cover;background:#26221e}}
.info{{display:block;padding:12px 14px 14px}}.info strong{{display:block;font:500 1.15rem Georgia,serif}}.info small{{color:var(--muted)}}
dialog{{width:100%;height:100%;max-width:none;max-height:none;margin:0;padding:0;border:0;background:#0b0b0b;color:var(--ink)}}
dialog::backdrop{{background:#000}}.bar{{position:sticky;top:0;z-index:2;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:10px max(12px,env(safe-area-inset-right)) 10px max(12px,env(safe-area-inset-left));background:#171615;border-bottom:1px solid #34312e}}
.bar strong{{font:500 1.1rem Georgia,serif}}.bar button{{min-height:42px;padding:8px 14px;border:1px solid #47413b;border-radius:7px;background:#24211e;color:inherit;font:inherit}}
.pages{{height:calc(100% - 62px);overflow:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch;text-align:center}}
.pages img{{display:block;width:min(100%,900px);height:auto;margin:0 auto;background:#191919}}
@media(max-width:600px){{ol{{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}.card{{border-radius:7px}}}}
</style></head><body><main><header><div class="eyebrow">Local preview</div><h1>Manga Shelf</h1>
<p>{len(volumes)} volumes · Select a cover to preview its pages.</p><a href="shelf.html">Open the website shelf</a></header><ol>{cards}</ol></main>
<dialog id="reader"><div class="bar"><strong id="title"></strong><button id="close" type="button">Close</button></div><div class="pages" id="pages"></div></dialog>
<script>
const volumes={data};const reader=document.querySelector('#reader');const pages=document.querySelector('#pages');
document.querySelectorAll('.open').forEach(button=>button.addEventListener('click',()=>{{
const volume=volumes[Number(button.dataset.index)];document.querySelector('#title').textContent=`Manga ${{volume.id}} · ${{volume.pages}} pages`;
pages.replaceChildren();for(let page=1;page<=volume.pages;page++){{const image=document.createElement('img');image.src=`m${{volume.id}}-${{String(page).padStart(3,'0')}}.jpg`;image.alt=`Manga ${{volume.id}}, page ${{page}}`;image.loading=page<3?'eager':'lazy';pages.append(image)}}reader.showModal();pages.scrollTop=0;
}}));document.querySelector('#close').addEventListener('click',()=>reader.close());reader.addEventListener('click',event=>{{if(event.target===reader)reader.close()}});
</script></body></html>'''


def write_preview(volumes: list[tuple[int, int]]) -> None:
    preview = build_preview(volumes)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=ROOT,
                                     delete=False, suffix=".html.tmp") as temporary:
        temporary.write(preview)
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, PREVIEW_PATH)


def archive_images(archive_path: Path) -> tuple[zipfile.ZipInfo, list[zipfile.ZipInfo]]:
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = [item for item in archive.infolist()
                       if not item.is_dir()
                       and Path(item.filename.replace("\\", "/")).suffix.casefold() in IMAGE_EXTENSIONS
                       and not is_hidden_or_metadata(item.filename)]
            members.sort(key=lambda item: natural_key(item.filename))
            if not members:
                raise RuntimeError("contains no supported image files")
    except zipfile.BadZipFile as exc:
        raise RuntimeError("is not a readable ZIP archive") from exc

    covers = [member for member in members if is_cover(member.filename)]
    if covers:
        cover = covers[0]
        pages = [member for member in members if not is_cover(member.filename)]
        if not pages:
            raise RuntimeError("contains a cover image but no page images")
    else:
        # If the ZIP has no clearly named cover, use its first sorted page as the shelf thumbnail.
        cover = members[0]
        pages = members
    return cover, pages


def main() -> int:
    INBOX.mkdir(exist_ok=True)
    PROCESSED.mkdir(exist_ok=True)
    archives = sorted(INBOX.glob("*.zip"), key=lambda path: natural_key(path.name))
    if not archives:
        try:
            html = (ROOT / "shelf.html").read_text(encoding="utf-8")
            write_preview(read_shelf_volumes(html))
        except (OSError, RuntimeError) as exc:
            print(f"Could not create the preview: {exc}", file=sys.stderr)
            return 1
        print(f"No ZIP files found. Refreshed the current shelf preview: {PREVIEW_PATH}")
        print(f"Drop manga ZIPs into: {INBOX}")
        return 0

    already_processed = [path.name for path in archives if (PROCESSED / path.name).exists()]
    if already_processed:
        print("Cannot process: same ZIP name already exists in manga-zips/processed:")
        for name in already_processed:
            print(f"  {name}")
        return 1

    shelf_path = ROOT / "shelf.html"
    try:
        original_shelf = shelf_path.read_text(encoding="utf-8")
        current_volumes = read_shelf_volumes(original_shelf)
    except (OSError, RuntimeError) as exc:
        print(f"Import stopped: {exc}", file=sys.stderr)
        return 1

    highest_image_number = existing_manga_number()
    highest_shelf_number = current_volumes[-1][0]
    if highest_image_number != highest_shelf_number:
        print(
            f"Import stopped: shelf lists Manga {highest_shelf_number}, but image files go through "
            f"Manga {highest_image_number}. Reconcile shelf.html and the existing images first.",
            file=sys.stderr,
        )
        return 1

    first_number = highest_shelf_number + 1
    planned: list[tuple[Path, int, zipfile.ZipInfo, list[zipfile.ZipInfo]]] = []
    try:
        for offset, archive_path in enumerate(archives):
            cover, pages = archive_images(archive_path)
            planned.append((archive_path, first_number + offset, cover, pages))
    except (RuntimeError, OSError) as exc:
        print(f"Import stopped: {archive_path.name} {exc}", file=sys.stderr)
        return 1

    destinations: list[Path] = []
    for _, manga_number, _, page_images in planned:
        destinations.append(ROOT / f"m{manga_number}-cover.jpg")
        destinations.extend(ROOT / f"m{manga_number}-{page_number:03}.jpg"
                            for page_number in range(1, len(page_images) + 1))
    conflicts = [path for path in destinations if path.exists()]
    if conflicts:
        print("Import stopped because these output files already exist:", file=sys.stderr)
        for path in conflicts:
            print(f"  {path.name}", file=sys.stderr)
        return 1

    staged_files: list[Path] = []
    updated_volumes = current_volumes + [
        (manga_number, len(page_images)) for _, manga_number, _, page_images in planned
    ]
    try:
        new_shelf = update_shelf_html(original_shelf, updated_volumes)
    except RuntimeError as exc:
        print(f"Import stopped: {exc}", file=sys.stderr)
        return 1

    committed_files: list[Path] = []
    moved_archives: list[Path] = []
    shelf_updated = False
    try:
        with tempfile.TemporaryDirectory(prefix="manga-import-", dir=ROOT) as temp_dir:
            staging = Path(temp_dir)
            for archive_path, manga_number, cover, page_images in planned:
                with zipfile.ZipFile(archive_path) as archive:
                    write_as_jpeg(archive.read(cover), cover.filename, staging / f"m{manga_number}-cover.jpg")
                    for page_number, page in enumerate(page_images, start=1):
                        write_as_jpeg(archive.read(page), page.filename, staging / f"m{manga_number}-{page_number:03}.jpg")
            staged_index = staging / "shelf.html.new"
            staged_index.write_text(new_shelf, encoding="utf-8", newline="")
            staged_files = sorted((path for path in staging.iterdir() if path != staged_index),
                                  key=lambda path: natural_key(path.name))
            for staged in staged_files:
                destination = ROOT / staged.name
                shutil.move(str(staged), str(destination))
                committed_files.append(destination)
            # Replace the list only after every image has been created successfully.
            os.replace(staged_index, shelf_path)
            shelf_updated = True
            for archive_path, _, _, _ in planned:
                shutil.move(str(archive_path), str(PROCESSED / archive_path.name))
                moved_archives.append(archive_path)
    except Exception as exc:
        for moved in moved_archives:
            try:
                shutil.move(str(PROCESSED / moved.name), str(INBOX / moved.name))
            except OSError:
                pass
        if shelf_updated:
            try:
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=ROOT,
                                                 delete=False, suffix=".html.tmp") as backup:
                    backup.write(original_shelf)
                    backup_path = Path(backup.name)
                os.replace(backup_path, shelf_path)
            except OSError:
                print("Warning: could not restore the original shelf list.", file=sys.stderr)
        for committed in committed_files:
            try:
                committed.unlink(missing_ok=True)
            except OSError:
                pass
        print(f"Import stopped while preparing images: {exc}", file=sys.stderr)
        return 1

    for archive_path, manga_number, _, page_images in planned:
        print(f"Manga {manga_number}: {len(page_images)} pages from {archive_path.name}")
    print(f"Created {len(destinations)} JPEG files in {ROOT}")
    print(f"Updated the shelf in {shelf_path} with {len(planned)} new volume(s).")
    try:
        write_preview(updated_volumes)
        print(f"Generated shelf preview: {PREVIEW_PATH}")
    except OSError as exc:
        print(f"Warning: the shelf was updated, but preview generation failed: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
