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


def test_zip_mp4_tidak_dikompres_ulang(tmp_path):
    hasil = tmp_path / "hasil"
    hasil.mkdir()
    (hasil / "klip_01.mp4").write_bytes(b"video" * 100)
    (hasil / "momen.md").write_text("isi " * 100, encoding="utf-8")
    with zipfile.ZipFile(paket.buat_zip(hasil, tmp_path / "hasil.zip")) as z:
        assert z.getinfo("klip_01.mp4").compress_type == zipfile.ZIP_STORED
        assert z.getinfo("momen.md").compress_type == zipfile.ZIP_DEFLATED
