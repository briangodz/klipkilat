"""Mengambil video (YouTube atau file lokal/Drive) dan mengekstrak audionya."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from . import proses
from .kesalahan import KlipKilatError
from .model import Video

log = logging.getLogger("klipkilat")

FORMAT_YT = "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b"


def _unduh_youtube(url: str, folder: Path) -> tuple[Path, str]:
    import yt_dlp

    for lama in folder.glob("video_sumber.*"):
        lama.unlink()
    opsi = {
        "format": FORMAT_YT,
        "merge_output_format": "mp4",
        "outtmpl": str(folder / "video_sumber.%(ext)s"),
        "quiet": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(opsi) as ydl:
        info = ydl.extract_info(url, download=True)
    hasil = [p for p in folder.glob("video_sumber.*") if p.suffix not in (".part", ".ytdl")]
    if not hasil:
        raise RuntimeError("yt-dlp selesai tetapi file video tidak ditemukan")
    return hasil[0], info.get("title") or "video"


def _adalah_url(teks: str) -> bool:
    return teks.lower().startswith(("http://", "https://"))


def _unduh_dengan_ulang(url: str, folder: Path, pengunduh, jeda: float) -> tuple[Path, str]:
    terakhir = None
    for percobaan in range(1, 3):
        try:
            return pengunduh(url, folder)
        except Exception as e:  # yt-dlp melempar banyak jenis error
            terakhir = e
            log.warning("Unduh gagal (percobaan %d): %r", percobaan, e)
            if percobaan == 1:
                time.sleep(jeda)
    raise KlipKilatError(
        "Gagal mengunduh video dari YouTube. Kemungkinan videonya privat, dibatasi umur, "
        "atau YouTube sedang memblokir server Colab.\n"
        "Solusi: unduh videonya sendiri, lalu upload (kosongkan kolom sumber) atau taruh di Google Drive.",
        repr(terakhir),
    ) from terakhir


def ambil_video(sumber: str, folder_kerja: Path, pengunduh=_unduh_youtube, jeda: float = 3.0) -> Video:
    folder_kerja = Path(folder_kerja)
    folder_kerja.mkdir(parents=True, exist_ok=True)
    sumber = sumber.strip()
    if _adalah_url(sumber):
        path, judul = _unduh_dengan_ulang(sumber, folder_kerja, pengunduh, jeda)
    else:
        path = Path(sumber)
        if not path.is_file():
            raise KlipKilatError(
                f"File video tidak ditemukan: {sumber}\n"
                "Pastikan path-nya benar, contoh: /content/drive/MyDrive/video.mp4"
            )
        judul = path.stem
    durasi = proses.durasi(path)
    if not proses.punya_audio(path):
        raise KlipKilatError("Video ini tidak punya suara, jadi tidak bisa dibuat transkrip dan subtitle.")
    audio = folder_kerja / "audio.wav"
    proses.jalankan(["ffmpeg", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", str(audio)])
    log.info("Video siap: %s (%.1f detik)", judul, durasi)
    return Video(path, audio, durasi, judul)
