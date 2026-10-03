"""Menyusun daftar momen (momen.md) dan mengemas hasil menjadi zip."""
from __future__ import annotations

import zipfile
from pathlib import Path

from .model import Momen, format_jam


def tulis_momen_md(momen_list: list[Momen], judul_video: str, path: Path,
                   gagal: set[int] = frozenset()) -> None:
    baris = [f"# Momen dari: {judul_video}", ""]
    for i, m in enumerate(momen_list, 1):
        berkas = "(gagal dibuat — lihat log.txt)" if i in gagal else f"klip_{i:02d}.mp4"
        baris += [
            f"## {i}. {m.judul}",
            f"- File: {berkas}",
            f"- Waktu di video asli: {format_jam(m.mulai)} – {format_jam(m.selesai)} ({m.durasi:.0f} detik)",
            f"- Alasan: {m.alasan}",
            "",
        ]
    Path(path).write_text("\n".join(baris), encoding="utf-8")


def buat_zip(folder_hasil: Path, path_zip: Path) -> Path:
    folder_hasil, path_zip = Path(folder_hasil), Path(path_zip)
    with zipfile.ZipFile(path_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder_hasil.rglob("*")):
            if f.is_file():
                # mp4 sudah terkompresi; DEFLATE hanya memperlambat tanpa memperkecil.
                jenis = zipfile.ZIP_STORED if f.suffix.lower() == ".mp4" else zipfile.ZIP_DEFLATED
                z.write(f, f.relative_to(folder_hasil).as_posix(), compress_type=jenis)
    return path_zip
