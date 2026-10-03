"""Menjalankan FFmpeg/ffprobe dan mengubah kegagalannya menjadi KlipKilatError."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .kesalahan import KlipKilatError


def cek_ffmpeg() -> None:
    for nama in ("ffmpeg", "ffprobe"):
        if shutil.which(nama) is None:
            raise KlipKilatError(
                f"Program '{nama}' tidak ditemukan. Di Colab seharusnya sudah tersedia — "
                "coba Runtime → Disconnect and delete runtime, lalu jalankan ulang dari sel 1.",
                f"{nama} tidak ada di PATH",
            )


def jalankan(args: list[str], cwd: Path | None = None) -> str:
    try:
        hasil = subprocess.run(
            [str(a) for a in args], cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError as e:
        raise KlipKilatError(f"Program '{args[0]}' tidak ditemukan.", repr(e)) from e
    if hasil.returncode != 0:
        perintah = " ".join(str(a) for a in args)
        raise KlipKilatError(f"Perintah {args[0]} gagal.", f"{perintah}\n{hasil.stderr[-3000:]}")
    return hasil.stdout


def durasi(path: Path) -> float:
    try:
        keluaran = jalankan(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
        return float(keluaran.strip())
    except (KlipKilatError, ValueError) as e:
        raise KlipKilatError(
            "Tidak bisa membaca durasi video. File mungkin rusak atau bukan video.",
            getattr(e, "detail_teknis", repr(e)),
        ) from e


def punya_audio(path: Path) -> bool:
    keluaran = jalankan(["ffprobe", "-v", "error", "-select_streams", "a",
                         "-show_entries", "stream=index", "-of", "csv=p=0", str(path)])
    return keluaran.strip() != ""


def ukuran_video(path: Path) -> tuple[int, int]:
    keluaran = jalankan(["ffprobe", "-v", "error", "-select_streams", "v:0",
                         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)])
    lebar, tinggi = keluaran.strip().split("x")
    return int(lebar), int(tinggi)
