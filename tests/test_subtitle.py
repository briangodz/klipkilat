import pytest

from klipkilat import subtitle
from klipkilat.model import Kata, Momen, Segmen, Transkrip


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


def test_kelompok_bertumpuk_dipotong_sampai_kelompok_berikutnya():
    # Whisper kadang memberi waktu kata yang bertumpuk antar-segmen.
    tr = Transkrip("id", 5.0, [
        Segmen("a b", 0.0, 2.0, [Kata("a", 0.0, 1.0), Kata("b", 1.0, 2.0)]),
        Segmen("c", 1.5, 3.0, [Kata("c", 1.5, 3.0)]),
    ])
    m = Momen("x", 0, 3)
    assert subtitle.buat_srt(tr, m) == (
        "1\n00:00:00,000 --> 00:00:01,500\na b\n\n"
        "2\n00:00:01,500 --> 00:00:03,000\nc\n"
    )
    dialog = [b for b in subtitle.buat_ass(tr, m).splitlines() if b.startswith("Dialogue:")]
    assert dialog[1].startswith("Dialogue: 0,0:00:01.00,0:00:01.50,")
    assert dialog[2].startswith("Dialogue: 0,0:00:01.50,0:00:03.00,")
