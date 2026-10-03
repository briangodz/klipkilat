"""Membuat KlipKilat.ipynb. Jalankan dari root repo: python scripts/buat_notebook.py"""
import json
from pathlib import Path

PENGANTAR = """# ⚡ KlipKilat
Ubah video panjang (live, podcast, YouTube) jadi **klip pendek vertikal + subtitle otomatis**. Gratis.

**Cara pakai:**
1. Jalankan sel **1️⃣ Persiapan** (klik ▶ di kiri sel).
2. Isi form di sel **2️⃣ Pengaturan**, lalu klik ▶ di sel itu.
3. Tunggu sampai muncul ✅. File `hasil.zip` akan terunduh otomatis.

**Kolom `sumber`:**
- Link YouTube, contoh `https://www.youtube.com/watch?v=...`
- File di Google Drive, contoh `/content/drive/MyDrive/podcast.mp4`
- **Kosongkan** untuk upload langsung dari komputer (cocok untuk file kecil)

**`gemini_api_key`** (opsional, gratis): buat di https://aistudio.google.com/apikey. Bisa juga disimpan di menu 🔑 *Secrets* Colab dengan nama `GEMINI_API_KEY`.
Tanpa key, isi **`timestamp_manual`**, contoh `01:23:10-01:24:00, 02:05:00-02:05:45`.

⚠️ Hanya clip konten yang boleh kamu clip: program clipping resmi, izin kreator, atau konten milikmu sendiri.
"""

PERSIAPAN = r'''#@title 1️⃣ Persiapan — klik ▶ lalu tunggu ±2 menit
import shutil
import subprocess

if shutil.which("nvidia-smi") and subprocess.run(["nvidia-smi"], capture_output=True).returncode == 0:
    print("✅ GPU aktif")
else:
    print("⚠️ GPU belum aktif. Klik menu Runtime → Change runtime type → pilih T4 GPU → Save,")
    print("   lalu jalankan ulang sel ini. (Tanpa GPU tetap bisa, tapi jauh lebih lambat.)")
!pip install -q -U yt-dlp
!pip install -q "klipkilat @ git+https://github.com/briangodz/klipkilat"
print("✅ Persiapan selesai. Lanjut ke sel 2️⃣.")
'''

PENGATURAN = r'''#@title 2️⃣ Pengaturan — isi form, lalu klik ▶
sumber = ""  #@param {type:"string"}
jumlah_klip = 5  #@param {type:"slider", min:1, max:15, step:1}
durasi_min = 30  #@param {type:"integer"}
durasi_maks = 60  #@param {type:"integer"}
bahasa = "id"  #@param ["id", "en", "auto"]
gaya_vertikal = "blur"  #@param ["blur", "crop"]
gemini_api_key = ""  #@param {type:"string"}
timestamp_manual = ""  #@param {type:"string"}
simpan_ke_drive = False  #@param {type:"boolean"}

import shutil
from datetime import datetime
from pathlib import Path

from google.colab import files
from klipkilat.kesalahan import KlipKilatError
from klipkilat.pipeline import Pengaturan, jalankan

FOLDER_KERJA = Path("/content/klipkilat_kerja")
sumber = sumber.strip()

if sumber.startswith("/content/drive") or simpan_ke_drive:
    from google.colab import drive
    drive.mount("/content/drive")

if not gemini_api_key.strip():
    try:
        from google.colab import userdata
        gemini_api_key = userdata.get("GEMINI_API_KEY") or ""
    except Exception:
        pass

if not sumber:
    print("📤 Pilih file video yang mau diupload...")
    unggahan = files.upload()
    sumber = str(Path.cwd() / next(iter(unggahan))) if unggahan else ""

if not sumber:
    print("❌ Tidak ada video. Isi kolom sumber atau upload file.")
else:
    try:
        hasil = jalankan(Pengaturan(
            sumber=sumber,
            folder_kerja=FOLDER_KERJA,
            jumlah_klip=jumlah_klip,
            durasi_min=durasi_min,
            durasi_maks=durasi_maks,
            bahasa=bahasa,
            gaya_vertikal=gaya_vertikal,
            gemini_api_key=gemini_api_key,
            timestamp_manual=timestamp_manual,
        ))
    except KlipKilatError as e:
        print(f"\n❌ {e.pesan_pengguna}")
        print(f"   Detail teknis tersimpan di {FOLDER_KERJA / 'log.txt'}")
    else:
        print("\n📋 Momen yang dibuat:")
        for i, m in enumerate(hasil.momen, 1):
            print(f"  {i}. {m.judul} ({m.durasi:.0f} detik)")
        if hasil.klip_gagal:
            print("\n⚠️ Klip yang gagal:")
            for g in hasil.klip_gagal:
                print("  -", g)
        if simpan_ke_drive:
            tujuan = Path("/content/drive/MyDrive/KlipKilat")
            tujuan.mkdir(parents=True, exist_ok=True)
            nama = f"hasil_{datetime.now():%Y%m%d_%H%M%S}.zip"
            shutil.copy(hasil.path_zip, tujuan / nama)
            print(f"💾 Disalin ke Google Drive: MyDrive/KlipKilat/{nama}")
        files.download(str(hasil.path_zip))
'''

MASALAH = """## 🛠️ Kalau ada masalah
- **GPU belum aktif** → Runtime → Change runtime type → T4 GPU → Save, lalu jalankan ulang dari sel 1.
- **Gagal mengunduh dari YouTube** → unduh videonya sendiri, lalu upload (kosongkan `sumber`) atau taruh di Google Drive.
- **Kuota Gemini habis / key tidak valid** → isi `timestamp_manual`, lalu jalankan ulang sel 2. Transkrip tidak dibuat ulang selama runtime belum dihapus.
- **Sesi terputus** → jalankan ulang sel 1 dan sel 2.
- **Bug lain** → laporkan di https://github.com/briangodz/klipkilat/issues dan lampirkan `log.txt` (ada di dalam `hasil.zip` atau di `/content/klipkilat_kerja/log.txt`).
"""


def _sel(jenis: str, teks: str) -> dict:
    sel = {"cell_type": jenis, "metadata": {}, "source": teks.strip("\n").splitlines(keepends=True)}
    if jenis == "code":
        sel["metadata"] = {"cellView": "form"}
        sel["execution_count"] = None
        sel["outputs"] = []
    return sel


def main() -> None:
    nb = {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"provenance": [], "gpuType": "T4"},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python"},
        },
        "cells": [
            _sel("markdown", PENGANTAR),
            _sel("code", PERSIAPAN),
            _sel("code", PENGATURAN),
            _sel("markdown", MASALAH),
        ],
    }
    tujuan = Path(__file__).resolve().parents[1] / "KlipKilat.ipynb"
    tujuan.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Ditulis: {tujuan}")


if __name__ == "__main__":
    main()
