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


PESAN_LIVE = (
    "Live stream ini masih berlangsung atau belum selesai diproses YouTube. Tunggu sampai rekamannya "
    "tersedia (biasanya beberapa jam setelah live selesai), lalu coba lagi."
)


def _file_selesai(folder: Path, id_video: str) -> Path | None:
    """File video_sumber_<id>.<ext> yang sudah utuh (bukan .part/.ytdl atau potongan format .f137.mp4)."""
    nama = f"video_sumber_{id_video}"
    hasil = sorted(p for p in folder.glob(f"{nama}.*")
                   if p.stem == nama and p.suffix not in (".part", ".ytdl") and p.is_file())
    return hasil[0] if hasil else None


def _unduh_youtube(url: str, folder: Path) -> tuple[Path, str]:
    import yt_dlp

    opsi = {
        "format": FORMAT_YT,
        "merge_output_format": "mp4",
        "outtmpl": str(folder / "video_sumber_%(id)s.%(ext)s"),
        "quiet": True,
        "noprogress": True,
    }
    with yt_dlp.YoutubeDL(opsi) as ydl:
        info = ydl.extract_info(url, download=False)
        if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming", "post_live"):
            raise KlipKilatError(PESAN_LIVE, f"live_status={info.get('live_status')!r}")
        judul = info.get("title") or "video"
        id_video = info.get("id") or "video"
        ada = _file_selesai(folder, id_video)
        if ada:
            log.info("Memakai video yang sudah diunduh: %s", ada.name)
            return ada, judul
        info = ydl.process_ie_result(info, download=True)
    unduhan = info.get("requested_downloads") or []
    path = Path(unduhan[0]["filepath"]) if unduhan and unduhan[0].get("filepath") else None
    if path is None or not path.is_file():
        path = _file_selesai(folder, id_video)
    if path is None:
        raise RuntimeError("yt-dlp selesai tetapi file video tidak ditemukan")
    return path, judul


def _adalah_url(teks: str) -> bool:
    return teks.lower().startswith(("http://", "https://"))


def _unduh_dengan_ulang(url: str, folder: Path, pengunduh, jeda: float) -> tuple[Path, str]:
    terakhir = None
    for percobaan in range(1, 3):
        try:
            return pengunduh(url, folder)
        except KlipKilatError:
            raise
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
    sumber = sumber.strip().strip("\"'")
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
