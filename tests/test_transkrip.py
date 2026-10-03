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
