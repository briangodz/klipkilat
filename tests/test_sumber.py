import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

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


def test_error_klipkilat_dari_pengunduh_tidak_dicoba_ulang(tmp_path):
    panggilan = []

    def unduh(url, folder):
        panggilan.append(url)
        raise KlipKilatError("Live stream ini masih berlangsung.")

    with pytest.raises(KlipKilatError) as info:
        sumber.ambil_video("https://youtu.be/abc", tmp_path, pengunduh=unduh, jeda=0)
    assert len(panggilan) == 1
    assert "Live" in info.value.pesan_pengguna


@pytest.mark.parametrize("kutip", ['"', "'"])
def test_path_lokal_berkutip(video_sintetis, tmp_path, kutip):
    v = sumber.ambil_video(f" {kutip}{video_sintetis}{kutip} ", tmp_path)
    assert v.path_video == video_sintetis


class YDLPalsu:
    """Pengganti yt_dlp.YoutubeDL: tidak pernah menyentuh internet."""

    info = {}
    unduhan = []

    def __init__(self, opsi):
        self.opsi = opsi
        YDLPalsu.opsi_terakhir = opsi

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        assert not download
        return dict(self.info)

    def process_ie_result(self, info, download=True):
        path = Path(self.opsi["outtmpl"].replace("%(id)s", info["id"]).replace("%(ext)s", "mp4"))
        path.write_bytes(b"video palsu")
        YDLPalsu.unduhan.append(path)
        return {**info, "requested_downloads": [{"filepath": str(path)}]}


@pytest.fixture
def ydl_palsu(monkeypatch):
    monkeypatch.setattr(YDLPalsu, "info", {"id": "abc123", "title": "Judul YT", "live_status": "was_live"})
    monkeypatch.setattr(YDLPalsu, "unduhan", [])
    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=YDLPalsu))
    return YDLPalsu


def test_unduh_youtube_memakai_ulang_file_yang_sudah_ada(ydl_palsu, tmp_path):
    lain = tmp_path / "video_sumber_lain.mp4"
    lain.write_bytes(b"video lain")
    (tmp_path / "video_sumber_abc123.f137.mp4").write_bytes(b"sisa unduhan")

    pertama = sumber._unduh_youtube("https://youtu.be/abc123", tmp_path)
    kedua = sumber._unduh_youtube("https://youtu.be/abc123", tmp_path)

    assert pertama == kedua == (tmp_path / "video_sumber_abc123.mp4", "Judul YT")
    assert len(ydl_palsu.unduhan) == 1
    assert lain.exists()


def test_unduh_youtube_link_dari_playlist_hanya_ambil_satu_video(ydl_palsu, tmp_path):
    sumber._unduh_youtube("https://www.youtube.com/watch?v=abc123&list=PLxyz", tmp_path)
    assert ydl_palsu.opsi_terakhir["noplaylist"] is True


@pytest.mark.parametrize("info", [
    {"is_live": True}, {"live_status": "is_live"}, {"live_status": "is_upcoming"}, {"live_status": "post_live"},
])
def test_unduh_youtube_menolak_live(ydl_palsu, tmp_path, monkeypatch, info):
    monkeypatch.setattr(YDLPalsu, "info", {"id": "abc123", "title": "Live", **info})
    with pytest.raises(KlipKilatError) as e:
        sumber._unduh_youtube("https://youtu.be/abc123", tmp_path)
    assert "Live stream" in e.value.pesan_pengguna
    assert ydl_palsu.unduhan == []
