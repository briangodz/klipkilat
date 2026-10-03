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
