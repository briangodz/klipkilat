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


def test_stdin_tidak_diwarisi(monkeypatch):
    dipanggil = {}

    def run_palsu(args, **k):
        dipanggil.update(k)
        return proses.subprocess.CompletedProcess(args, 0, "ok", "")

    monkeypatch.setattr(proses.subprocess, "run", run_palsu)
    assert proses.jalankan(["ffmpeg", "-version"]) == "ok"
    assert dipanggil["stdin"] is proses.subprocess.DEVNULL
