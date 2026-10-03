import json
import sys
from types import SimpleNamespace

import pytest

from klipkilat import momen
from klipkilat.kesalahan import GagalAI


@pytest.fixture
def tr(buat_tr):
    return buat_tr([
        (0, 4, "a b c d"),
        (4, 9, "e f g h i"),
        (10, 15, "j k l m n"),
        (15, 22, "o p q r s t u"),
        (22, 30, "v w x y z a1 a2 a3"),
    ], durasi=40)


def jawaban(*daftar):
    return json.dumps([
        {"judul": j, "mulai_detik": a, "selesai_detik": b, "alasan": "seru"} for j, a, b in daftar
    ])


class LLMPalsu:
    def __init__(self, *respons):
        self.respons = list(respons)
        self.prompt = []

    def __call__(self, prompt):
        self.prompt.append(prompt)
        r = self.respons.pop(0) if len(self.respons) > 1 else self.respons[0]
        if isinstance(r, Exception):
            raise r
        return r


def test_ai_valid(tr):
    llm = LLMPalsu(jawaban(("Satu", 4, 15), ("Dua", 15, 30)))
    hasil = momen.pilih_dengan_ai(tr, 5, 8, 12, llm, judul_video="Podcast Uji")
    assert [m.judul for m in hasil] == ["Satu", "Dua"]
    assert [(m.mulai, m.selesai) for m in hasil] == [(3.7, 15.3), (14.7, 22.3)]
    assert hasil[0].alasan == "seru"


def test_prompt_berisi_transkrip_dan_pengaturan(tr):
    llm = LLMPalsu(jawaban(("Satu", 4, 15)))
    momen.pilih_dengan_ai(tr, 3, 8, 12, llm, judul_video="Podcast Uji")
    prompt = llm.prompt[0]
    assert "[00:00:04 | 4.0 dtk] e f g h i" in prompt
    assert "[jj:mm:dd | detik]" in prompt
    assert "Podcast Uji" in prompt
    assert "3 momen" in prompt
    assert "8" in prompt and "12" in prompt


def test_ai_jawaban_berpagar_markdown(tr):
    llm = LLMPalsu("```json\n" + jawaban(("Satu", 4, 15)) + "\n```")
    assert len(momen.pilih_dengan_ai(tr, 5, 8, 12, llm)) == 1


def test_ai_jawaban_dibungkus_objek(tr):
    isi = json.dumps({"momen": json.loads(jawaban(("Satu", 4, 15)))})
    assert len(momen.pilih_dengan_ai(tr, 5, 8, 12, LLMPalsu(isi))) == 1


def test_ai_diminta_ulang_kalau_bukan_json(tr):
    llm = LLMPalsu("maaf saya tidak bisa", jawaban(("Satu", 4, 15)))
    assert len(momen.pilih_dengan_ai(tr, 5, 8, 12, llm)) == 1
    assert len(llm.prompt) == 2


def test_ai_menyerah_setelah_tiga_kali(tr):
    llm = LLMPalsu("bukan json")
    with pytest.raises(GagalAI) as info:
        momen.pilih_dengan_ai(tr, 5, 8, 12, llm)
    assert info.value.jenis == "format"
    assert len(llm.prompt) == 3


def test_item_tidak_valid_dibuang(tr):
    isi = json.dumps([{"judul": "rusak"}, {"judul": "Satu", "mulai_detik": 4, "selesai_detik": 15}])
    hasil = momen.pilih_dengan_ai(tr, 5, 8, 12, LLMPalsu(isi))
    assert [m.judul for m in hasil] == ["Satu"]


def test_waktu_berformat_jam_diterima(tr):
    isi = json.dumps([{"judul": "Satu", "mulai_detik": "00:00:04", "selesai_detik": "15"}])
    hasil = momen.pilih_dengan_ai(tr, 5, 8, 12, LLMPalsu(isi))
    assert [(m.judul, m.mulai, m.selesai) for m in hasil] == [("Satu", 3.7, 15.3)]


@pytest.mark.parametrize("nilai", [float("nan"), "nan", float("inf"), "1e1", True])
def test_waktu_tidak_wajar_dibuang(tr, nilai):
    isi = json.dumps([{"judul": "rusak", "mulai_detik": nilai, "selesai_detik": 15},
                      {"judul": "Satu", "mulai_detik": 4, "selesai_detik": 15}])
    hasil = momen.pilih_dengan_ai(tr, 5, 8, 12, LLMPalsu(isi))
    assert [m.judul for m in hasil] == ["Satu"]


def test_dipotong_sesuai_jumlah(tr):
    llm = LLMPalsu(jawaban(("A", 0, 9), ("B", 10, 22), ("C", 22, 30)))
    assert [m.judul for m in momen.pilih_dengan_ai(tr, 2, 8, 12, llm)] == ["A", "B"]


def test_error_kuota_langsung_diteruskan(tr):
    llm = LLMPalsu(GagalAI("kuota", "Kuota habis"))
    with pytest.raises(GagalAI) as info:
        momen.pilih_dengan_ai(tr, 5, 8, 12, llm)
    assert info.value.jenis == "kuota"
    assert len(llm.prompt) == 1


class ErrorAPI(Exception):
    def __init__(self, code, pesan):
        super().__init__(pesan)
        self.code = code


@pytest.mark.parametrize("error,jenis", [
    (ErrorAPI(429, "RESOURCE_EXHAUSTED"), "kuota"),
    (ErrorAPI(400, "API key not valid. Please pass a valid API key."), "key"),
    (ErrorAPI(403, "PERMISSION_DENIED"), "key"),
    (ErrorAPI(404, "models/xyz is not found"), "model"),
    (ErrorAPI(503, "UNAVAILABLE"), "sibuk"),
    (ErrorAPI(500, "INTERNAL"), "sibuk"),
    (ErrorAPI(None, "The model is overloaded. Please try again later."), "sibuk"),
    (ValueError("aneh"), "lain"),
])
def test_klasifikasi_error(error, jenis):
    hasil = momen._klasifikasi_error(error)
    assert isinstance(hasil, GagalAI)
    assert hasil.jenis == jenis


def test_klasifikasi_pesan_sibuk_dan_model():
    assert "sibuk" in momen._klasifikasi_error(ErrorAPI(503, "UNAVAILABLE")).pesan_pengguna
    assert "issues" in momen._klasifikasi_error(ErrorAPI(404, "not found")).pesan_pengguna


def test_klasifikasi_library_belum_terpasang():
    hasil = momen._klasifikasi_error(ImportError("No module named 'google.genai'"))
    assert hasil.jenis == "lain"
    assert "sel 1" in hasil.pesan_pengguna


def test_klien_gemini_tanpa_library_jadi_gagal_ai(monkeypatch):
    monkeypatch.setitem(sys.modules, "google.genai", None)
    panggil = momen.buat_klien_gemini("key-palsu")
    with pytest.raises(GagalAI) as info:
        panggil("halo")
    assert "sel 1" in info.value.pesan_pengguna


class KlienPalsu:
    def __init__(self, *hasil):
        self.hasil = list(hasil)
        self.panggilan = 0
        self.models = self

    def generate_content(self, model, contents, config):
        self.panggilan += 1
        r = self.hasil.pop(0)
        if isinstance(r, Exception):
            raise r
        return SimpleNamespace(text=r)


def _pasang_klien(monkeypatch, klien):
    dibuat = []
    monkeypatch.setattr(momen, "_klien_genai", lambda key: dibuat.append(key) or klien)
    return dibuat


def test_klien_gemini_mencoba_ulang_saat_sibuk(monkeypatch):
    klien = KlienPalsu(ErrorAPI(503, "UNAVAILABLE"), ErrorAPI(503, "overloaded"), "[]")
    dibuat = _pasang_klien(monkeypatch, klien)
    tidur = []
    panggil = momen.buat_klien_gemini("key-palsu", jeda=(5, 15), tidur=tidur.append)
    assert panggil("halo") == "[]"
    assert tidur == [5, 15]
    assert klien.panggilan == 3
    assert dibuat == ["key-palsu"]


def test_klien_gemini_menyerah_kalau_tetap_sibuk(monkeypatch):
    klien = KlienPalsu(*[ErrorAPI(503, "UNAVAILABLE")] * 3)
    _pasang_klien(monkeypatch, klien)
    tidur = []
    with pytest.raises(GagalAI) as info:
        momen.buat_klien_gemini("key-palsu", jeda=(5, 15), tidur=tidur.append)("halo")
    assert info.value.jenis == "sibuk"
    assert tidur == [5, 15] and klien.panggilan == 3


def test_klien_gemini_kuota_tidak_dicoba_ulang(monkeypatch):
    klien = KlienPalsu(ErrorAPI(429, "RESOURCE_EXHAUSTED"), "[]")
    _pasang_klien(monkeypatch, klien)
    tidur = []
    with pytest.raises(GagalAI) as info:
        momen.buat_klien_gemini("key-palsu", tidur=tidur.append)("halo")
    assert info.value.jenis == "kuota"
    assert tidur == [] and klien.panggilan == 1
