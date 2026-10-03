"""Menentukan momen yang dijadikan klip: dari timestamp manual atau dari Gemini."""
from __future__ import annotations

import logging
import re

from .kesalahan import KlipKilatError
from .model import Momen, Segmen, Transkrip, format_jam

log = logging.getLogger("klipkilat")

PADDING = 0.3
CONTOH_MANUAL = "01:23:10-01:24:00, 02:05:00-02:05:45"


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
