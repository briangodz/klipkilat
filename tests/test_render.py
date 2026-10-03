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


def test_render_hanya_memetakan_audio_pertama(tmp_path, monkeypatch):
    perintah = []
    monkeypatch.setattr(proses, "jalankan", lambda args, cwd=None: perintah.append(args) or "")
    render.render_klip(Video(tmp_path / "v.mp4", tmp_path / "a.wav", 10, "x"), Momen("x", 0, 1),
                       tmp_path / "a.ass", "crop", tmp_path / "o.mp4", tmp_path)
    args = perintah[0]
    assert args[args.index("[v]") + 2] == "0:a:0?"
