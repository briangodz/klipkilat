# KlipKilat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membangun notebook Google Colab + paket Python `klipkilat` yang mengubah video panjang menjadi klip vertikal 9:16 bersubtitle gaya TikTok, dengan momen seru dipilih Gemini atau timestamp manual.

**Architecture:** Notebook hanya berisi form dan memanggil `klipkilat.pipeline.jalankan()`. Logika dipecah per tugas: `sumber` (ambil video), `transkrip` (Whisper), `momen` (pilih + rapikan), `subtitle` (ASS/SRT), `render` (FFmpeg), dan `paket` (zip). Semua dependensi eksternal (yt-dlp, Whisper, Gemini, unduh font) bisa disuntik lewat parameter, sehingga tes unit tidak butuh jaringan atau GPU.

**Tech Stack:** Python 3.12, faster-whisper, google-genai, yt-dlp, FFmpeg/ffprobe (dengan libass), pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-03-klipkilat-design.md`

## Global Constraints

- Semua teks yang dilihat pengguna memakai bahasa Indonesia. Nama modul, fungsi, dan variabel juga berbahasa Indonesia, mengikuti spec.
- Output klip: 1080×1920, `libx264 -crf 20 -preset veryfast`, `aac 128k`.
- Default: `jumlah_klip` 5 (rentang 1–15), `durasi_min` 30, `durasi_maks` 60, `bahasa` `id` (`id`/`en`/`auto`), `gaya_vertikal` `blur` (`blur`/`crop`).
- Subtitle: maksimal 3 kata per tampilan, kata aktif kuning `&H00FFFF&`, kata lain putih, posisi y = 70% tinggi layar, font `Montserrat ExtraBold` dengan cadangan `DejaVu Sans`.
- Rapikan momen: jeda 0,3 detik di awal dan akhir. Gemini diminta ulang maksimal 2 kali (total 3 percobaan). Unduhan YouTube dicoba ulang 1 kali.
- Error yang sudah diantisipasi = `KlipKilatError(pesan_pengguna, detail_teknis)`. Detail teknis hanya masuk ke `log.txt`.
- Dependensi dikunci dengan `==` di Task 13, **kecuali `yt-dlp`** yang selalu memakai versi terbaru.
- Repo: `https://github.com/briangodz/klipkilat`, branch `main`.
- **Lingkungan lokal (Windows, Git Bash):** semua perintah dijalankan dari root repo. Sebelum menjalankan tes, tambahkan WinGet Links ke PATH:
  `export PATH="$(cygpath "$LOCALAPPDATA")/Microsoft/WinGet/Links:$PATH"`
  Python yang dipakai: `.venv/Scripts/python.exe` (3.12, dibuat dengan uv). Perintah tes di bawah ditulis sebagai `PY -m pytest ...`, dengan `PY` = `.venv/Scripts/python.exe`.
- Setiap pesan commit diakhiri dengan baris kosong lalu `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Struktur File

| File | Tanggung jawab |
|---|---|
| `pyproject.toml` | Metadata paket, dependensi, konfigurasi pytest |
| `.gitignore` | Abaikan venv, cache, data uji, folder kerja |
| `klipkilat/__init__.py` | Versi paket |
| `klipkilat/model.py` | Dataclass `Kata`, `Segmen`, `Transkrip`, `Momen`, `Video`, serta `format_jam()` |
| `klipkilat/kesalahan.py` | `KlipKilatError`, `GagalAI` |
| `klipkilat/proses.py` | Menjalankan FFmpeg/ffprobe: `jalankan`, `durasi`, `punya_audio`, `ukuran_video`, `cek_ffmpeg`. Ditambahkan di luar daftar spec agar pemanggilan FFmpeg tidak tersebar di banyak modul. |
| `klipkilat/sumber.py` | Ambil video dari URL/path, ekstrak audio |
| `klipkilat/transkrip.py` | Whisper, cache transkrip, deteksi GPU |
| `klipkilat/momen.py` | Parsing timestamp manual, `rapikan`, pemilihan via Gemini |
| `klipkilat/subtitle.py` | Pembuatan `.ass` dan `.srt` |
| `klipkilat/render.py` | Siapkan font, render klip vertikal |
| `klipkilat/paket.py` | `momen.md` dan zip |
| `klipkilat/pipeline.py` | `Pengaturan`, `Hasil`, `jalankan()` |
| `scripts/buat_notebook.py` | Membuat `KlipKilat.ipynb` dari teks sel |
| `KlipKilat.ipynb` | Notebook Colab (hasil dari script) |
| `README.md`, `LICENSE` | Dokumentasi berbahasa Indonesia, lisensi MIT |
| `.github/workflows/tes.yml` | CI |
| `tests/conftest.py` | Fixture video sintetis + `buat_tr` |
| `tests/test_*.py` | Satu file tes per modul |

---

### Task 1: Lingkungan & fondasi paket

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `README.md` (sementara), `klipkilat/__init__.py`, `klipkilat/model.py`, `klipkilat/kesalahan.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Produces: `Kata(teks, mulai, selesai)`, `Segmen(teks, mulai, selesai, kata)`, `Transkrip(bahasa, durasi, segmen)` dengan `.semua_kata()`, `.ke_dict()`, `Transkrip.dari_dict(d)`; `Momen(judul, mulai, selesai, alasan="")` dengan properti `.durasi`; `Video(path_video, path_audio, durasi, judul)`; `format_jam(detik) -> "hh:mm:ss"`; `KlipKilatError(pesan_pengguna, detail_teknis="")`; `GagalAI(jenis, pesan_pengguna, detail_teknis="")`.

- [ ] **Step 1: Instal FFmpeg dan uv (minta izin pengguna dulu, karena ini menginstal software)**

```bash
winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements --silent
winget install --id astral-sh.uv -e --accept-package-agreements --accept-source-agreements --silent
export PATH="$(cygpath "$LOCALAPPDATA")/Microsoft/WinGet/Links:$PATH"
ffmpeg -version | head -1 && ffprobe -version | head -1 && uv --version
```
Expected: ketiga versi tercetak. Kalau `ffmpeg` tidak ditemukan di Links, cari dengan `ls "$(cygpath "$LOCALAPPDATA")/Microsoft/WinGet/Packages/" | grep -i ffmpeg`, lalu tambahkan folder `bin`-nya ke PATH dengan cara yang sama.

- [ ] **Step 2: Tulis `pyproject.toml`, `.gitignore`, `README.md` sementara, `klipkilat/__init__.py`**

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "klipkilat"
version = "0.1.0"
description = "Cari momen seru + subtitle otomatis gaya TikTok untuk clipper Indonesia"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
dependencies = [
    "faster-whisper>=1.1.0",
    "google-genai>=1.0.0",
    "yt-dlp",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.setuptools]
packages = ["klipkilat"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-m 'not e2e'"
markers = ["e2e: uji alur lengkap dengan Whisper sungguhan (tidak dijalankan di CI)"]
```

`.gitignore`:
```
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
tests/data/
klipkilat_kerja/
```

`README.md`:
```markdown
# KlipKilat

Tool gratis untuk clipper Indonesia: cari momen seru + subtitle otomatis gaya TikTok, jalan di Google Colab.

(Dokumentasi lengkap menyusul.)
```

`klipkilat/__init__.py`:
```python
"""KlipKilat: ubah video panjang jadi klip pendek vertikal bersubtitle."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Buat venv Python 3.12 dan instal paket**

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.venv/Scripts/python.exe -c "import faster_whisper, google.genai, yt_dlp; print('ok')"
```
Expected: `ok`

- [ ] **Step 4: Tulis tes yang gagal — `tests/test_model.py`**

```python
from klipkilat.kesalahan import GagalAI, KlipKilatError
from klipkilat.model import Kata, Momen, Segmen, Transkrip, format_jam


def _tr():
    return Transkrip("id", 12.5, [
        Segmen("halo dunia", 0.0, 1.0, [Kata("halo", 0.0, 0.5), Kata("dunia", 0.5, 1.0)]),
        Segmen("apa kabar", 2.0, 3.0, [Kata("apa", 2.0, 2.4), Kata("kabar", 2.4, 3.0)]),
    ])


def test_transkrip_bolak_balik_dict():
    tr = _tr()
    assert Transkrip.dari_dict(tr.ke_dict()) == tr


def test_semua_kata_berurutan():
    assert [k.teks for k in _tr().semua_kata()] == ["halo", "dunia", "apa", "kabar"]


def test_durasi_momen():
    assert Momen("a", 10.0, 42.5).durasi == 32.5


def test_format_jam():
    assert format_jam(0) == "00:00:00"
    assert format_jam(59.6) == "00:01:00"
    assert format_jam(3725.4) == "01:02:05"


def test_klipkilat_error_menyimpan_pesan_dan_detail():
    e = KlipKilatError("pesan untuk pengguna", "detail teknis")
    assert str(e) == "pesan untuk pengguna"
    assert e.pesan_pengguna == "pesan untuk pengguna"
    assert e.detail_teknis == "detail teknis"


def test_gagal_ai_adalah_klipkilat_error():
    e = GagalAI("kuota", "Kuota habis")
    assert isinstance(e, KlipKilatError)
    assert e.jenis == "kuota"
    assert e.pesan_pengguna == "Kuota habis"
```

- [ ] **Step 5: Jalankan tes, pastikan gagal**

Run: `PY -m pytest tests/test_model.py -v`
Expected: FAIL / ERROR dengan `ModuleNotFoundError: No module named 'klipkilat.kesalahan'`

- [ ] **Step 6: Implementasi `klipkilat/kesalahan.py`**

```python
"""Jenis error KlipKilat. pesan_pengguna ditampilkan ke pengguna, detail_teknis hanya ke log."""


class KlipKilatError(Exception):
    def __init__(self, pesan_pengguna: str, detail_teknis: str = ""):
        super().__init__(pesan_pengguna)
        self.pesan_pengguna = pesan_pengguna
        self.detail_teknis = detail_teknis


class GagalAI(KlipKilatError):
    """Gagal memakai Gemini. jenis: 'key', 'kuota', 'format', atau 'lain'."""

    def __init__(self, jenis: str, pesan_pengguna: str, detail_teknis: str = ""):
        super().__init__(pesan_pengguna, detail_teknis)
        self.jenis = jenis
```

- [ ] **Step 7: Implementasi `klipkilat/model.py`**

```python
"""Struktur data yang dipakai bersama oleh semua modul KlipKilat. Satuan waktu: detik."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Kata:
    teks: str
    mulai: float
    selesai: float


@dataclass
class Segmen:
    teks: str
    mulai: float
    selesai: float
    kata: list[Kata] = field(default_factory=list)


@dataclass
class Transkrip:
    bahasa: str
    durasi: float
    segmen: list[Segmen] = field(default_factory=list)

    def semua_kata(self) -> list[Kata]:
        return [k for s in self.segmen for k in s.kata]

    def ke_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def dari_dict(cls, data: dict) -> Transkrip:
        return cls(
            bahasa=data["bahasa"],
            durasi=data["durasi"],
            segmen=[
                Segmen(s["teks"], s["mulai"], s["selesai"], [Kata(**k) for k in s["kata"]])
                for s in data["segmen"]
            ],
        )


@dataclass
class Momen:
    judul: str
    mulai: float
    selesai: float
    alasan: str = ""

    @property
    def durasi(self) -> float:
        return self.selesai - self.mulai


@dataclass
class Video:
    path_video: Path
    path_audio: Path
    durasi: float
    judul: str


def format_jam(detik: float) -> str:
    total = int(round(detik))
    jam, sisa = divmod(total, 3600)
    menit, dtk = divmod(sisa, 60)
    return f"{jam:02d}:{menit:02d}:{dtk:02d}"
```

- [ ] **Step 8: Jalankan tes, pastikan lolos**

Run: `PY -m pytest tests/test_model.py -v`
Expected: 6 passed

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .gitignore README.md klipkilat tests
git commit -m "feat: fondasi paket (model data dan jenis error)"
```

---

### Task 2: Pembungkus FFmpeg & fixture media uji

**Files:**
- Create: `klipkilat/proses.py`, `tests/conftest.py`
- Test: `tests/test_proses.py`

**Interfaces:**
- Consumes: `KlipKilatError`, `Kata`, `Segmen`, `Transkrip`
- Produces: `proses.jalankan(args: list[str], cwd: Path | None = None) -> str` (stdout); `proses.durasi(path) -> float`; `proses.punya_audio(path) -> bool`; `proses.ukuran_video(path) -> tuple[int, int]`; `proses.cek_ffmpeg() -> None`. Fixture: `video_sintetis` (1280×720, 10 detik, ada audio), `video_bisu` (tanpa audio), `perlu_ffmpeg` (skip kalau tidak ada ffmpeg), `buat_tr` (fungsi `buat_tr(kalimat: list[tuple[float, float, str]], durasi=None, bahasa="id") -> Transkrip`, kata dibagi rata di dalam segmen).

- [ ] **Step 1: Tulis `tests/conftest.py`**

```python
import shutil
import subprocess

import pytest

from klipkilat.model import Kata, Segmen, Transkrip


def _buat_video(path, dengan_audio=True, detik=10):
    args = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size=1280x720:rate=30:duration={detik}"]
    if dengan_audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={detik}"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if dengan_audio:
        args += ["-c:a", "aac", "-shortest"]
    args.append(str(path))
    subprocess.run(args, check=True, capture_output=True)
    return path


@pytest.fixture(scope="session")
def perlu_ffmpeg():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe tidak terpasang")


@pytest.fixture(scope="session")
def video_sintetis(perlu_ffmpeg, tmp_path_factory):
    return _buat_video(tmp_path_factory.mktemp("media") / "sintetis.mp4")


@pytest.fixture(scope="session")
def video_bisu(perlu_ffmpeg, tmp_path_factory):
    return _buat_video(tmp_path_factory.mktemp("media") / "bisu.mp4", dengan_audio=False)


def buat_transkrip_uji(kalimat, durasi=None, bahasa="id"):
    """kalimat: daftar (mulai, selesai, teks). Waktu kata dibagi rata di dalam segmen."""
    segmen = []
    for mulai, selesai, teks in kalimat:
        kata_teks = teks.split()
        langkah = (selesai - mulai) / len(kata_teks)
        kata = [
            Kata(t, round(mulai + i * langkah, 3), round(mulai + (i + 1) * langkah, 3))
            for i, t in enumerate(kata_teks)
        ]
        segmen.append(Segmen(teks, float(mulai), float(selesai), kata))
    if durasi is None:
        durasi = kalimat[-1][1] if kalimat else 0.0
    return Transkrip(bahasa, float(durasi), segmen)


@pytest.fixture
def buat_tr():
    return buat_transkrip_uji
```

- [ ] **Step 2: Tulis tes yang gagal — `tests/test_proses.py`**

```python
import pytest

from klipkilat import proses
from klipkilat.kesalahan import KlipKilatError


def test_program_tidak_ada_jadi_klipkilat_error():
    with pytest.raises(KlipKilatError) as info:
        proses.jalankan(["program-yang-tidak-ada-123"])
    assert "tidak ditemukan" in info.value.pesan_pengguna


def test_perintah_gagal_menyimpan_stderr(perlu_ffmpeg):
    with pytest.raises(KlipKilatError) as info:
        proses.jalankan(["ffmpeg", "-i", "file_yang_tidak_ada.mp4"])
    assert "file_yang_tidak_ada.mp4" in info.value.detail_teknis


def test_durasi(video_sintetis):
    assert proses.durasi(video_sintetis) == pytest.approx(10.0, abs=0.1)


def test_punya_audio(video_sintetis, video_bisu):
    assert proses.punya_audio(video_sintetis) is True
    assert proses.punya_audio(video_bisu) is False


def test_ukuran_video(video_sintetis):
    assert proses.ukuran_video(video_sintetis) == (1280, 720)


def test_durasi_file_bukan_video(perlu_ffmpeg, tmp_path):
    palsu = tmp_path / "bukan video.mp4"
    palsu.write_text("ini bukan video")
    with pytest.raises(KlipKilatError):
        proses.durasi(palsu)


def test_cek_ffmpeg_tidak_ada(monkeypatch):
    monkeypatch.setattr(proses.shutil, "which", lambda nama: None)
    with pytest.raises(KlipKilatError) as info:
        proses.cek_ffmpeg()
    assert "ffmpeg" in info.value.pesan_pengguna
```

- [ ] **Step 3: Jalankan tes, pastikan gagal**

Run: `PY -m pytest tests/test_proses.py -v`
Expected: ERROR `ImportError: cannot import name 'proses'`

- [ ] **Step 4: Implementasi `klipkilat/proses.py`**

```python
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
            [str(a) for a in args], cwd=cwd, capture_output=True,
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
```

- [ ] **Step 5: Jalankan tes, pastikan lolos**

Run: `PY -m pytest tests/test_proses.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add klipkilat/proses.py tests/conftest.py tests/test_proses.py
git commit -m "feat: pembungkus FFmpeg dan fixture media uji"
```

---

### Task 3: Sumber video

**Files:**
- Create: `klipkilat/sumber.py`
- Test: `tests/test_sumber.py`

**Interfaces:**
- Consumes: `proses.jalankan`, `proses.durasi`, `proses.punya_audio`, `Video`, `KlipKilatError`
- Produces: `sumber.ambil_video(sumber: str, folder_kerja: Path, pengunduh=_unduh_youtube, jeda: float = 3.0) -> Video`. `pengunduh(url, folder) -> tuple[Path, str]` mengembalikan (path video, judul). Audio WAV 16 kHz mono ditulis ke `folder_kerja / "audio.wav"`.

- [ ] **Step 1: Tulis tes yang gagal — `tests/test_sumber.py`**

```python
import shutil

import pytest

from klipkilat import sumber
from klipkilat.kesalahan import KlipKilatError


def test_file_lokal(video_sintetis, tmp_path):
    v = sumber.ambil_video(str(video_sintetis), tmp_path / "kerja dengan spasi")
    assert v.path_video == video_sintetis
    assert v.judul == "sintetis"
    assert v.durasi == pytest.approx(10.0, abs=0.1)
    assert v.path_audio.exists() and v.path_audio.stat().st_size > 0


def test_file_tidak_ada(tmp_path):
    with pytest.raises(KlipKilatError) as info:
        sumber.ambil_video(str(tmp_path / "tidak_ada.mp4"), tmp_path)
    assert "tidak ditemukan" in info.value.pesan_pengguna


def test_video_tanpa_suara(video_bisu, tmp_path):
    with pytest.raises(KlipKilatError) as info:
        sumber.ambil_video(str(video_bisu), tmp_path)
    assert "tidak punya suara" in info.value.pesan_pengguna


def _pengunduh_salin(video_sintetis):
    def unduh(url, folder):
        tujuan = folder / "video_sumber.mp4"
        shutil.copy(video_sintetis, tujuan)
        return tujuan, "Judul Uji"
    return unduh


def test_url_memakai_pengunduh(video_sintetis, tmp_path):
    v = sumber.ambil_video("https://youtu.be/abc", tmp_path, pengunduh=_pengunduh_salin(video_sintetis))
    assert v.judul == "Judul Uji"
    assert v.path_video == tmp_path / "video_sumber.mp4"


def test_url_dicoba_ulang_sekali(video_sintetis, tmp_path):
    panggilan = []
    berhasil = _pengunduh_salin(video_sintetis)

    def unduh(url, folder):
        panggilan.append(url)
        if len(panggilan) == 1:
            raise RuntimeError("HTTP Error 403")
        return berhasil(url, folder)

    v = sumber.ambil_video("https://youtu.be/abc", tmp_path, pengunduh=unduh, jeda=0)
    assert len(panggilan) == 2
    assert v.judul == "Judul Uji"


def test_url_gagal_dua_kali(tmp_path):
    panggilan = []

    def unduh(url, folder):
        panggilan.append(url)
        raise RuntimeError("Sign in to confirm you're not a bot")

    with pytest.raises(KlipKilatError) as info:
        sumber.ambil_video("https://youtu.be/abc", tmp_path, pengunduh=unduh, jeda=0)
    assert len(panggilan) == 2
    assert "YouTube" in info.value.pesan_pengguna
    assert "not a bot" in info.value.detail_teknis
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `PY -m pytest tests/test_sumber.py -v`
Expected: ERROR `ImportError: cannot import name 'sumber'`

- [ ] **Step 3: Implementasi `klipkilat/sumber.py`**

```python
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
```

- [ ] **Step 4: Jalankan tes, pastikan lolos**

Run: `PY -m pytest tests/test_sumber.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add klipkilat/sumber.py tests/test_sumber.py
git commit -m "feat: ambil video dari YouTube atau file, ekstrak audio"
```

---

### Task 4: Transkrip

**Files:**
- Create: `klipkilat/transkrip.py`
- Test: `tests/test_transkrip.py`

**Interfaces:**
- Consumes: `Video`, `Transkrip`, `Segmen`, `Kata`, `KlipKilatError`
- Produces: `transkrip.deteksi_perangkat() -> "cuda" | "cpu"`; `transkrip.pilih_model(perangkat) -> (nama_model, compute_type)`; `transkrip.buat_transkrip(video, bahasa, perangkat, folder_kerja, nama_model=None, transkriptor=None) -> Transkrip`; `transkrip.simpan(tr, path)`; `transkrip.muat(path) -> Transkrip`. `transkriptor(audio, bahasa, perangkat, nama_model, compute_type) -> Transkrip`.

- [ ] **Step 1: Tulis tes yang gagal — `tests/test_transkrip.py`**

```python
import sys

import pytest

from klipkilat import transkrip
from klipkilat.kesalahan import KlipKilatError
from klipkilat.model import Video

KALIMAT_PANJANG = " ".join(f"kata{i}" for i in range(25))


def _video(tmp_path, isi=b"audio palsu"):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(isi)
    return Video(tmp_path / "v.mp4", audio, 60.0, "uji")


def test_pilih_model():
    assert transkrip.pilih_model("cuda") == ("large-v3", "float16")
    assert transkrip.pilih_model("cpu") == ("small", "int8")


def test_deteksi_perangkat_tanpa_ctranslate2(monkeypatch):
    monkeypatch.setitem(sys.modules, "ctranslate2", None)
    assert transkrip.deteksi_perangkat() == "cpu"


def test_transkrip_disimpan_dan_dipakai_ulang(tmp_path, buat_tr):
    tr = buat_tr([(0, 10, KALIMAT_PANJANG)])
    panggilan = []

    def palsu(audio, bahasa, perangkat, nama_model, compute):
        panggilan.append((bahasa, nama_model, compute))
        return tr

    v = _video(tmp_path)
    assert transkrip.buat_transkrip(v, "id", "cuda", tmp_path, transkriptor=palsu) == tr
    assert transkrip.buat_transkrip(v, "id", "cuda", tmp_path, transkriptor=palsu) == tr
    assert panggilan == [("id", "large-v3", "float16")]


def test_bahasa_berbeda_tidak_memakai_cache(tmp_path, buat_tr):
    tr = buat_tr([(0, 10, KALIMAT_PANJANG)])
    panggilan = []

    def palsu(audio, bahasa, perangkat, nama_model, compute):
        panggilan.append(bahasa)
        return tr

    v = _video(tmp_path)
    transkrip.buat_transkrip(v, "id", "cpu", tmp_path, transkriptor=palsu)
    transkrip.buat_transkrip(v, "en", "cpu", tmp_path, transkriptor=palsu)
    assert panggilan == ["id", "en"]


def test_model_bisa_dipaksa(tmp_path, buat_tr):
    tr = buat_tr([(0, 10, KALIMAT_PANJANG)])
    dipakai = []
    transkrip.buat_transkrip(_video(tmp_path), "id", "cpu", tmp_path, nama_model="tiny",
                             transkriptor=lambda a, b, p, m, c: dipakai.append(m) or tr)
    assert dipakai == ["tiny"]


def test_terlalu_sedikit_kata(tmp_path, buat_tr):
    tr = buat_tr([(0, 3, "musik saja")])
    with pytest.raises(KlipKilatError) as info:
        transkrip.buat_transkrip(_video(tmp_path), "id", "cpu", tmp_path,
                                 transkriptor=lambda *a: tr)
    assert "ucapan" in info.value.pesan_pengguna


def test_error_whisper_dibungkus(tmp_path):
    def rusak(*a):
        raise RuntimeError("CUDA out of memory")

    with pytest.raises(KlipKilatError) as info:
        transkrip.buat_transkrip(_video(tmp_path), "id", "cuda", tmp_path, transkriptor=rusak)
    assert "transkrip" in info.value.pesan_pengguna
    assert "CUDA out of memory" in info.value.detail_teknis


def test_simpan_muat(tmp_path, buat_tr):
    tr = buat_tr([(0, 10, KALIMAT_PANJANG)])
    transkrip.simpan(tr, tmp_path / "t.json")
    assert transkrip.muat(tmp_path / "t.json") == tr
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `PY -m pytest tests/test_transkrip.py -v`
Expected: ERROR `ImportError: cannot import name 'transkrip'`

- [ ] **Step 3: Implementasi `klipkilat/transkrip.py`**

```python
"""Mengubah audio menjadi transkrip dengan timestamp per kata (faster-whisper)."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from .kesalahan import KlipKilatError
from .model import Kata, Segmen, Transkrip, Video

log = logging.getLogger("klipkilat")

MIN_KATA = 20


def deteksi_perangkat() -> str:
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def pilih_model(perangkat: str) -> tuple[str, str]:
    return ("large-v3", "float16") if perangkat == "cuda" else ("small", "int8")


def _hash_file(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def simpan(tr: Transkrip, path: Path) -> None:
    Path(path).write_text(json.dumps(tr.ke_dict(), ensure_ascii=False), encoding="utf-8")


def muat(path: Path) -> Transkrip:
    return Transkrip.dari_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _whisper(audio: Path, bahasa: str, perangkat: str, nama_model: str, compute_type: str) -> Transkrip:
    from faster_whisper import WhisperModel

    model = WhisperModel(nama_model, device=perangkat, compute_type=compute_type)
    hasil, info = model.transcribe(
        str(audio),
        language=None if bahasa == "auto" else bahasa,
        word_timestamps=True,
        vad_filter=True,
    )
    segmen = []
    for s in hasil:
        kata = [Kata(w.word.strip(), float(w.start), float(w.end)) for w in (s.words or []) if w.word.strip()]
        if kata:
            segmen.append(Segmen(s.text.strip(), float(s.start), float(s.end), kata))
    return Transkrip(info.language, float(info.duration), segmen)


def buat_transkrip(video: Video, bahasa: str, perangkat: str, folder_kerja: Path,
                   nama_model: str | None = None, transkriptor=None) -> Transkrip:
    model_bawaan, compute_type = pilih_model(perangkat)
    nama_model = nama_model or model_bawaan
    kunci = f"{_hash_file(video.path_audio)[:12]}_{bahasa}_{nama_model}"
    cache = Path(folder_kerja) / f"transkrip_{kunci}.json"
    if cache.exists():
        log.info("Memakai transkrip tersimpan: %s", cache.name)
        return muat(cache)

    log.info("Transkrip dengan model %s di %s", nama_model, perangkat)
    try:
        tr = (transkriptor or _whisper)(video.path_audio, bahasa, perangkat, nama_model, compute_type)
    except KlipKilatError:
        raise
    except Exception as e:
        raise KlipKilatError(
            "Gagal membuat transkrip. Coba Runtime → Restart session, lalu jalankan ulang semua sel.",
            repr(e),
        ) from e

    jumlah_kata = len(tr.semua_kata())
    if jumlah_kata < MIN_KATA:
        raise KlipKilatError(
            "Video ini tidak berisi ucapan yang cukup untuk ditranskrip (mungkin hanya musik atau hening).",
            f"jumlah kata: {jumlah_kata}",
        )
    simpan(tr, cache)
    return tr
```

- [ ] **Step 4: Jalankan tes, pastikan lolos**

Run: `PY -m pytest tests/test_transkrip.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add klipkilat/transkrip.py tests/test_transkrip.py
git commit -m "feat: transkrip Whisper dengan cache dan deteksi GPU"
```

---

### Task 5: Momen — timestamp manual & `rapikan`

**Files:**
- Create: `klipkilat/momen.py`
- Test: `tests/test_momen_manual.py`

**Interfaces:**
- Consumes: `Momen`, `Transkrip`, `format_jam`, `KlipKilatError`
- Produces: `momen.parse_waktu(teks) -> float` (melempar `ValueError` kalau formatnya salah); `momen.dari_teks_manual(teks, transkrip) -> list[Momen]`; `momen.rapikan(momen_list, transkrip, dmin, dmaks, manual=False) -> list[Momen]`; konstanta `momen.CONTOH_MANUAL`, `momen.PADDING = 0.3`.

Transkrip uji untuk semua tes di task ini (durasi 40): segmen `(0,4)`, `(4,9)`, `(10,15)`, `(15,22)`, `(22,30)`. Segmen terakhir berisi 8 kata, masing-masing 1 detik.

- [ ] **Step 1: Tulis tes yang gagal — `tests/test_momen_manual.py`**

```python
import pytest

from klipkilat import momen
from klipkilat.kesalahan import KlipKilatError
from klipkilat.model import Momen


@pytest.fixture
def tr(buat_tr):
    return buat_tr([
        (0, 4, "a b c d"),
        (4, 9, "e f g h i"),
        (10, 15, "j k l m n"),
        (15, 22, "o p q r s t u"),
        (22, 30, "v w x y z a1 a2 a3"),
    ], durasi=40)


def _rentang(daftar):
    return [(pytest.approx(m.mulai), pytest.approx(m.selesai)) for m in daftar]


@pytest.mark.parametrize("teks,detik", [("90", 90), ("01:30", 90), ("1:02:03", 3723), (" 0:05 ", 5)])
def test_parse_waktu(teks, detik):
    assert momen.parse_waktu(teks) == detik


@pytest.mark.parametrize("teks", ["", "abc", "1:2:3:4", "01:"])
def test_parse_waktu_salah(teks):
    with pytest.raises(ValueError):
        momen.parse_waktu(teks)


def test_manual_dirapikan_ke_batas_segmen(tr):
    hasil = momen.dari_teks_manual("00:05-00:12, 0:16-0:21", tr)
    assert [m.judul for m in hasil] == ["Klip 1", "Klip 2"]
    assert _rentang(hasil) == [(3.7, 15.3), (14.7, 22.3)]


def test_manual_baris_baru_juga_pemisah(tr):
    assert len(momen.dari_teks_manual("00:05-00:12\n0:16-0:21", tr)) == 2


@pytest.mark.parametrize("teks", ["abc", "00:05", "00:05-00:10-00:12"])
def test_manual_format_salah(tr, teks):
    with pytest.raises(KlipKilatError) as info:
        momen.dari_teks_manual(teks, tr)
    assert "Contoh" in info.value.pesan_pengguna


def test_manual_kosong(tr):
    with pytest.raises(KlipKilatError):
        momen.dari_teks_manual("  ", tr)


def test_manual_di_luar_durasi(tr):
    with pytest.raises(KlipKilatError) as info:
        momen.dari_teks_manual("01:00-01:10", tr)
    assert "di luar durasi" in info.value.pesan_pengguna


def test_rapikan_geser_ke_batas_segmen(tr):
    assert _rentang(momen.rapikan([Momen("x", 5, 12)], tr, 8, 12)) == [(3.7, 15.3)]


def test_rapikan_awal_di_celah_maju_ke_segmen_berikutnya(tr):
    assert _rentang(momen.rapikan([Momen("x", 9.5, 21)], tr, 8, 12)) == [(9.7, 22.3)]


def test_rapikan_terlalu_panjang_dipotong_di_batas_segmen(tr):
    assert _rentang(momen.rapikan([Momen("x", 4, 29)], tr, 8, 12)) == [(3.7, 15.3)]


def test_rapikan_satu_segmen_terlalu_panjang_dipotong_di_batas_kata(tr):
    assert _rentang(momen.rapikan([Momen("x", 22, 30)], tr, 2, 5)) == [(21.7, 27.3)]


def test_rapikan_terlalu_pendek_diperpanjang(tr):
    assert _rentang(momen.rapikan([Momen("x", 0, 3)], tr, 8, 12)) == [(0.0, 9.3)]


def test_rapikan_buang_yang_bertumpuk(tr):
    hasil = momen.rapikan([Momen("A", 4, 15), Momen("B", 10, 20)], tr, 8, 12)
    assert [m.judul for m in hasil] == ["A"]


def test_rapikan_buang_yang_tidak_valid(tr):
    assert momen.rapikan([Momen("luar", 50, 60), Momen("terbalik", 30, 25)], tr, 8, 12) == []


def test_rapikan_akhir_melebihi_durasi(tr):
    assert _rentang(momen.rapikan([Momen("x", 25, 55)], tr, 8, 12)) == [(21.7, 30.3)]
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `PY -m pytest tests/test_momen_manual.py -v`
Expected: ERROR `ImportError: cannot import name 'momen'`

- [ ] **Step 3: Implementasi `klipkilat/momen.py` (bagian manual + rapikan)**

```python
"""Menentukan momen yang dijadikan klip: dari timestamp manual atau dari Gemini."""
from __future__ import annotations

import logging
import re

from .kesalahan import KlipKilatError
from .model import Momen, Segmen, Transkrip, format_jam

log = logging.getLogger("klipkilat")

PADDING = 0.3
CONTOH_MANUAL = "01:23:10-01:24:00, 02:05:00-02:05:45"


def parse_waktu(teks: str) -> float:
    bagian = teks.strip().split(":")
    if not 1 <= len(bagian) <= 3 or any(b.strip() == "" for b in bagian):
        raise ValueError(f"format waktu tidak dikenali: {teks!r}")
    detik = 0.0
    for b in bagian:
        detik = detik * 60 + float(b)
    return detik


def dari_teks_manual(teks: str, transkrip: Transkrip) -> list[Momen]:
    potongan = [p.strip() for p in re.split(r"[,;\n]+", teks) if p.strip()]
    if not potongan:
        raise KlipKilatError(f"Kolom timestamp_manual kosong. Contoh: {CONTOH_MANUAL}")
    daftar = []
    for i, p in enumerate(potongan, 1):
        try:
            awal, akhir = p.split("-")
            daftar.append(Momen(f"Klip {i}", parse_waktu(awal), parse_waktu(akhir), "Dipilih manual"))
        except ValueError:
            raise KlipKilatError(
                f"Format timestamp '{p}' tidak dikenali. Tulis mulai-selesai, dipisah koma. "
                f"Contoh: {CONTOH_MANUAL}"
            ) from None
    hasil = rapikan(daftar, transkrip, 0, 0, manual=True)
    if not hasil:
        raise KlipKilatError(
            f"Semua timestamp manual berada di luar durasi video ({format_jam(transkrip.durasi)}) "
            "atau tidak valid (mulai harus lebih kecil dari selesai)."
        )
    return hasil


def _segmen_awal(transkrip: Transkrip, t: float) -> Segmen | None:
    return next((s for s in transkrip.segmen if s.mulai <= t < s.selesai), None)


def _segmen_akhir(transkrip: Transkrip, t: float) -> Segmen | None:
    return next((s for s in transkrip.segmen if s.mulai < t <= s.selesai), None)


def _geser_awal(transkrip: Transkrip, t: float) -> float:
    s = _segmen_awal(transkrip, t)
    if s:
        return s.mulai
    berikutnya = [s.mulai for s in transkrip.segmen if s.mulai >= t]
    return min(berikutnya) if berikutnya else t


def _geser_akhir(transkrip: Transkrip, t: float) -> float:
    s = _segmen_akhir(transkrip, t)
    if s:
        return s.selesai
    sebelumnya = [s.selesai for s in transkrip.segmen if s.selesai <= t]
    return max(sebelumnya) if sebelumnya else t


def _potong_maks(transkrip: Transkrip, mulai: float, dmaks: float) -> float:
    batas = mulai + dmaks
    ujung = [s.selesai for s in transkrip.segmen if mulai < s.selesai <= batas]
    if not ujung:
        ujung = [k.selesai for k in transkrip.semua_kata() if mulai < k.selesai <= batas]
    return max(ujung) if ujung else batas


def _perpanjang_min(transkrip: Transkrip, mulai: float, selesai: float, dmin: float, dmaks: float) -> float:
    for s in sorted(transkrip.segmen, key=lambda s: s.mulai):
        if selesai - mulai >= dmin:
            break
        if s.selesai <= selesai:
            continue
        if s.selesai - mulai > dmaks:
            break
        selesai = s.selesai
    return selesai


def _bertumpuk(a: Momen, b: Momen) -> bool:
    return a.mulai < b.selesai and b.mulai < a.selesai


def rapikan(momen_list: list[Momen], transkrip: Transkrip, dmin: float, dmaks: float,
            manual: bool = False) -> list[Momen]:
    """Validasi momen dan geser titik potong ke batas kalimat (lihat spec bagian 3.3)."""
    hasil: list[Momen] = []
    for m in momen_list:
        mulai, selesai = max(0.0, m.mulai), min(transkrip.durasi, m.selesai)
        if mulai >= selesai:
            log.info("Momen dibuang (di luar durasi/terbalik): %s", m)
            continue
        mulai, selesai = _geser_awal(transkrip, mulai), _geser_akhir(transkrip, selesai)
        if mulai >= selesai:
            log.info("Momen dibuang (tidak berisi ucapan): %s", m)
            continue
        if not manual:
            if selesai - mulai > dmaks:
                selesai = _potong_maks(transkrip, mulai, dmaks)
            if selesai - mulai < dmin:
                selesai = _perpanjang_min(transkrip, mulai, selesai, dmin, dmaks)
        baru = Momen(m.judul, mulai, selesai, m.alasan)
        if not manual and any(_bertumpuk(baru, k) for k in hasil):
            log.info("Momen dibuang (bertumpuk): %s", m)
            continue
        hasil.append(baru)
    for m in hasil:
        m.mulai = round(max(0.0, m.mulai - PADDING), 3)
        m.selesai = round(min(transkrip.durasi, m.selesai + PADDING), 3)
    return hasil
```

- [ ] **Step 4: Jalankan tes, pastikan lolos**

Run: `PY -m pytest tests/test_momen_manual.py -v`
Expected: semua passed (25 tes, termasuk parametrize)

- [ ] **Step 5: Commit**

```bash
git add klipkilat/momen.py tests/test_momen_manual.py
git commit -m "feat: timestamp manual dan perapian momen ke batas kalimat"
```

---

### Task 6: Momen — pemilihan dengan Gemini

**Files:**
- Modify: `klipkilat/momen.py` (tambahkan bagian AI di bawah kode yang sudah ada)
- Test: `tests/test_momen_ai.py`

**Interfaces:**
- Consumes: `rapikan`, `GagalAI`, `format_jam`
- Produces: `momen.pilih_dengan_ai(transkrip, jumlah, dmin, dmaks, panggil_llm, judul_video="") -> list[Momen]`; `momen.buat_klien_gemini(api_key, model=MODEL_GEMINI) -> Callable[[str], str]`; `momen.MODEL_GEMINI`. `panggil_llm(prompt) -> str` boleh melempar `GagalAI`.

- [ ] **Step 1: Pastikan nama model Gemini Flash terbaru di kuota gratis**

Buka `https://ai.google.dev/gemini-api/docs/models` dan `https://ai.google.dev/gemini-api/docs/pricing` (WebFetch). Pilih model **Flash** stabil terbaru (bukan preview) yang punya kuota gratis. Pakai namanya untuk `MODEL_GEMINI` di Step 4. Kalau halaman tidak bisa dibuka, pakai `"gemini-2.5-flash"`. Nama ini akan diverifikasi lagi di uji Colab (Task 13).

- [ ] **Step 2: Tulis tes yang gagal — `tests/test_momen_ai.py`**

```python
import json
import sys

import pytest

from klipkilat import momen
from klipkilat.kesalahan import GagalAI


@pytest.fixture
def tr(buat_tr):
    return buat_tr([
        (0, 4, "a b c d"),
        (4, 9, "e f g h i"),
        (10, 15, "j k l m n"),
        (15, 22, "o p q r s t u"),
        (22, 30, "v w x y z a1 a2 a3"),
    ], durasi=40)


def jawaban(*daftar):
    return json.dumps([
        {"judul": j, "mulai_detik": a, "selesai_detik": b, "alasan": "seru"} for j, a, b in daftar
    ])


class LLMPalsu:
    def __init__(self, *respons):
        self.respons = list(respons)
        self.prompt = []

    def __call__(self, prompt):
        self.prompt.append(prompt)
        r = self.respons.pop(0) if len(self.respons) > 1 else self.respons[0]
        if isinstance(r, Exception):
            raise r
        return r


def test_ai_valid(tr):
    llm = LLMPalsu(jawaban(("Satu", 4, 15), ("Dua", 15, 30)))
    hasil = momen.pilih_dengan_ai(tr, 5, 8, 12, llm, judul_video="Podcast Uji")
    assert [m.judul for m in hasil] == ["Satu", "Dua"]
    assert [(m.mulai, m.selesai) for m in hasil] == [(3.7, 15.3), (14.7, 22.3)]
    assert hasil[0].alasan == "seru"


def test_prompt_berisi_transkrip_dan_pengaturan(tr):
    llm = LLMPalsu(jawaban(("Satu", 4, 15)))
    momen.pilih_dengan_ai(tr, 3, 8, 12, llm, judul_video="Podcast Uji")
    prompt = llm.prompt[0]
    assert "[00:00:04] e f g h i" in prompt
    assert "Podcast Uji" in prompt
    assert "3 momen" in prompt
    assert "8" in prompt and "12" in prompt


def test_ai_jawaban_berpagar_markdown(tr):
    llm = LLMPalsu("```json\n" + jawaban(("Satu", 4, 15)) + "\n```")
    assert len(momen.pilih_dengan_ai(tr, 5, 8, 12, llm)) == 1


def test_ai_jawaban_dibungkus_objek(tr):
    isi = json.dumps({"momen": json.loads(jawaban(("Satu", 4, 15)))})
    assert len(momen.pilih_dengan_ai(tr, 5, 8, 12, LLMPalsu(isi))) == 1


def test_ai_diminta_ulang_kalau_bukan_json(tr):
    llm = LLMPalsu("maaf saya tidak bisa", jawaban(("Satu", 4, 15)))
    assert len(momen.pilih_dengan_ai(tr, 5, 8, 12, llm)) == 1
    assert len(llm.prompt) == 2


def test_ai_menyerah_setelah_tiga_kali(tr):
    llm = LLMPalsu("bukan json")
    with pytest.raises(GagalAI) as info:
        momen.pilih_dengan_ai(tr, 5, 8, 12, llm)
    assert info.value.jenis == "format"
    assert len(llm.prompt) == 3


def test_item_tidak_valid_dibuang(tr):
    isi = json.dumps([{"judul": "rusak"}, {"judul": "Satu", "mulai_detik": 4, "selesai_detik": 15}])
    hasil = momen.pilih_dengan_ai(tr, 5, 8, 12, LLMPalsu(isi))
    assert [m.judul for m in hasil] == ["Satu"]


def test_dipotong_sesuai_jumlah(tr):
    llm = LLMPalsu(jawaban(("A", 0, 9), ("B", 10, 22), ("C", 22, 30)))
    assert [m.judul for m in momen.pilih_dengan_ai(tr, 2, 8, 12, llm)] == ["A", "B"]


def test_error_kuota_langsung_diteruskan(tr):
    llm = LLMPalsu(GagalAI("kuota", "Kuota habis"))
    with pytest.raises(GagalAI) as info:
        momen.pilih_dengan_ai(tr, 5, 8, 12, llm)
    assert info.value.jenis == "kuota"
    assert len(llm.prompt) == 1


class ErrorAPI(Exception):
    def __init__(self, code, pesan):
        super().__init__(pesan)
        self.code = code


@pytest.mark.parametrize("error,jenis", [
    (ErrorAPI(429, "RESOURCE_EXHAUSTED"), "kuota"),
    (ErrorAPI(400, "API key not valid. Please pass a valid API key."), "key"),
    (ErrorAPI(403, "PERMISSION_DENIED"), "key"),
    (ErrorAPI(404, "models/xyz is not found"), "lain"),
    (ValueError("aneh"), "lain"),
])
def test_klasifikasi_error(error, jenis):
    hasil = momen._klasifikasi_error(error)
    assert isinstance(hasil, GagalAI)
    assert hasil.jenis == jenis


def test_klien_gemini_tanpa_library_jadi_gagal_ai(monkeypatch):
    monkeypatch.setitem(sys.modules, "google.genai", None)
    panggil = momen.buat_klien_gemini("key-palsu")
    with pytest.raises(GagalAI):
        panggil("halo")
```

- [ ] **Step 3: Jalankan tes, pastikan gagal**

Run: `PY -m pytest tests/test_momen_ai.py -v`
Expected: FAIL dengan `AttributeError: module 'klipkilat.momen' has no attribute 'pilih_dengan_ai'`

- [ ] **Step 4: Tambahkan bagian AI ke `klipkilat/momen.py`**

Ubah impor di bagian atas file:
```python
import json
import logging
import re
from typing import Callable

from .kesalahan import GagalAI, KlipKilatError
from .model import Momen, Segmen, Transkrip, format_jam
```

Tambahkan di bawah konstanta `CONTOH_MANUAL`:
```python
MODEL_GEMINI = "gemini-2.5-flash"  # ganti sesuai hasil Step 1
PERCOBAAN_AI = 3

PROMPT = """Kamu adalah editor video pendek (TikTok/Reels/Shorts) yang jago menemukan momen viral.
Di bawah ini transkrip video berjudul "{judul}". Setiap baris diawali waktu mulai [jj:mm:dd].

Pilih {jumlah} momen terbaik untuk dijadikan klip pendek. Syarat setiap momen:
- Berdiri sendiri: penonton paham tanpa menonton video lengkapnya.
- Punya "hook" kuat di beberapa detik pertama (mengejutkan, lucu, kontroversial, emosional, atau informasi berharga).
- Durasi antara {dmin} dan {dmaks} detik.
- Tidak saling bertumpuk.
Urutkan dari momen yang paling berpotensi viral.

Jawab HANYA dengan JSON berupa daftar objek dengan kunci:
"judul" (judul klip yang menarik, maksimal 60 karakter), "mulai_detik" (angka), "selesai_detik" (angka),
"alasan" (1 kalimat kenapa momen ini menarik).
Tulis "judul" dan "alasan" dalam bahasa yang sama dengan transkrip.

TRANSKRIP:
{transkrip}
"""
```

Tambahkan di akhir file:
```python
def _format_transkrip(transkrip: Transkrip) -> str:
    return "\n".join(f"[{format_jam(s.mulai)}] {s.teks}" for s in transkrip.segmen)


def _ambil_json(teks: str) -> list:
    teks = re.sub(r"^```(?:json)?\s*|\s*```$", "", teks.strip())
    data = json.loads(teks)
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), None)
    if not isinstance(data, list):
        raise ValueError("JSON bukan daftar momen")
    return data


def _ke_momen(item) -> Momen | None:
    try:
        return Momen(
            str(item.get("judul") or "Momen").strip()[:80],
            float(item["mulai_detik"]),
            float(item["selesai_detik"]),
            str(item.get("alasan") or "").strip(),
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def pilih_dengan_ai(transkrip: Transkrip, jumlah: int, dmin: float, dmaks: float,
                    panggil_llm: Callable[[str], str], judul_video: str = "") -> list[Momen]:
    prompt = PROMPT.format(judul=judul_video or "tanpa judul", jumlah=jumlah, dmin=int(dmin),
                           dmaks=int(dmaks), transkrip=_format_transkrip(transkrip))
    for percobaan in range(1, PERCOBAAN_AI + 1):
        jawaban = panggil_llm(prompt)
        try:
            data = _ambil_json(jawaban)
        except ValueError as e:
            log.warning("Percobaan %d: jawaban Gemini bukan JSON yang valid (%s): %.300s", percobaan, e, jawaban)
            continue
        kandidat = [m for m in (_ke_momen(x) for x in data) if m is not None]
        hasil = rapikan(kandidat, transkrip, dmin, dmaks)[:jumlah]
        if hasil:
            return hasil
        log.warning("Percobaan %d: tidak ada momen valid dari %d kandidat", percobaan, len(kandidat))
    raise GagalAI("format", f"AI tidak memberikan momen yang valid setelah {PERCOBAAN_AI} kali mencoba.")


def _klasifikasi_error(e: Exception) -> GagalAI:
    kode = getattr(e, "code", None)
    pesan = str(e)
    if kode == 429 or "RESOURCE_EXHAUSTED" in pesan:
        return GagalAI("kuota", "Kuota gratis API Gemini sedang habis. Coba lagi nanti atau besok.", pesan)
    if kode in (401, 403) or (kode == 400 and "API key" in pesan):
        return GagalAI("key", "API key Gemini tidak valid. Buat key baru di https://aistudio.google.com/apikey "
                              "lalu tempel ulang.", pesan)
    return GagalAI("lain", "Gagal menghubungi Gemini.", f"{type(e).__name__}: {pesan}")


def buat_klien_gemini(api_key: str, model: str = MODEL_GEMINI) -> Callable[[str], str]:
    def panggil(prompt: str) -> str:
        try:
            from google import genai
            from google.genai import types

            klien = genai.Client(api_key=api_key)
            respons = klien.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.4),
            )
            return respons.text or ""
        except Exception as e:
            raise _klasifikasi_error(e) from e

    return panggil
```

- [ ] **Step 5: Jalankan tes, pastikan lolos (termasuk tes Task 5)**

Run: `PY -m pytest tests/test_momen_ai.py tests/test_momen_manual.py -v`
Expected: semua passed

- [ ] **Step 6: Commit**

```bash
git add klipkilat/momen.py tests/test_momen_ai.py
git commit -m "feat: pilih momen seru dengan Gemini, termasuk validasi dan percobaan ulang"
```

---

### Task 7: Subtitle

**Files:**
- Create: `klipkilat/subtitle.py`
- Test: `tests/test_subtitle.py`

**Interfaces:**
- Consumes: `Kata`, `Momen`, `Transkrip`
- Produces: `subtitle.kelompokkan(transkrip, momen) -> list[list[Kata]]`; `subtitle.buat_ass(transkrip, momen, nama_font="Montserrat ExtraBold") -> str`; `subtitle.buat_srt(transkrip, momen) -> str`. Semua waktu relatif terhadap `momen.mulai`.

- [ ] **Step 1: Tulis tes yang gagal — `tests/test_subtitle.py`**

```python
import pytest

from klipkilat import subtitle
from klipkilat.model import Momen


@pytest.fixture
def tr(buat_tr):
    # kata: satu 10-11, dua 11-12, tiga 12-13, empat 13-14, lima 14-15, enam 15-16
    return buat_tr([(10, 14, "satu dua tiga empat"), (14, 16, "lima enam")], durasi=20)


def _teks(grup):
    return [[k.teks for k in g] for g in grup]


def test_kelompok_maksimal_tiga_dan_tidak_melewati_segmen(tr):
    grup = subtitle.kelompokkan(tr, Momen("x", 10.5, 15.5))
    assert _teks(grup) == [["satu", "dua", "tiga"], ["empat"], ["lima", "enam"]]


def test_kata_di_luar_momen_tidak_ikut(tr):
    assert _teks(subtitle.kelompokkan(tr, Momen("x", 12.5, 13.5))) == [["tiga", "empat"]]


def test_ass_header_dan_font(tr):
    ass = subtitle.buat_ass(tr, Momen("x", 10.5, 15.5), "DejaVu Sans")
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert "Style: Default,DejaVu Sans," in ass


def test_ass_satu_baris_per_kata_dengan_highlight(tr):
    ass = subtitle.buat_ass(tr, Momen("x", 10.5, 15.5))
    dialog = [b for b in ass.splitlines() if b.startswith("Dialogue:")]
    assert len(dialog) == 6
    assert dialog[0].startswith("Dialogue: 0,0:00:00.00,0:00:00.50,Default,")
    assert dialog[0].endswith("{\\pos(540,1344)}{\\c&H00FFFF&}satu{\\c&HFFFFFF&} dua tiga")
    assert dialog[1].endswith("satu {\\c&H00FFFF&}dua{\\c&HFFFFFF&} tiga")
    assert dialog[5].startswith("Dialogue: 0,0:00:04.50,0:00:05.00,")


def test_ass_karakter_khusus_dibersihkan(buat_tr):
    tr = buat_tr([(0, 2, "{halo} a\\b")])
    ass = subtitle.buat_ass(tr, Momen("x", 0, 2))
    assert "(halo)" in ass and "a/b" in ass


def test_srt(tr):
    srt = subtitle.buat_srt(tr, Momen("x", 10, 16))
    assert srt == (
        "1\n00:00:00,000 --> 00:00:03,000\nsatu dua tiga\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\nempat\n\n"
        "3\n00:00:04,000 --> 00:00:06,000\nlima enam\n"
    )


def test_format_waktu():
    assert subtitle._waktu_ass(3725.456) == "1:02:05.46"
    assert subtitle._waktu_srt(3725.456) == "01:02:05,456"
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `PY -m pytest tests/test_subtitle.py -v`
Expected: ERROR `ImportError: cannot import name 'subtitle'`

- [ ] **Step 3: Implementasi `klipkilat/subtitle.py`**

```python
"""Membuat subtitle gaya TikTok (.ass, kata aktif di-highlight) dan .srt untuk satu klip."""
from __future__ import annotations

from .model import Kata, Momen, Transkrip

MAKS_KATA = 3
LEBAR, TINGGI = 1080, 1920
POS_X, POS_Y = LEBAR // 2, int(TINGGI * 0.7)
KUNING = "&H00FFFF&"
PUTIH = "&HFFFFFF&"

HEADER_ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: {lebar}
PlayResY: {tinggi}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def kelompokkan(transkrip: Transkrip, momen: Momen) -> list[list[Kata]]:
    grup = []
    for s in transkrip.segmen:
        kata = [k for k in s.kata if k.selesai > momen.mulai and k.mulai < momen.selesai]
        for i in range(0, len(kata), MAKS_KATA):
            grup.append(kata[i:i + MAKS_KATA])
    return grup


def _relatif(t: float, momen: Momen) -> float:
    return min(max(t - momen.mulai, 0.0), momen.durasi)


def _waktu_ass(t: float) -> str:
    cs = round(t * 100)
    jam, sisa = divmod(cs, 360000)
    menit, sisa = divmod(sisa, 6000)
    detik, centi = divmod(sisa, 100)
    return f"{jam}:{menit:02d}:{detik:02d}.{centi:02d}"


def _waktu_srt(t: float) -> str:
    ms = round(t * 1000)
    jam, sisa = divmod(ms, 3600000)
    menit, sisa = divmod(sisa, 60000)
    detik, milidetik = divmod(sisa, 1000)
    return f"{jam:02d}:{menit:02d}:{detik:02d},{milidetik:03d}"


def _bersihkan(teks: str) -> str:
    return teks.replace("\\", "/").replace("{", "(").replace("}", ")")


def buat_ass(transkrip: Transkrip, momen: Momen, nama_font: str = "Montserrat ExtraBold") -> str:
    baris = []
    for grup in kelompokkan(transkrip, momen):
        for i, aktif in enumerate(grup):
            mulai = _relatif(aktif.mulai, momen)
            akhir = grup[i + 1].mulai if i + 1 < len(grup) else aktif.selesai
            selesai = _relatif(akhir, momen)
            if selesai <= mulai:
                continue
            teks = " ".join(
                f"{{\\c{KUNING}}}{_bersihkan(k.teks)}{{\\c{PUTIH}}}" if k is aktif else _bersihkan(k.teks)
                for k in grup
            )
            baris.append(
                f"Dialogue: 0,{_waktu_ass(mulai)},{_waktu_ass(selesai)},Default,,0,0,0,,"
                f"{{\\pos({POS_X},{POS_Y})}}{teks}"
            )
    return HEADER_ASS.format(lebar=LEBAR, tinggi=TINGGI, font=nama_font) + "\n".join(baris) + "\n"


def buat_srt(transkrip: Transkrip, momen: Momen) -> str:
    entri = []
    for grup in kelompokkan(transkrip, momen):
        mulai, selesai = _relatif(grup[0].mulai, momen), _relatif(grup[-1].selesai, momen)
        if selesai <= mulai:
            continue
        teks = " ".join(k.teks for k in grup)
        entri.append(f"{len(entri) + 1}\n{_waktu_srt(mulai)} --> {_waktu_srt(selesai)}\n{teks}\n")
    return "\n".join(entri)
```

- [ ] **Step 4: Jalankan tes, pastikan lolos**

Run: `PY -m pytest tests/test_subtitle.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add klipkilat/subtitle.py tests/test_subtitle.py
git commit -m "feat: subtitle gaya TikTok (.ass) dan .srt"
```

---

### Task 8: Render klip vertikal

**Files:**
- Create: `klipkilat/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `proses.jalankan`, `Video`, `Momen`, `KlipKilatError`, `subtitle.buat_ass` (hanya di tes)
- Produces: `render.siapkan_font(folder_font: Path, unduh=_unduh) -> str` (nama font untuk ASS); `render.render_klip(video, momen, path_ass, gaya, keluaran, folder_font) -> Path`. FFmpeg dijalankan dengan `cwd=path_ass.parent`, dan filter merujuk ASS serta folder font dengan path relatif, supaya spasi dan `C:\` di Windows tidak merusak sintaks filter.

- [ ] **Step 1: Tulis tes yang gagal — `tests/test_render.py`**

```python
import pytest

from klipkilat import proses, render, subtitle
from klipkilat.kesalahan import KlipKilatError
from klipkilat.model import Momen, Video


def test_font_berhasil_diunduh(tmp_path):
    def unduh(url, tujuan):
        tujuan.write_bytes(b"x" * 20_000)

    assert render.siapkan_font(tmp_path / "font", unduh=unduh) == render.FONT_UTAMA


def test_font_gagal_diunduh_pakai_cadangan(tmp_path):
    def unduh(url, tujuan):
        raise OSError("tidak ada internet")

    assert render.siapkan_font(tmp_path / "font", unduh=unduh) == render.FONT_CADANGAN


def test_font_rusak_pakai_cadangan(tmp_path):
    def unduh(url, tujuan):
        tujuan.write_bytes(b"halaman error")

    assert render.siapkan_font(tmp_path / "font", unduh=unduh) == render.FONT_CADANGAN
    assert not (tmp_path / "font" / "Montserrat-ExtraBold.ttf").exists()


def test_font_sudah_ada_tidak_diunduh_ulang(tmp_path):
    folder = tmp_path / "font"
    folder.mkdir()
    (folder / "Montserrat-ExtraBold.ttf").write_bytes(b"x" * 20_000)

    def unduh(url, tujuan):
        raise AssertionError("tidak boleh mengunduh")

    assert render.siapkan_font(folder, unduh=unduh) == render.FONT_UTAMA


@pytest.mark.parametrize("gaya", ["blur", "crop"])
def test_render_klip_vertikal(video_sintetis, tmp_path, buat_tr, gaya):
    kerja = tmp_path / "folder dengan spasi"
    (kerja / "font").mkdir(parents=True)
    tr = buat_tr([(1, 4, "halo ini uji subtitle"), (4, 8, "klip vertikal pertama kita")], durasi=10)
    m = Momen("uji", 2.0, 5.0)
    path_ass = kerja / "klip_01.ass"
    path_ass.write_text(subtitle.buat_ass(tr, m, render.FONT_CADANGAN), encoding="utf-8")
    video = Video(video_sintetis, video_sintetis, 10.0, "uji")

    hasil = render.render_klip(video, m, path_ass, gaya, kerja / "hasil" / "klip_01.mp4", kerja / "font")

    assert hasil.exists()
    assert proses.ukuran_video(hasil) == (1080, 1920)
    assert proses.punya_audio(hasil)
    assert proses.durasi(hasil) == pytest.approx(3.0, abs=0.2)


def test_gaya_tidak_dikenal(tmp_path):
    with pytest.raises(KlipKilatError):
        render.render_klip(Video(tmp_path, tmp_path, 1, "x"), Momen("x", 0, 1),
                           tmp_path / "a.ass", "miring", tmp_path / "o.mp4", tmp_path)
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `PY -m pytest tests/test_render.py -v`
Expected: ERROR `ImportError: cannot import name 'render'`

- [ ] **Step 3: Implementasi `klipkilat/render.py`**

```python
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
```

Catatan: string `"crop"` di dalam f-string memakai `{{ass}}` supaya tetap menjadi `{ass}` untuk `.format()`. String `"blur"` hanya baris pertamanya yang berupa f-string, jadi baris ketiganya memakai `{ass}` biasa.

- [ ] **Step 4: Jalankan tes, pastikan lolos**

Run: `PY -m pytest tests/test_render.py -v`
Expected: 7 passed. Kalau tes render gagal karena filter `ass` tidak dikenal, berarti build FFmpeg tidak punya libass. Pastikan yang terpasang adalah build Gyan (`ffmpeg -filters | grep ass`).

- [ ] **Step 5: Commit**

```bash
git add klipkilat/render.py tests/test_render.py
git commit -m "feat: render klip vertikal (blur/crop) dengan subtitle tertanam"
```

---

### Task 9: Paket hasil

**Files:**
- Create: `klipkilat/paket.py`
- Test: `tests/test_paket.py`

**Interfaces:**
- Consumes: `Momen`, `format_jam`
- Produces: `paket.tulis_momen_md(momen_list, judul_video, path, gagal: set[int] = frozenset()) -> None` (nomor klip dimulai dari 1); `paket.buat_zip(folder_hasil, path_zip) -> Path`.

- [ ] **Step 1: Tulis tes yang gagal — `tests/test_paket.py`**

```python
import zipfile

from klipkilat import paket
from klipkilat.model import Momen


def test_momen_md(tmp_path):
    daftar = [Momen("Pengakuan mengejutkan", 3725.0, 3770.0, "Hook kuat"), Momen("Lucu", 10.0, 40.0, "Ngakak")]
    path = tmp_path / "momen.md"
    paket.tulis_momen_md(daftar, "Podcast Uji", path, gagal={2})
    isi = path.read_text(encoding="utf-8")
    assert "# Momen dari: Podcast Uji" in isi
    assert "## 1. Pengakuan mengejutkan" in isi
    assert "klip_01.mp4" in isi
    assert "01:02:05 – 01:02:50 (45 detik)" in isi
    assert "Hook kuat" in isi
    assert "gagal dibuat" in isi
    assert "klip_02.mp4" not in isi


def test_buat_zip(tmp_path):
    hasil = tmp_path / "hasil"
    hasil.mkdir()
    (hasil / "klip_01.mp4").write_bytes(b"video")
    (hasil / "momen.md").write_text("isi", encoding="utf-8")
    path_zip = paket.buat_zip(hasil, tmp_path / "hasil.zip")
    with zipfile.ZipFile(path_zip) as z:
        assert sorted(z.namelist()) == ["klip_01.mp4", "momen.md"]
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `PY -m pytest tests/test_paket.py -v`
Expected: ERROR `ImportError: cannot import name 'paket'`

- [ ] **Step 3: Implementasi `klipkilat/paket.py`**

```python
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
                z.write(f, f.relative_to(folder_hasil).as_posix())
    return path_zip
```

- [ ] **Step 4: Jalankan tes, pastikan lolos**

Run: `PY -m pytest tests/test_paket.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add klipkilat/paket.py tests/test_paket.py
git commit -m "feat: momen.md dan zip hasil"
```

---

### Task 10: Pipeline

**Files:**
- Create: `klipkilat/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: semua modul di atas, persis dengan signature yang didefinisikan di task-task sebelumnya.
- Produces: `Pengaturan(sumber, folder_kerja=Path("klipkilat_kerja"), jumlah_klip=5, durasi_min=30.0, durasi_maks=60.0, bahasa="id", gaya_vertikal="blur", gemini_api_key="", timestamp_manual="", model_whisper=None)`; `Hasil(path_zip, klip_berhasil, klip_gagal, peringatan, momen)`; `jalankan(pengaturan, tampil=print) -> Hasil` yang hanya melempar `KlipKilatError`. Log ditulis ke `folder_kerja/log.txt`.

- [ ] **Step 1: Tulis tes yang gagal — `tests/test_pipeline.py`**

```python
import json
import zipfile

import pytest

from klipkilat import momen as modul_momen
from klipkilat import pipeline, proses, render, sumber
from klipkilat import transkrip as modul_transkrip
from klipkilat.kesalahan import GagalAI, KlipKilatError
from klipkilat.model import Video


@pytest.fixture
def lingkungan(monkeypatch, tmp_path, buat_tr):
    """Mengganti semua bagian berat (FFmpeg, Whisper, render) dengan versi palsu."""
    tr = buat_tr([(i * 5, i * 5 + 5, "kata satu dua tiga empat") for i in range(12)], durasi=60)
    status = {"render_gagal": set(), "render_dipanggil": []}

    def render_palsu(video, m, path_ass, gaya, keluaran, folder_font):
        nomor = len(status["render_dipanggil"]) + 1
        status["render_dipanggil"].append((m, gaya, path_ass.read_text(encoding="utf-8")))
        if nomor in status["render_gagal"]:
            raise KlipKilatError("Perintah ffmpeg gagal.", "stderr palsu")
        keluaran.parent.mkdir(parents=True, exist_ok=True)
        keluaran.write_bytes(b"mp4 palsu")
        return keluaran

    monkeypatch.setattr(proses, "cek_ffmpeg", lambda: None)
    monkeypatch.setattr(sumber, "ambil_video",
                        lambda s, folder: Video(tmp_path / "v.mp4", tmp_path / "a.wav", 60.0, "Video Uji"))
    monkeypatch.setattr(modul_transkrip, "deteksi_perangkat", lambda: "cuda")
    monkeypatch.setattr(modul_transkrip, "buat_transkrip", lambda *a, **k: tr)
    monkeypatch.setattr(render, "siapkan_font", lambda folder: "DejaVu Sans")
    monkeypatch.setattr(render, "render_klip", render_palsu)
    status["tr"] = tr
    return status


def _p(tmp_path, **ubah):
    nilai = dict(sumber="video.mp4", folder_kerja=tmp_path / "kerja", durasi_min=8, durasi_maks=12)
    nilai.update(ubah)
    return pipeline.Pengaturan(**nilai)


def test_mode_manual_menghasilkan_zip_lengkap(lingkungan, tmp_path):
    hasil = pipeline.jalankan(_p(tmp_path, timestamp_manual="00:05-00:15, 00:20-00:30"), tampil=lambda s: None)
    assert len(hasil.klip_berhasil) == 2 and hasil.klip_gagal == []
    with zipfile.ZipFile(hasil.path_zip) as z:
        nama = set(z.namelist())
    assert {"klip_01.mp4", "klip_02.mp4", "klip_01.srt", "klip_02.srt",
            "momen.md", "transkrip.json", "log.txt"} <= nama
    assert "Dialogue:" in lingkungan["render_dipanggil"][0][2]


def test_satu_klip_gagal_yang_lain_tetap_jalan(lingkungan, tmp_path):
    lingkungan["render_gagal"] = {1}
    hasil = pipeline.jalankan(_p(tmp_path, timestamp_manual="00:05-00:15, 00:20-00:30"), tampil=lambda s: None)
    assert len(hasil.klip_berhasil) == 1
    assert len(hasil.klip_gagal) == 1 and "Klip 1" in hasil.klip_gagal[0]
    with zipfile.ZipFile(hasil.path_zip) as z:
        assert "klip_01.srt" not in z.namelist()
        assert "gagal dibuat" in z.read("momen.md").decode("utf-8")


def test_semua_klip_gagal(lingkungan, tmp_path):
    lingkungan["render_gagal"] = {1, 2}
    with pytest.raises(KlipKilatError) as info:
        pipeline.jalankan(_p(tmp_path, timestamp_manual="00:05-00:15, 00:20-00:30"), tampil=lambda s: None)
    assert "Semua klip gagal" in info.value.pesan_pengguna


def test_tanpa_key_dan_tanpa_manual(lingkungan, tmp_path):
    with pytest.raises(KlipKilatError) as info:
        pipeline.jalankan(_p(tmp_path), tampil=lambda s: None)
    assert "timestamp_manual" in info.value.pesan_pengguna


def test_ai_berhasil(lingkungan, tmp_path, monkeypatch):
    jawaban = json.dumps([{"judul": "Seru", "mulai_detik": 10, "selesai_detik": 20, "alasan": "hook"}])
    monkeypatch.setattr(modul_momen, "buat_klien_gemini", lambda key: (lambda prompt: jawaban))
    hasil = pipeline.jalankan(_p(tmp_path, gemini_api_key="abc"), tampil=lambda s: None)
    assert [m.judul for m in hasil.momen] == ["Seru"]


def test_ai_gagal_pindah_ke_manual(lingkungan, tmp_path, monkeypatch):
    def klien(key):
        def panggil(prompt):
            raise GagalAI("kuota", "Kuota gratis API Gemini sedang habis.")
        return panggil

    monkeypatch.setattr(modul_momen, "buat_klien_gemini", klien)
    tampilan = []
    with pytest.raises(KlipKilatError) as info:
        pipeline.jalankan(_p(tmp_path, gemini_api_key="abc"), tampil=tampilan.append)
    assert "timestamp_manual" in info.value.pesan_pengguna
    assert any("Kuota" in t for t in tampilan)


def test_manual_mengalahkan_ai(lingkungan, tmp_path, monkeypatch):
    def klien(key):
        raise AssertionError("AI tidak boleh dipanggil")

    monkeypatch.setattr(modul_momen, "buat_klien_gemini", klien)
    hasil = pipeline.jalankan(_p(tmp_path, gemini_api_key="abc", timestamp_manual="00:05-00:15"),
                              tampil=lambda s: None)
    assert len(hasil.momen) == 1


def test_peringatan_tanpa_gpu(lingkungan, tmp_path, monkeypatch):
    monkeypatch.setattr(modul_transkrip, "deteksi_perangkat", lambda: "cpu")
    hasil = pipeline.jalankan(_p(tmp_path, timestamp_manual="00:05-00:15"), tampil=lambda s: None)
    assert any("GPU" in p for p in hasil.peringatan)


@pytest.mark.parametrize("ubah", [
    {"jumlah_klip": 0}, {"jumlah_klip": 16}, {"durasi_min": 60, "durasi_maks": 30},
    {"bahasa": "jp"}, {"gaya_vertikal": "miring"}, {"sumber": "  "},
])
def test_validasi_pengaturan(lingkungan, tmp_path, ubah):
    with pytest.raises(KlipKilatError):
        pipeline.jalankan(_p(tmp_path, timestamp_manual="00:05-00:15", **ubah), tampil=lambda s: None)


def test_error_tak_terduga_dibungkus_dan_dicatat(lingkungan, tmp_path, monkeypatch):
    def meledak(s, folder):
        raise RuntimeError("bug tersembunyi")

    monkeypatch.setattr(sumber, "ambil_video", meledak)
    with pytest.raises(KlipKilatError) as info:
        pipeline.jalankan(_p(tmp_path, timestamp_manual="00:05-00:15"), tampil=lambda s: None)
    assert "tidak terduga" in info.value.pesan_pengguna
    log = (tmp_path / "kerja" / "log.txt").read_text(encoding="utf-8")
    assert "RuntimeError: bug tersembunyi" in log
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `PY -m pytest tests/test_pipeline.py -v`
Expected: ERROR `ImportError: cannot import name 'pipeline'`

- [ ] **Step 3: Implementasi `klipkilat/pipeline.py`**

```python
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
    tr = modul_transkrip.buat_transkrip(video, p.bahasa, perangkat, folder_kerja, nama_model=p.model_whisper)

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
```

- [ ] **Step 4: Jalankan tes pipeline, lalu seluruh tes**

Run: `PY -m pytest tests/test_pipeline.py -v`, lalu `PY -m pytest -v`
Expected: semua passed

- [ ] **Step 5: Commit**

```bash
git add klipkilat/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline lengkap dengan penanganan error dan log"
```

---

### Task 11: Notebook Colab, README, lisensi, CI

**Files:**
- Create: `scripts/buat_notebook.py`, `KlipKilat.ipynb` (hasil script), `LICENSE`, `.github/workflows/tes.yml`
- Modify: `README.md` (ganti seluruh isinya)
- Test: `tests/test_notebook.py`

**Interfaces:**
- Consumes: `klipkilat.pipeline.Pengaturan`, `klipkilat.pipeline.jalankan`, `klipkilat.kesalahan.KlipKilatError`, `Hasil.momen`, `Hasil.klip_gagal`, `Hasil.path_zip`
- Produces: `KlipKilat.ipynb` dengan metadata `accelerator: GPU` dan dua sel kode (Persiapan, Pengaturan).

- [ ] **Step 1: Tulis tes yang gagal — `tests/test_notebook.py`**

```python
import dataclasses
import json
from pathlib import Path

from klipkilat.pipeline import Pengaturan

NOTEBOOK = Path(__file__).resolve().parents[1] / "KlipKilat.ipynb"


def _nb():
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def _kode(nb):
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def test_notebook_meminta_gpu():
    assert _nb()["metadata"]["accelerator"] == "GPU"


def test_sel_kode_valid_python():
    kode = _kode(_nb())
    assert len(kode) == 2
    for sumber in kode:
        tanpa_shell = "\n".join(b for b in sumber.splitlines() if not b.lstrip().startswith("!"))
        compile(tanpa_shell, "sel", "exec")


def test_semua_pengaturan_diteruskan():
    sel_pengaturan = _kode(_nb())[1]
    for f in dataclasses.fields(Pengaturan):
        if f.name != "model_whisper":
            assert f"{f.name}=" in sel_pengaturan, f.name


def test_menginstal_dari_repo_ini():
    assert "git+https://github.com/briangodz/klipkilat" in _kode(_nb())[0]
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `PY -m pytest tests/test_notebook.py -v`
Expected: FAIL `FileNotFoundError` (KlipKilat.ipynb belum ada)

- [ ] **Step 3: Tulis `scripts/buat_notebook.py`**

```python
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
```

- [ ] **Step 4: Buat notebook dan jalankan tes**

Run: `PY scripts/buat_notebook.py && PY -m pytest tests/test_notebook.py -v`
Expected: `Ditulis: ...KlipKilat.ipynb`, lalu 4 passed

- [ ] **Step 5: Tulis `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 briangodz

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 6: Tulis `.github/workflows/tes.yml`**

```yaml
name: tes

on:
  push:
  pull_request:

jobs:
  tes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Pasang FFmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg
      - name: Pasang paket
        run: pip install -e ".[dev]"
      - name: Jalankan tes
        run: pytest -v
```

- [ ] **Step 7: Tulis ulang `README.md`**

````markdown
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
````

- [ ] **Step 8: Jalankan seluruh tes**

Run: `PY -m pytest -v`
Expected: semua passed

- [ ] **Step 9: Commit**

```bash
git add scripts KlipKilat.ipynb LICENSE .github README.md tests/test_notebook.py
git commit -m "feat: notebook Colab, README, lisensi MIT, dan CI"
```

---

### Task 12: Uji alur lengkap di lokal (e2e)

**Files:**
- Create: `tests/test_e2e.py`
- Data uji (tidak di-commit, `tests/data/` ada di .gitignore): `tests/data/ucapan.wav`, `tests/data/e2e.mp4`

**Interfaces:**
- Consumes: `pipeline.Pengaturan` (dengan `model_whisper="tiny"`), `pipeline.jalankan`, `proses.ukuran_video`, `proses.punya_audio`

- [ ] **Step 1: Buat audio ucapan dengan TTS Windows, lalu gabungkan dengan video sintetis**

```powershell
New-Item -ItemType Directory -Force tests\data | Out-Null
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SetOutputToWaveFile("$PWD\tests\data\ucapan.wav")
$s.Speak("Hello everyone, this is a test video for KlipKilat. We are checking that the transcript works, that the subtitles appear on screen, and that every clip is cut into a vertical video. If you can read these words on the screen, the test was a success. Thank you for watching and see you next time.")
$s.Dispose()
```
```bash
ffmpeg -y -f lavfi -i testsrc=size=1280x720:rate=30 -i tests/data/ucapan.wav -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac tests/data/e2e.mp4
```

- [ ] **Step 2: Tulis `tests/test_e2e.py`**

```python
"""Uji alur lengkap dengan Whisper sungguhan. Jalankan:
KLIPKILAT_VIDEO_E2E=tests/data/e2e.mp4 pytest -m e2e -v
"""
import os
import zipfile

import pytest

from klipkilat import proses
from klipkilat.pipeline import Pengaturan, jalankan


@pytest.mark.e2e
def test_alur_lengkap(tmp_path):
    video = os.environ.get("KLIPKILAT_VIDEO_E2E")
    if not video:
        pytest.skip("Set KLIPKILAT_VIDEO_E2E ke path video berisi ucapan")
    hasil = jalankan(Pengaturan(
        sumber=video,
        folder_kerja=tmp_path / "kerja",
        bahasa=os.environ.get("KLIPKILAT_BAHASA_E2E", "en"),
        timestamp_manual="00:00-00:12",
        model_whisper="tiny",
    ))
    assert len(hasil.klip_berhasil) == 1
    klip = hasil.klip_berhasil[0]
    assert proses.ukuran_video(klip) == (1080, 1920)
    assert proses.punya_audio(klip)
    with zipfile.ZipFile(hasil.path_zip) as z:
        srt = z.read("klip_01.srt").decode("utf-8").lower()
    assert "test" in srt
```

- [ ] **Step 3: Jalankan e2e**

Run: `KLIPKILAT_VIDEO_E2E=tests/data/e2e.mp4 PY -m pytest -m e2e -v`
Expected: 1 passed. Unduhan pertama model `tiny` membutuhkan internet. Kalau gagal, perbaiki akar masalahnya dengan skill systematic-debugging, lalu jalankan ulang seluruh tes.

- [ ] **Step 4: Cek hasil secara visual**

Ekstrak satu frame dari klip (salin `hasil.zip` dari folder `tmp_path` yang tercetak, atau jalankan pipeline sekali lewat script kecil di scratchpad), lalu lihat gambarnya dengan Read:
```bash
ffmpeg -y -ss 3 -i <path klip_01.mp4> -frames:v 1 <scratchpad>/frame.png
```
Expected: frame 1080×1920 berisi video di tengah, latar blur, dan subtitle putih dengan satu kata kuning di sekitar 70% tinggi layar.

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test: uji alur lengkap dengan Whisper sungguhan"
```

---

### Task 13: Kunci versi, push, dan uji akhir di Colab

**Files:**
- Modify: `pyproject.toml` (bagian dependencies), `README.md` (tambah bagian perkiraan waktu), mungkin `klipkilat/momen.py` (`MODEL_GEMINI`)

- [ ] **Step 1: Kunci versi dependensi**

Run: `uv pip show --python .venv/Scripts/python.exe faster-whisper google-genai | grep -E "^(Name|Version)"`
Ganti `"faster-whisper>=1.1.0"` dan `"google-genai>=1.0.0"` di `pyproject.toml` menjadi `==<versi yang tercetak>`. `yt-dlp` tetap tanpa versi.

- [ ] **Step 2: Jalankan ulang seluruh tes, lalu commit dan push (konfirmasi ke pengguna sebelum push)**

```bash
PY -m pytest -v
git add pyproject.toml
git commit -m "build: kunci versi dependensi"
git push origin main
```
Lalu cek CI sekali: `gh run list --limit 1`. Expected: status `completed success`. Kalau masih `in_progress`, beri tahu pengguna dan cek lagi setelah pengguna membalas.

- [ ] **Step 3: Uji Colab bersama pengguna**

Kirim link `https://colab.research.google.com/github/briangodz/klipkilat/blob/main/KlipKilat.ipynb` ke pengguna dan pandu langkah demi langkah. Checklist (pengguna menjalankan, Claude memeriksa output yang dilaporkan atau ditempel pengguna):
1. Sel 1 menampilkan "✅ GPU aktif" dan instalasi selesai tanpa error.
2. Video bahasa Indonesia sekitar 1 jam + `gemini_api_key` + `blur`: 5 klip terbentuk. **Catat waktu proses** (transkrip dan total).
3. Video yang sama, tanpa key, dengan `timestamp_manual` + `crop`: transkrip memakai cache (cepat), dan klip terbentuk.
4. Pengguna membuka 2 klip dan memastikan subtitle pas dengan suara serta klip tidak terpotong di tengah kata.
5. Kalau Gemini mengembalikan error 404 model, perbarui `MODEL_GEMINI` dengan model Flash yang tersedia, jalankan tes, commit, push, lalu ulangi langkah 2.

Setiap masalah yang muncul diperbaiki dengan skill systematic-debugging, ditambahkan tes yang mereproduksinya bila memungkinkan, lalu di-commit dan push sebelum checklist diulang.

- [ ] **Step 4: Catat waktu proses di README**

Tambahkan bagian berikut di bawah tabel kolom pada `README.md`, isi angkanya dari hasil Step 3:
```markdown
## Perkiraan waktu (Colab GPU T4 gratis)

Video bahasa Indonesia berdurasi <D> menit: transkrip ±<T> menit, total sampai 5 klip jadi ±<W> menit.
Menjalankan ulang video yang sama (misalnya mengganti timestamp) melewati tahap transkrip.
```
`<D>`, `<T>`, dan `<W>` diganti dengan angka hasil pengukuran, bukan dibiarkan seperti itu.

- [ ] **Step 5: Commit dan push**

```bash
git add README.md klipkilat/momen.py
git commit -m "docs: catat waktu proses hasil uji di Colab"
git push origin main
```
