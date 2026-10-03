"""Menjalankan seluruh alur KlipKilat: video → transkrip → momen → klip → zip."""
from __future__ import annotations

import logging
import shutil
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import momen as modul_momen
from . import paket, proses, render, subtitle, sumber
from . import transkrip as modul_transkrip
from .kesalahan import GagalAI, KlipKilatError
from .model import Momen, Transkrip

log = logging.getLogger("klipkilat")

BATAS_PERINGATAN_DURASI = 4 * 3600
PESAN_TAK_TERDUGA = (
    "Terjadi kesalahan yang tidak terduga. Laporkan di https://github.com/briangodz/klipkilat/issues "
    "dan lampirkan file log.txt."
)


@dataclass
class Pengaturan:
    sumber: str
    folder_kerja: Path = Path("klipkilat_kerja")
    jumlah_klip: int = 5
    durasi_min: float = 30.0
    durasi_maks: float = 60.0
    bahasa: str = "id"
    gaya_vertikal: str = "blur"
    gemini_api_key: str = ""
    timestamp_manual: str = ""
    model_whisper: str | None = None


@dataclass
class Hasil:
    path_zip: Path
    klip_berhasil: list[Path]
    klip_gagal: list[str]
    peringatan: list[str]
    momen: list[Momen] = field(default_factory=list)


def _validasi(p: Pengaturan) -> None:
    if not p.sumber.strip():
        raise KlipKilatError("Kolom sumber masih kosong. Isi link YouTube atau path file video.")
    if not 1 <= p.jumlah_klip <= 15:
        raise KlipKilatError("jumlah_klip harus antara 1 dan 15.")
    if p.durasi_min <= 0 or p.durasi_min >= p.durasi_maks:
        raise KlipKilatError("durasi_min harus lebih dari 0 dan lebih kecil dari durasi_maks.")
    if p.bahasa not in ("id", "en", "auto"):
        raise KlipKilatError("bahasa harus 'id', 'en', atau 'auto'.")
    if p.gaya_vertikal not in ("blur", "crop"):
        raise KlipKilatError("gaya_vertikal harus 'blur' atau 'crop'.")
    if not p.gemini_api_key.strip() and not p.timestamp_manual.strip():
        raise KlipKilatError("Isi gemini_api_key untuk memilih momen otomatis, atau isi timestamp_manual. "
                             f"Contoh: {modul_momen.CONTOH_MANUAL}")


def jalankan(p: Pengaturan, tampil: Callable[[str], None] = print) -> Hasil:
    folder_kerja = Path(p.folder_kerja)
    folder_kerja.mkdir(parents=True, exist_ok=True)
    folder_hasil = folder_kerja / "hasil"
    shutil.rmtree(folder_hasil, ignore_errors=True)
    folder_hasil.mkdir()

    handler = logging.FileHandler(folder_kerja / "log.txt", mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        return _proses(p, folder_kerja, folder_hasil, tampil, handler)
    except KlipKilatError as e:
        log.error("%s | %s", e.pesan_pengguna, e.detail_teknis)
        raise
    except Exception as e:
        log.error("Kesalahan tidak terduga:\n%s", traceback.format_exc())
        raise KlipKilatError(PESAN_TAK_TERDUGA, repr(e)) from e
    finally:
        log.removeHandler(handler)
        handler.close()


def _proses(p: Pengaturan, folder_kerja: Path, folder_hasil: Path,
            tampil: Callable[[str], None], handler: logging.Handler) -> Hasil:
    peringatan: list[str] = []

    def ingatkan(pesan: str) -> None:
        peringatan.append(pesan)
        log.warning(pesan)
        tampil(f"⚠️ {pesan}")

    _validasi(p)
    proses.cek_ffmpeg()

    tampil("📥 Mengambil video...")
    video = sumber.ambil_video(p.sumber, folder_kerja)
    if video.durasi > BATAS_PERINGATAN_DURASI:
        ingatkan("Video lebih dari 4 jam. Sesi Colab gratis bisa terputus sebelum selesai.")

    perangkat = modul_transkrip.deteksi_perangkat()
    if perangkat == "cpu":
        ingatkan("GPU tidak aktif, transkrip akan lambat dan kurang akurat. "
                 "Aktifkan GPU: Runtime → Change runtime type → T4 GPU.")
    tampil("📝 Membuat transkrip (langkah paling lama)...")
    try:
        tr = modul_transkrip.buat_transkrip(video, p.bahasa, perangkat, folder_kerja, nama_model=p.model_whisper)
    except KlipKilatError as e:
        if perangkat != "cuda" or e.pesan_pengguna == modul_transkrip.PESAN_SEDIKIT_UCAPAN:
            raise
        log.error("Transkrip di GPU gagal: %s", e.detail_teknis)
        ingatkan("Transkrip di GPU gagal, mencoba ulang di CPU (lebih lambat).")
        tr = modul_transkrip.buat_transkrip(video, p.bahasa, "cpu", folder_kerja, nama_model=p.model_whisper)

    tampil("🔎 Menentukan momen...")
    daftar = _tentukan_momen(p, tr, video.judul, ingatkan)

    nama_font = render.siapkan_font(folder_kerja / "font")
    berhasil: list[Path] = []
    gagal: list[str] = []
    nomor_gagal: set[int] = set()
    for i, m in enumerate(daftar, 1):
        tampil(f"🎬 Membuat klip {i}/{len(daftar)}: {m.judul}")
        nama = f"klip_{i:02d}"
        path_srt = folder_hasil / f"{nama}.srt"
        try:
            path_ass = folder_kerja / f"{nama}.ass"
            path_ass.write_text(subtitle.buat_ass(tr, m, nama_font), encoding="utf-8")
            path_srt.write_text(subtitle.buat_srt(tr, m), encoding="utf-8")
            berhasil.append(render.render_klip(video, m, path_ass, p.gaya_vertikal,
                                               folder_hasil / f"{nama}.mp4", folder_kerja / "font"))
        except Exception as e:
            pesan = e.pesan_pengguna if isinstance(e, KlipKilatError) else "kesalahan tidak terduga"
            log.error("Klip %d gagal: %s\n%s", i, pesan,
                      getattr(e, "detail_teknis", "") or traceback.format_exc())
            gagal.append(f"Klip {i} ({m.judul}): {pesan}")
            nomor_gagal.add(i)
            path_srt.unlink(missing_ok=True)

    if not berhasil:
        raise KlipKilatError("Semua klip gagal dibuat. Lihat log.txt untuk detailnya.")

    paket.tulis_momen_md(daftar, video.judul, folder_hasil / "momen.md", gagal=nomor_gagal)
    modul_transkrip.simpan(tr, folder_hasil / "transkrip.json")
    handler.flush()
    shutil.copy(folder_kerja / "log.txt", folder_hasil / "log.txt")
    path_zip = paket.buat_zip(folder_hasil, folder_kerja / "hasil.zip")
    tampil(f"✅ Selesai: {len(berhasil)} klip berhasil" + (f", {len(gagal)} gagal" if gagal else ""))
    return Hasil(path_zip, berhasil, gagal, peringatan, daftar)


def _tentukan_momen(p: Pengaturan, tr: Transkrip, judul: str,
                    ingatkan: Callable[[str], None]) -> list[Momen]:
    contoh = f"Contoh: {modul_momen.CONTOH_MANUAL}"
    if p.timestamp_manual.strip():
        return modul_momen.dari_teks_manual(p.timestamp_manual, tr)
    if p.gemini_api_key.strip():
        try:
            klien = modul_momen.buat_klien_gemini(p.gemini_api_key.strip())
            return modul_momen.pilih_dengan_ai(tr, p.jumlah_klip, p.durasi_min, p.durasi_maks,
                                               klien, judul_video=judul)
        except GagalAI as e:
            log.error("Gemini gagal (%s): %s", e.jenis, e.detail_teknis)
            ingatkan(f"{e.pesan_pengguna} Beralih ke mode timestamp manual.")
        raise KlipKilatError(
            "Momen tidak bisa dipilih otomatis. Isi kolom timestamp_manual lalu jalankan ulang "
            f"(transkrip tidak akan dibuat ulang). {contoh}"
        )
    raise KlipKilatError(f"Isi gemini_api_key untuk memilih momen otomatis, atau isi timestamp_manual. {contoh}")
