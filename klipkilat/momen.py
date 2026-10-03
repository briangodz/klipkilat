"""Menentukan momen yang dijadikan klip: dari timestamp manual atau dari Gemini."""
from __future__ import annotations

import json
import logging
import re
from typing import Callable

from .kesalahan import GagalAI, KlipKilatError
from .model import Momen, Segmen, Transkrip, format_jam

log = logging.getLogger("klipkilat")

PADDING = 0.3
CONTOH_MANUAL = "01:23:10-01:24:00, 02:05:00-02:05:45"

MODEL_GEMINI = "gemini-3.8-flash"  # Flash stabil terbaru berkuota gratis per dokumen Google (Task 6 Step 1)
PERCOBAAN_AI = 3

PROMPT = """Kamu adalah editor video pendek (TikTok/Reels/Shorts) yang jago menemukan momen viral.
Di bawah ini transkrip video berjudul "{judul}". Setiap baris diawali waktu mulai [jj:mm:dd].

Pilih {jumlah} momen terbaik untuk dijadikan klip pendek. Syarat setiap momen:
- Berdiri sendiri: penonton paham tanpa menonton video lengkapnya.
- Punya "hook" kuat di beberapa detik pertama (mengejutkan, lucu, kontroversial, emosional, atau informasi berharga).
- Durasi antara {dmin} dan {dmaks} detik.
- Tidak saling bertumpuk.
Urutkan dari momen yang paling berpotensi viral.

Jawab HANYA dengan JSON berupa daftar objek dengan kunci:
"judul" (judul klip yang menarik, maksimal 60 karakter), "mulai_detik" (angka), "selesai_detik" (angka),
"alasan" (1 kalimat kenapa momen ini menarik).
Tulis "judul" dan "alasan" dalam bahasa yang sama dengan transkrip.

TRANSKRIP:
{transkrip}
"""


def parse_waktu(teks: str) -> float:
    bagian = teks.strip().split(":")
    if not 1 <= len(bagian) <= 3 or any(b.strip() == "" for b in bagian):
        raise ValueError(f"format waktu tidak dikenali: {teks!r}")
    detik = 0.0
    for b in bagian:
        detik = detik * 60 + float(b)
    return detik


def dari_teks_manual(teks: str, transkrip: Transkrip) -> list[Momen]:
    potongan = [p.strip() for p in re.split(r"[,;\n]+", teks) if p.strip()]
    if not potongan:
        raise KlipKilatError(f"Kolom timestamp_manual kosong. Contoh: {CONTOH_MANUAL}")
    daftar = []
    for i, p in enumerate(potongan, 1):
        try:
            awal, akhir = p.split("-")
            daftar.append(Momen(f"Klip {i}", parse_waktu(awal), parse_waktu(akhir), "Dipilih manual"))
        except ValueError:
            raise KlipKilatError(
                f"Format timestamp '{p}' tidak dikenali. Tulis mulai-selesai, dipisah koma. "
                f"Contoh: {CONTOH_MANUAL}"
            ) from None
    hasil = rapikan(daftar, transkrip, 0, 0, manual=True)
    if not hasil:
        raise KlipKilatError(
            f"Semua timestamp manual berada di luar durasi video ({format_jam(transkrip.durasi)}) "
            "atau tidak valid (mulai harus lebih kecil dari selesai)."
        )
    return hasil


def _segmen_awal(transkrip: Transkrip, t: float) -> Segmen | None:
    return next((s for s in transkrip.segmen if s.mulai <= t < s.selesai), None)


def _segmen_akhir(transkrip: Transkrip, t: float) -> Segmen | None:
    return next((s for s in transkrip.segmen if s.mulai < t <= s.selesai), None)


def _geser_awal(transkrip: Transkrip, t: float) -> float:
    s = _segmen_awal(transkrip, t)
    if s:
        return s.mulai
    berikutnya = [s.mulai for s in transkrip.segmen if s.mulai >= t]
    return min(berikutnya) if berikutnya else t


def _geser_akhir(transkrip: Transkrip, t: float) -> float:
    s = _segmen_akhir(transkrip, t)
    if s:
        return s.selesai
    sebelumnya = [s.selesai for s in transkrip.segmen if s.selesai <= t]
    return max(sebelumnya) if sebelumnya else t


def _potong_maks(transkrip: Transkrip, mulai: float, dmaks: float) -> float:
    batas = mulai + dmaks
    ujung = [s.selesai for s in transkrip.segmen if mulai < s.selesai <= batas]
    if not ujung:
        ujung = [k.selesai for k in transkrip.semua_kata() if mulai < k.selesai <= batas]
    return max(ujung) if ujung else batas


def _perpanjang_min(transkrip: Transkrip, mulai: float, selesai: float, dmin: float, dmaks: float) -> float:
    for s in sorted(transkrip.segmen, key=lambda s: s.mulai):
        if selesai - mulai >= dmin:
            break
        if s.selesai <= selesai:
            continue
        if s.selesai - mulai > dmaks:
            break
        selesai = s.selesai
    return selesai


def _bertumpuk(a: Momen, b: Momen) -> bool:
    return a.mulai < b.selesai and b.mulai < a.selesai


def rapikan(momen_list: list[Momen], transkrip: Transkrip, dmin: float, dmaks: float,
            manual: bool = False) -> list[Momen]:
    """Validasi momen dan geser titik potong ke batas kalimat (lihat spec bagian 3.3)."""
    hasil: list[Momen] = []
    for m in momen_list:
        mulai, selesai = max(0.0, m.mulai), min(transkrip.durasi, m.selesai)
        if mulai >= selesai:
            log.info("Momen dibuang (di luar durasi/terbalik): %s", m)
            continue
        mulai, selesai = _geser_awal(transkrip, mulai), _geser_akhir(transkrip, selesai)
        if mulai >= selesai:
            log.info("Momen dibuang (tidak berisi ucapan): %s", m)
            continue
        if not manual:
            if selesai - mulai > dmaks:
                selesai = _potong_maks(transkrip, mulai, dmaks)
            if selesai - mulai < dmin:
                selesai = _perpanjang_min(transkrip, mulai, selesai, dmin, dmaks)
        baru = Momen(m.judul, mulai, selesai, m.alasan)
        if not manual and any(_bertumpuk(baru, k) for k in hasil):
            log.info("Momen dibuang (bertumpuk): %s", m)
            continue
        hasil.append(baru)
    for m in hasil:
        m.mulai = round(max(0.0, m.mulai - PADDING), 3)
        m.selesai = round(min(transkrip.durasi, m.selesai + PADDING), 3)
    return hasil


def _format_transkrip(transkrip: Transkrip) -> str:
    return "\n".join(f"[{format_jam(s.mulai)}] {s.teks}" for s in transkrip.segmen)


def _ambil_json(teks: str) -> list:
    teks = re.sub(r"^```(?:json)?\s*|\s*```$", "", teks.strip())
    data = json.loads(teks)
    if isinstance(data, dict):
        data = next((v for v in data.values() if isinstance(v, list)), None)
    if not isinstance(data, list):
        raise ValueError("JSON bukan daftar momen")
    return data


def _ke_momen(item) -> Momen | None:
    try:
        return Momen(
            str(item.get("judul") or "Momen").strip()[:80],
            float(item["mulai_detik"]),
            float(item["selesai_detik"]),
            str(item.get("alasan") or "").strip(),
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def pilih_dengan_ai(transkrip: Transkrip, jumlah: int, dmin: float, dmaks: float,
                    panggil_llm: Callable[[str], str], judul_video: str = "") -> list[Momen]:
    prompt = PROMPT.format(judul=judul_video or "tanpa judul", jumlah=jumlah, dmin=int(dmin),
                           dmaks=int(dmaks), transkrip=_format_transkrip(transkrip))
    for percobaan in range(1, PERCOBAAN_AI + 1):
        jawaban = panggil_llm(prompt)
        try:
            data = _ambil_json(jawaban)
        except ValueError as e:
            log.warning("Percobaan %d: jawaban Gemini bukan JSON yang valid (%s): %.300s", percobaan, e, jawaban)
            continue
        kandidat = [m for m in (_ke_momen(x) for x in data) if m is not None]
        hasil = rapikan(kandidat, transkrip, dmin, dmaks)[:jumlah]
        if hasil:
            return hasil
        log.warning("Percobaan %d: tidak ada momen valid dari %d kandidat", percobaan, len(kandidat))
    raise GagalAI("format", f"AI tidak memberikan momen yang valid setelah {PERCOBAAN_AI} kali mencoba.")


def _klasifikasi_error(e: Exception) -> GagalAI:
    kode = getattr(e, "code", None)
    pesan = str(e)
    if kode == 429 or "RESOURCE_EXHAUSTED" in pesan:
        return GagalAI("kuota", "Kuota gratis API Gemini sedang habis. Coba lagi nanti atau besok.", pesan)
    if kode in (401, 403) or (kode == 400 and "API key" in pesan):
        return GagalAI("key", "API key Gemini tidak valid. Buat key baru di https://aistudio.google.com/apikey "
                              "lalu tempel ulang.", pesan)
    return GagalAI("lain", "Gagal menghubungi Gemini.", f"{type(e).__name__}: {pesan}")


def buat_klien_gemini(api_key: str, model: str = MODEL_GEMINI) -> Callable[[str], str]:
    def panggil(prompt: str) -> str:
        try:
            from google import genai
            from google.genai import types

            klien = genai.Client(api_key=api_key)
            respons = klien.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.4),
            )
            return respons.text or ""
        except Exception as e:
            raise _klasifikasi_error(e) from e

    return panggil
