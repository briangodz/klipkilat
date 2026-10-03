"""Membuat subtitle gaya TikTok (.ass, kata aktif di-highlight) dan .srt untuk satu klip."""
from __future__ import annotations

from .model import Kata, Momen, Transkrip

MAKS_KATA = 3
LEBAR, TINGGI = 1080, 1920
POS_X, POS_Y = LEBAR // 2, int(TINGGI * 0.7)
KUNING = "&H00FFFF&"
PUTIH = "&HFFFFFF&"

HEADER_ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: {lebar}
PlayResY: {tinggi}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def kelompokkan(transkrip: Transkrip, momen: Momen) -> list[list[Kata]]:
    grup = []
    for s in transkrip.segmen:
        kata = [k for k in s.kata if k.selesai > momen.mulai and k.mulai < momen.selesai]
        for i in range(0, len(kata), MAKS_KATA):
            grup.append(kata[i:i + MAKS_KATA])
    return grup


def _relatif(t: float, momen: Momen) -> float:
    return min(max(t - momen.mulai, 0.0), momen.durasi)


def _waktu_ass(t: float) -> str:
    cs = round(t * 100)
    jam, sisa = divmod(cs, 360000)
    menit, sisa = divmod(sisa, 6000)
    detik, centi = divmod(sisa, 100)
    return f"{jam}:{menit:02d}:{detik:02d}.{centi:02d}"


def _waktu_srt(t: float) -> str:
    ms = round(t * 1000)
    jam, sisa = divmod(ms, 3600000)
    menit, sisa = divmod(sisa, 60000)
    detik, milidetik = divmod(sisa, 1000)
    return f"{jam:02d}:{menit:02d}:{detik:02d},{milidetik:03d}"


def _bersihkan(teks: str) -> str:
    return teks.replace("\\", "/").replace("{", "(").replace("}", ")")


def buat_ass(transkrip: Transkrip, momen: Momen, nama_font: str = "Montserrat ExtraBold") -> str:
    baris = []
    for grup in kelompokkan(transkrip, momen):
        for i, aktif in enumerate(grup):
            mulai = _relatif(aktif.mulai, momen)
            akhir = grup[i + 1].mulai if i + 1 < len(grup) else aktif.selesai
            selesai = _relatif(akhir, momen)
            if selesai <= mulai:
                continue
            teks = " ".join(
                f"{{\\c{KUNING}}}{_bersihkan(k.teks)}{{\\c{PUTIH}}}" if k is aktif else _bersihkan(k.teks)
                for k in grup
            )
            baris.append(
                f"Dialogue: 0,{_waktu_ass(mulai)},{_waktu_ass(selesai)},Default,,0,0,0,,"
                f"{{\\pos({POS_X},{POS_Y})}}{teks}"
            )
    return HEADER_ASS.format(lebar=LEBAR, tinggi=TINGGI, font=nama_font) + "\n".join(baris) + "\n"


def buat_srt(transkrip: Transkrip, momen: Momen) -> str:
    entri = []
    for grup in kelompokkan(transkrip, momen):
        mulai, selesai = _relatif(grup[0].mulai, momen), _relatif(grup[-1].selesai, momen)
        if selesai <= mulai:
            continue
        teks = " ".join(k.teks for k in grup)
        entri.append(f"{len(entri) + 1}\n{_waktu_srt(mulai)} --> {_waktu_srt(selesai)}\n{teks}\n")
    return "\n".join(entri)
