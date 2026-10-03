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


@pytest.mark.parametrize("teks,detik", [
    ("90", 90), ("01:30", 90), ("1:02:03", 3723), (" 0:05 ", 5), ("01.30", 90), ("1.02.03", 3723),
])
def test_parse_waktu(teks, detik):
    assert momen.parse_waktu(teks) == detik


@pytest.mark.parametrize("teks", ["", "abc", "1:2:3:4", "01:", "nan", "1e2", "1:75", "-5", "1:02.5.3"])
def test_parse_waktu_salah(teks):
    with pytest.raises(ValueError):
        momen.parse_waktu(teks)


def test_manual_dirapikan_ke_batas_segmen(tr):
    hasil = momen.dari_teks_manual("00:05-00:12, 0:16-0:21", tr)
    assert [m.judul for m in hasil] == ["Klip 1", "Klip 2"]
    assert _rentang(hasil) == [(3.7, 15.3), (14.7, 22.3)]


def test_manual_format_titik(buat_tr):
    tr = buat_tr([(80, 88, "a b c d"), (88, 100, "e f g h i"), (100, 134, "j k l m n"),
                  (134, 140, "o p q"), (140, 150, "r s t")], durasi=160)
    assert _rentang(momen.dari_teks_manual("01.30-02.15", tr)) == [(87.7, 140.3)]


@pytest.mark.parametrize("pisah", ["–", "—", " - ", " – "])
def test_manual_tanda_pisah_en_dan_em(tr, pisah):
    assert _rentang(momen.dari_teks_manual(f"00:05{pisah}00:12", tr)) == [(3.7, 15.3)]


def test_manual_baris_baru_juga_pemisah(tr):
    assert len(momen.dari_teks_manual("00:05-00:12\n0:16-0:21", tr)) == 2


@pytest.mark.parametrize("teks", ["abc", "00:05", "00:05-00:10-00:12", "nan-00:10", "1e1-2e1", "00:05-1:75"])
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
