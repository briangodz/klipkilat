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
