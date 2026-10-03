# KlipKilat — Desain

**Tanggal:** 2026-10-03
**Status:** Disetujui per bagian, menunggu review dokumen

## 1. Ringkasan

KlipKilat adalah tool gratis dan open-source untuk clipper Indonesia. Tool ini mengubah video panjang (live stream, podcast, video YouTube) menjadi klip pendek vertikal yang siap diunggah ke TikTok, Reels, atau Shorts. Ada dua pekerjaan berat yang diotomatiskan:

1. **Mencari momen seru.** AI membaca transkrip lalu menyarankan bagian yang paling menarik.
2. **Subtitle otomatis.** Subtitle bahasa Indonesia gaya TikTok, dengan kata yang sedang diucapkan di-highlight, langsung tertanam di video.

Tool dijalankan sebagai **notebook Google Colab**. Pengguna tidak perlu menginstal apa pun, dan proses berjalan di GPU gratis milik Google.

**Tujuan proyek:** produk yang benar-benar dipakai clipper, sekaligus menjadi portofolio GitHub.

## 2. Pengguna & cara pakai

**Pengguna:** clipper Indonesia, umumnya bukan programmer.

**Alur:**
1. Pengguna membuka tombol "Open in Colab" di README GitHub.
2. Pengguna mengisi form Colab (kolom `#@param`) tanpa menyentuh kode.
3. Pengguna klik **Runtime → Run all**.
4. Pengguna mengunduh `hasil.zip`. Kalau Google Drive terhubung, salinannya juga disimpan ke Drive.

**Isian form:**

| Kolom | Default | Keterangan |
|---|---|---|
| `sumber` | kosong | Link YouTube, **atau** path file di Google Drive. Kalau kosong, muncul tombol upload langsung (cocok untuk file kecil). |
| `jumlah_klip` | 5 | 1–15 |
| `durasi_min` / `durasi_maks` | 30 / 60 detik | Batas durasi tiap klip |
| `bahasa` | `id` | `id`, `en`, atau `auto` |
| `gaya_vertikal` | `blur` | `blur` (video utuh di tengah, latar blur) atau `crop` (potong tengah) |
| `gemini_api_key` | kosong | Opsional. Kalau kosong, pengguna memakai mode timestamp manual. |
| `timestamp_manual` | kosong | Contoh: `01:23:10-01:24:00, 02:05:00-02:05:45`. Dipakai kalau tidak ada API key, atau kalau diisi (mengalahkan pilihan AI). |

**Isi `hasil.zip`:**
- `klip_01.mp4`, `klip_02.mp4`, … : 1080×1920, H.264 + AAC, subtitle sudah tertanam
- `klip_01.srt`, … : subtitle terpisah untuk diedit di CapCut atau aplikasi lain
- `momen.md` : daftar momen (judul, timestamp di video asli, alasan dipilih)
- `transkrip.json` : transkrip lengkap
- `log.txt` : log teknis untuk melacak bug

**Di luar cakupan versi 1:** pelacakan wajah otomatis, upload otomatis ke media sosial, website terpisah, bahasa selain Indonesia/Inggris, editor subtitle di dalam tool.

## 3. Arsitektur

Notebook hanya berisi form dan satu panggilan ke `pipeline.jalankan()`. Semua logika ada di paket Python `klipkilat/`, yang diinstal di Colab lewat `pip install git+https://github.com/<user>/klipkilat`.

```
klipkilat/
├── KlipKilat.ipynb
├── klipkilat/
│   ├── __init__.py
│   ├── pipeline.py      orkestrasi seluruh alur + dataclass Pengaturan
│   ├── model.py         dataclass data bersama (Kata, Segmen, Transkrip, Momen, Video)
│   ├── kesalahan.py     KlipKilatError + pesan error berbahasa Indonesia
│   ├── sumber.py        ambil video (YouTube / Drive / upload), ekstrak audio
│   ├── transkrip.py     Whisper → kata + timestamp, cache ke JSON
│   ├── momen.py         pilih momen (Gemini atau manual), validasi, rapikan
│   ├── subtitle.py      buat .ass (gaya TikTok) dan .srt per klip
│   ├── render.py        FFmpeg: potong, vertikal, tempel subtitle
│   └── paket.py         susun folder hasil + zip
├── tests/
├── .github/workflows/tes.yml
├── pyproject.toml
├── LICENSE              MIT
└── README.md            bahasa Indonesia, tombol Open in Colab
```

### 3.1 Struktur data (`klipkilat/model.py`, dataclass)

- `Kata(teks: str, mulai: float, selesai: float)`, dalam satuan detik
- `Segmen(teks: str, mulai: float, selesai: float, kata: list[Kata])`, yaitu satu kalimat atau ujaran dari Whisper
- `Transkrip(bahasa: str, durasi: float, segmen: list[Segmen])`
- `Momen(judul: str, mulai: float, selesai: float, alasan: str)`
- `Video(path_video: Path, path_audio: Path, durasi: float, judul: str)`

### 3.2 Antarmuka modul

| Fungsi | Masukan → Keluaran |
|---|---|
| `sumber.ambil_video(sumber, folder_kerja)` | URL/path → `Video`. Audio diekstrak ke WAV 16 kHz mono. |
| `transkrip.buat_transkrip(video, bahasa, perangkat)` | → `Transkrip`. Disimpan ke `transkrip.json`, dengan nama berdasarkan hash file audio. Kalau file itu sudah ada, langsung dibaca tanpa transkrip ulang. |
| `momen.pilih_dengan_ai(transkrip, jumlah, dmin, dmaks, api_key)` | → `list[Momen]` (sudah divalidasi dan dirapikan) |
| `momen.dari_teks_manual(teks, transkrip)` | → `list[Momen]` |
| `momen.rapikan(momen_list, transkrip, dmin, dmaks)` | Validasi + geser titik potong ke batas segmen + buang yang bertumpuk |
| `subtitle.buat_ass(transkrip, momen, lebar, tinggi)` | → teks file `.ass`, timestamp relatif terhadap awal klip |
| `subtitle.buat_srt(transkrip, momen)` | → teks file `.srt` |
| `render.render_klip(video, momen, path_ass, gaya, keluaran)` | → path `.mp4` |
| `paket.buat_zip(folder_hasil)` | → path `hasil.zip` |
| `pipeline.jalankan(pengaturan)` | Menjalankan semuanya dan mengembalikan `Hasil(zip, klip_berhasil, klip_gagal, peringatan)` |

### 3.3 Detail tiap bagian

**Sumber**
- YouTube: yt-dlp dengan format terbaik ≤1080p, digabung ke mp4. Gagal → coba ulang satu kali → `KlipKilatError` dengan saran memakai upload atau Drive.
- Durasi > 4 jam memunculkan peringatan, tidak menghentikan proses.

**Transkrip**
- faster-whisper dengan `word_timestamps=True` dan `vad_filter=True`.
- Ada GPU → model `large-v3` dengan `float16`. Tidak ada GPU → model `small` dengan `int8`, disertai peringatan bahwa proses lebih lambat dan akurasi lebih rendah.
- Total kata < 20 → error "video tidak berisi ucapan yang bisa ditranskrip".

**Momen (AI)**
- Transkrip dikirim ke Gemini sebagai baris `[jj:mm:dd] teks` per segmen, dalam mode output JSON. Formatnya: daftar `{judul, mulai_detik, selesai_detik, alasan}`.
- Prompt meminta momen yang berdiri sendiri, punya "hook" di awal, dan berdurasi antara `dmin` dan `dmaks`. Judul dan alasan ditulis dalam bahasa video.
- SDK yang dipakai: `google-genai`. Nama model disimpan sebagai konstanta `MODEL_GEMINI`, yaitu model Flash terbaru yang tersedia di kuota gratis saat implementasi.
- Error key tidak valid atau kuota habis → peringatan spesifik, lalu pindah ke mode manual. Kalau `timestamp_manual` kosong, proses berhenti dengan pesan yang menjelaskan cara mengisinya.
- JSON tidak valid → diminta ulang maksimal 2 kali.

**Merapikan momen** (berlaku untuk hasil AI maupun manual)
1. Buang momen yang di luar durasi video atau yang `mulai >= selesai`.
2. Geser `mulai` ke awal segmen yang memuatnya, dan `selesai` ke akhir segmen yang memuatnya.
3. Kalau durasi > `dmaks`, potong di batas segmen terakhir yang masih ≤ `dmaks`. Kalau satu segmen saja sudah > `dmaks`, potong di batas kata.
4. Kalau durasi < `dmin`, perpanjang dengan segmen berikutnya selama masih ≤ `dmaks`.
5. Kalau ada momen yang bertumpuk, pertahankan yang urutannya lebih awal di daftar AI (prioritas lebih tinggi).
6. Tambahkan jeda 0,3 detik di awal dan akhir, dibatasi oleh durasi video.
7. Untuk input manual, aturan dmin/dmaks **tidak** dipaksakan. Hanya langkah 1, 2, dan 6 yang diterapkan.

**Subtitle**
- Format ASS dengan resolusi 1080×1920. Kata dikelompokkan maksimal 3 kata per tampilan dan tidak melewati batas segmen.
- Kata yang sedang diucapkan diberi warna kuning dan kata lain putih, dengan outline hitam tebal. Posisinya di tengah horizontal, kira-kira 70% dari atas layar.
- Font: Montserrat ExtraBold, diunduh dari Google Fonts saat setup. Kalau unduhan gagal, dipakai DejaVu Sans Bold.

**Render**
- FFmpeg dengan `-ss`/`-to` untuk memotong.
- `blur`: latar diskalakan sampai menutupi 1080×1920 lalu diberi `boxblur`, kemudian video utama diskalakan ke lebar 1080 dan ditaruh di tengah.
- `crop`: video diskalakan setinggi 1920, lalu dipotong di tengah selebar 1080.
- Subtitle dibakar dengan filter `ass`. Encoding: `libx264 -crf 20 -preset veryfast`, `aac 128k`.
- Satu klip gagal → dicatat, lalu lanjut ke klip berikutnya.

## 4. Penanganan error

- Semua error yang sudah diantisipasi memakai `KlipKilatError(pesan_pengguna, detail_teknis)`. Notebook hanya menampilkan `pesan_pengguna` dalam bahasa Indonesia, berisi apa yang terjadi dan apa yang harus dilakukan. `detail_teknis` dan traceback ditulis ke `log.txt`.
- Error yang tidak terduga ditangkap di `pipeline.jalankan()` dan ditampilkan sebagai: "Terjadi kesalahan yang tidak terduga. Laporkan di GitHub Issues dan lampirkan log.txt."
- GPU dicek di sel pertama notebook. Kalau tidak ada GPU, notebook menampilkan petunjuk cara mengaktifkannya.

| Situasi | Perilaku |
|---|---|
| GPU tidak aktif | Petunjuk mengaktifkan GPU, lalu lanjut di CPU dengan model `small` |
| YouTube gagal | Coba ulang 1×, lalu pesan + saran upload/Drive |
| API key salah atau kuota habis | Pesan spesifik, lalu pindah ke mode manual |
| JSON Gemini tidak valid | Minta ulang ≤2×. Momen tidak valid dibuang. Kalau semua tidak valid, pindah ke mode manual |
| Format timestamp manual salah | Pesan + contoh format |
| Tidak ada ucapan | Pesan yang jelas, proses berhenti |
| Satu klip gagal render | Klip lain tetap diproses, kegagalan dilaporkan di akhir |
| Sesi Colab terputus | Transkrip yang sudah ada dipakai ulang di sesi yang sama |

**Versi library:** semua dependensi dikunci di `pyproject.toml`, **kecuali yt-dlp**, yang selalu memakai versi terbaru.

## 5. Pengujian

Tool dianggap selesai kalau keempat tahap ini lolos:

1. **Tes unit (pytest).** Mencakup: parsing timestamp manual, langkah-langkah `rapikan()`, pengelompokan kata dan timing pada ASS/SRT, parsing JSON Gemini (yang valid, rusak, dan berisi momen tidak valid, dengan klien Gemini dipalsukan), pemetaan error ke pesan pengguna, serta render dengan video sintetis 10 detik buatan FFmpeg (`testsrc` + `sine`) untuk memastikan resolusi output 1080×1920 dan ada stream audio.
2. **Uji alur lengkap di lokal.** Video pendek dengan ucapan, model Whisper `tiny`/`small` di CPU, dan mode timestamp manual. Diberi tanda `@pytest.mark.e2e` dan tidak dijalankan di CI.
3. **GitHub Actions.** Tes unit berjalan di setiap push dan pull request (ubuntu-latest, FFmpeg diinstal via apt).
4. **Uji akhir di Colab sungguhan.** Pemilik repo menjalankannya dengan akun Google-nya: video bahasa Indonesia asli berdurasi sekitar 1 jam, dengan dan tanpa API key Gemini, serta mode `blur` dan `crop`. Hasilnya dicek manual: subtitle pas dengan suara dan klip tidak terpotong di tengah kata.

## 6. Kriteria sukses

- Video bahasa Indonesia sekitar 1 jam menghasilkan 5 klip siap unggah di Colab GPU gratis. Waktu prosesnya diukur dan dicatat di README.
- Pengguna awam bisa memakai tool hanya dengan mengikuti README, tanpa menyentuh kode.
- Semua tahap pengujian di bagian 5 lolos.

## 7. Catatan etika

README mengingatkan pengguna untuk hanya meng-clip konten yang memang boleh di-clip, misalnya lewat program clipping resmi, izin dari kreator, atau konten milik sendiri. Pengguna bertanggung jawab atas konten yang diunggahnya.
