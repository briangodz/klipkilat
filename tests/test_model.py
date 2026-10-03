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
