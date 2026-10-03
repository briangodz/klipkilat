import json
import sys

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
    assert "[00:00:04] e f g h i" in prompt
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
    (ErrorAPI(404, "models/xyz is not found"), "lain"),
    (ValueError("aneh"), "lain"),
])
def test_klasifikasi_error(error, jenis):
    hasil = momen._klasifikasi_error(error)
    assert isinstance(hasil, GagalAI)
    assert hasil.jenis == jenis


def test_klien_gemini_tanpa_library_jadi_gagal_ai(monkeypatch):
    monkeypatch.setitem(sys.modules, "google.genai", None)
    panggil = momen.buat_klien_gemini("key-palsu")
    with pytest.raises(GagalAI):
        panggil("halo")
