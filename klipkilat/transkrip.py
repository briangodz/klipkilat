"""Mengubah audio menjadi transkrip dengan timestamp per kata (faster-whisper)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

from .kesalahan import KlipKilatError
from .model import Kata, Segmen, Transkrip, Video

log = logging.getLogger("klipkilat")

MIN_KATA = 20
PESAN_SEDIKIT_UCAPAN = (
    "Video ini tidak berisi ucapan yang cukup untuk ditranskrip (mungkin hanya musik atau hening)."
)


def deteksi_perangkat() -> str:
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def pilih_model(perangkat: str) -> tuple[str, str]:
    return ("large-v3", "float16") if perangkat == "cuda" else ("small", "int8")


def _hash_file(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def simpan(tr: Transkrip, path: Path) -> None:
    path = Path(path)
    sementara = path.with_suffix(path.suffix + ".tmp")
    sementara.write_text(json.dumps(tr.ke_dict(), ensure_ascii=False), encoding="utf-8")
    os.replace(sementara, path)


def muat(path: Path) -> Transkrip:
    return Transkrip.dari_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _whisper(audio: Path, bahasa: str, perangkat: str, nama_model: str, compute_type: str) -> Transkrip:
    from faster_whisper import WhisperModel

    model = WhisperModel(nama_model, device=perangkat, compute_type=compute_type)
    hasil, info = model.transcribe(
        str(audio),
        language=None if bahasa == "auto" else bahasa,
        word_timestamps=True,
        vad_filter=True,
    )
    segmen = []
    for s in hasil:
        kata = [Kata(w.word.strip(), float(w.start), float(w.end)) for w in (s.words or []) if w.word.strip()]
        if kata:
            segmen.append(Segmen(s.text.strip(), float(s.start), float(s.end), kata))
    return Transkrip(info.language, float(info.duration), segmen)


def buat_transkrip(video: Video, bahasa: str, perangkat: str, folder_kerja: Path,
                   nama_model: str | None = None, transkriptor=None) -> Transkrip:
    model_bawaan, compute_type = pilih_model(perangkat)
    nama_model = nama_model or model_bawaan
    kunci = f"{_hash_file(video.path_audio)[:12]}_{bahasa}_{nama_model}"
    cache = Path(folder_kerja) / f"transkrip_{kunci}.json"
    if cache.exists():
        try:
            tr = muat(cache)
        except (ValueError, KeyError, TypeError) as e:
            log.warning("Transkrip tersimpan rusak, dibuat ulang: %s (%r)", cache.name, e)
            cache.unlink(missing_ok=True)
        else:
            log.info("Memakai transkrip tersimpan: %s", cache.name)
            return tr

    log.info("Transkrip dengan model %s di %s", nama_model, perangkat)
    try:
        tr = (transkriptor or _whisper)(video.path_audio, bahasa, perangkat, nama_model, compute_type)
    except KlipKilatError:
        raise
    except Exception as e:
        raise KlipKilatError(
            "Gagal membuat transkrip. Coba Runtime → Restart session, lalu jalankan ulang semua sel.",
            repr(e),
        ) from e

    jumlah_kata = len(tr.semua_kata())
    if jumlah_kata < MIN_KATA:
        raise KlipKilatError(PESAN_SEDIKIT_UCAPAN, f"jumlah kata: {jumlah_kata}")
    simpan(tr, cache)
    return tr
