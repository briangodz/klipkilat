# ⚡ KlipKilat

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/briangodz/klipkilat/blob/main/KlipKilat.ipynb)
[![tes](https://github.com/briangodz/klipkilat/actions/workflows/tes.yml/badge.svg)](https://github.com/briangodz/klipkilat/actions/workflows/tes.yml)

**Tool gratis untuk clipper Indonesia.** Masukkan video panjang (live stream, podcast, YouTube), dan keluarlah klip pendek vertikal **siap upload ke TikTok, Reels, dan Shorts**:

- 🔎 **Momen seru dipilih AI.** Gemini membaca seluruh transkrip lalu menyarankan bagian yang paling berpotensi viral.
- 💬 **Subtitle otomatis gaya TikTok.** Bahasa Indonesia, kata yang sedang diucapkan di-highlight, langsung tertanam di video.
- 📱 **Format 9:16.** Video asli di tengah dengan latar blur, atau dipotong di tengah.
- 💸 **Gratis.** Berjalan di GPU gratis Google Colab, tanpa instalasi.

## Cara pakai

1. Klik tombol **Open in Colab** di atas.
2. Jalankan sel **1️⃣ Persiapan**.
3. Isi form di sel **2️⃣ Pengaturan**, lalu jalankan.
4. Unduh `hasil.zip`.

| Kolom | Isi |
|---|---|
| `sumber` | Link YouTube, path Google Drive (`/content/drive/MyDrive/video.mp4`), atau kosongkan untuk upload |
| `jumlah_klip` | 1–15 (default 5) |
| `durasi_min` / `durasi_maks` | Durasi tiap klip dalam detik (default 30–60) |
| `bahasa` | `id`, `en`, atau `auto` |
| `gaya_vertikal` | `blur` (video utuh + latar blur) atau `crop` (potong tengah) |
| `gemini_api_key` | Opsional, gratis di [Google AI Studio](https://aistudio.google.com/apikey) |
| `timestamp_manual` | Kalau tidak pakai AI, contoh `01:23:10-01:24:00, 02:05:00-02:05:45` |
| `simpan_ke_drive` | Salin hasil ke `MyDrive/KlipKilat` |

**Isi `hasil.zip`:** `klip_01.mp4` dan seterusnya (1080×1920, subtitle tertanam), `klip_01.srt` dan seterusnya (bisa diedit di CapCut), `momen.md` (judul, waktu, alasan), `transkrip.json`, dan `log.txt`.

> 🔒 Jangan bagikan notebook yang kolom `gemini_api_key`-nya masih terisi. Lebih aman simpan key di menu 🔑 *Secrets* Colab dengan nama `GEMINI_API_KEY`.

## Kalau ada masalah

- **GPU belum aktif**: Runtime → Change runtime type → T4 GPU.
- **YouTube gagal diunduh**: upload videonya sendiri atau taruh di Google Drive.
- **Kuota Gemini habis**: isi `timestamp_manual`. Transkrip tidak dibuat ulang.
- **Bug lain**: buka [Issue](https://github.com/briangodz/klipkilat/issues) dan lampirkan `log.txt`.

## ⚠️ Etika

Hanya clip konten yang memang boleh di-clip: program clipping resmi, izin dari kreator, atau konten milikmu sendiri. Kamu bertanggung jawab atas konten yang kamu unggah.

## Untuk developer

```
klipkilat/
├── sumber.py      ambil video + ekstrak audio
├── transkrip.py   faster-whisper, cache transkrip
├── momen.py       Gemini / timestamp manual + perapian ke batas kalimat
├── subtitle.py    .ass gaya TikTok dan .srt
├── render.py      FFmpeg: potong, 9:16, tempel subtitle
├── paket.py       momen.md + zip
└── pipeline.py    menyatukan semuanya
```

Menjalankan tes (butuh Python 3.10+ dan FFmpeg):

```bash
pip install -e ".[dev]"
pytest
```

Notebook dibuat dari `scripts/buat_notebook.py`. Edit script itu, bukan file `.ipynb`-nya.

## Lisensi

MIT
