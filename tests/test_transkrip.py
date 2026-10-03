import sys
from types import SimpleNamespace

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


def test_simpan_atomik_tanpa_sisa_tmp(tmp_path, buat_tr, monkeypatch):
    diganti = []
    asli = transkrip.os.replace
    monkeypatch.setattr(transkrip.os, "replace", lambda a, b: diganti.append((str(a), str(b))) or asli(a, b))
    tr = buat_tr([(0, 10, KALIMAT_PANJANG)])
    transkrip.simpan(tr, tmp_path / "t.json")
    assert diganti == [(str(tmp_path / "t.json.tmp"), str(tmp_path / "t.json"))]
    assert list(tmp_path.glob("*.tmp")) == []
    assert transkrip.muat(tmp_path / "t.json") == tr


@pytest.mark.parametrize("isi_rusak", ['{"bahasa": "id", "dur', '{"bahasa": "id"}', "[1, 2]", ""])
def test_cache_rusak_dianggap_tidak_ada(tmp_path, buat_tr, isi_rusak):
    tr = buat_tr([(0, 10, KALIMAT_PANJANG)])
    panggilan = []

    def palsu(audio, bahasa, perangkat, nama_model, compute):
        panggilan.append(bahasa)
        return tr

    v = _video(tmp_path)
    transkrip.buat_transkrip(v, "id", "cpu", tmp_path, transkriptor=palsu)
    (cache,) = tmp_path.glob("transkrip_*.json")
    cache.write_text(isi_rusak, encoding="utf-8")

    assert transkrip.buat_transkrip(v, "id", "cpu", tmp_path, transkriptor=palsu) == tr
    assert panggilan == ["id", "id"]
    assert transkrip.muat(cache) == tr


class WhisperPalsu:
    """Pengganti faster_whisper.WhisperModel: tidak memuat model sungguhan."""

    opsi = {}

    def __init__(self, nama, device, compute_type):
        pass

    def transcribe(self, audio, **opsi):
        WhisperPalsu.opsi = opsi
        segmen = [
            SimpleNamespace(text=f" kalimat {i}", start=i * 10.0, end=i * 10.0 + 10,
                            words=[SimpleNamespace(word=f" k{i}_{j}", start=i * 10.0 + j, end=i * 10.0 + j + 1)
                                   for j in range(5)])
            for i in range(5)
        ]
        return iter(segmen), SimpleNamespace(language="id", duration=50.0)


@pytest.fixture
def whisper_palsu(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=WhisperPalsu))
    return WhisperPalsu


def test_whisper_melaporkan_kemajuan(tmp_path, whisper_palsu):
    pesan = []
    tr = transkrip.buat_transkrip(_video(tmp_path), "id", "cpu", tmp_path, kemajuan=pesan.append)
    assert len(tr.semua_kata()) == 25
    assert pesan == [f"📝 Transkrip {p}%" for p in (20, 40, 60, 80, 100)]
    assert whisper_palsu.opsi["condition_on_previous_text"] is False


def test_whisper_tanpa_kemajuan(tmp_path, whisper_palsu):
    assert len(transkrip.buat_transkrip(_video(tmp_path), "id", "cpu", tmp_path).semua_kata()) == 25
