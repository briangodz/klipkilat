"""Struktur data yang dipakai bersama oleh semua modul KlipKilat. Satuan waktu: detik."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Kata:
    teks: str
    mulai: float
    selesai: float


@dataclass
class Segmen:
    teks: str
    mulai: float
    selesai: float
    kata: list[Kata] = field(default_factory=list)


@dataclass
class Transkrip:
    bahasa: str
    durasi: float
    segmen: list[Segmen] = field(default_factory=list)

    def semua_kata(self) -> list[Kata]:
        return [k for s in self.segmen for k in s.kata]

    def ke_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def dari_dict(cls, data: dict) -> Transkrip:
        return cls(
            bahasa=data["bahasa"],
            durasi=data["durasi"],
            segmen=[
                Segmen(s["teks"], s["mulai"], s["selesai"], [Kata(**k) for k in s["kata"]])
                for s in data["segmen"]
            ],
        )


@dataclass
class Momen:
    judul: str
    mulai: float
    selesai: float
    alasan: str = ""

    @property
    def durasi(self) -> float:
        return self.selesai - self.mulai


@dataclass
class Video:
    path_video: Path
    path_audio: Path
    durasi: float
    judul: str


def format_jam(detik: float) -> str:
    total = int(round(detik))
    jam, sisa = divmod(total, 3600)
    menit, dtk = divmod(sisa, 60)
    return f"{jam:02d}:{menit:02d}:{dtk:02d}"
