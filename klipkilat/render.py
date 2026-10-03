"""Memotong video, mengubahnya ke 9:16, dan menempelkan subtitle dengan FFmpeg."""
from __future__ import annotations

import logging
import os
import urllib.request
from pathlib import Path

from . import proses
from .kesalahan import KlipKilatError
from .model import Momen, Video

log = logging.getLogger("klipkilat")

URL_FONT = "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-ExtraBold.ttf"
FILE_FONT = "Montserrat-ExtraBold.ttf"
FONT_UTAMA = "Montserrat ExtraBold"
FONT_CADANGAN = "DejaVu Sans"
UKURAN_FONT_MIN = 10_000

LATAR = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
FILTER = {
    "blur": (
        f"[0:v]{LATAR},boxblur=20:2[bg];"
        "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,ass={ass}:fontsdir={font},format=yuv420p[v]"
    ),
    "crop": f"[0:v]{LATAR},ass={{ass}}:fontsdir={{font}},format=yuv420p[v]",
}


def _unduh(url: str, tujuan: Path) -> None:
    urllib.request.urlretrieve(url, tujuan)


def siapkan_font(folder_font: Path, unduh=_unduh) -> str:
    folder_font = Path(folder_font)
    folder_font.mkdir(parents=True, exist_ok=True)
    tujuan = folder_font / FILE_FONT
    if tujuan.exists() and tujuan.stat().st_size > UKURAN_FONT_MIN:
        return FONT_UTAMA
    try:
        unduh(URL_FONT, tujuan)
        if tujuan.stat().st_size > UKURAN_FONT_MIN:
            return FONT_UTAMA
    except Exception as e:
        log.warning("Gagal mengunduh font, memakai %s: %r", FONT_CADANGAN, e)
    tujuan.unlink(missing_ok=True)
    return FONT_CADANGAN


def render_klip(video: Video, momen: Momen, path_ass: Path, gaya: str, keluaran: Path,
                folder_font: Path) -> Path:
    if gaya not in FILTER:
        raise KlipKilatError(f"gaya_vertikal '{gaya}' tidak dikenal. Pilih 'blur' atau 'crop'.")
    path_ass, keluaran = Path(path_ass), Path(keluaran)
    keluaran.parent.mkdir(parents=True, exist_ok=True)
    font_relatif = Path(os.path.relpath(folder_font, path_ass.parent)).as_posix()
    filter_video = FILTER[gaya].format(ass=path_ass.name, font=font_relatif)
    proses.jalankan([
        "ffmpeg", "-y",
        "-ss", f"{momen.mulai:.3f}", "-i", str(Path(video.path_video).resolve()),
        "-t", f"{momen.durasi:.3f}",
        "-filter_complex", filter_video,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(keluaran.resolve()),
    ], cwd=path_ass.parent)
    return keluaran
