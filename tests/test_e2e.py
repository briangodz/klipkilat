"""Uji alur lengkap dengan Whisper sungguhan. Jalankan:
KLIPKILAT_VIDEO_E2E=tests/data/e2e.mp4 pytest -m e2e -v
"""
import os
import zipfile

import pytest

from klipkilat import proses
from klipkilat.pipeline import Pengaturan, jalankan


@pytest.mark.e2e
def test_alur_lengkap(tmp_path):
    video = os.environ.get("KLIPKILAT_VIDEO_E2E")
    if not video:
        pytest.skip("Set KLIPKILAT_VIDEO_E2E ke path video berisi ucapan")
    hasil = jalankan(Pengaturan(
        sumber=video,
        folder_kerja=tmp_path / "kerja",
        bahasa=os.environ.get("KLIPKILAT_BAHASA_E2E", "en"),
        timestamp_manual="00:00-00:12",
        model_whisper="tiny",
    ))
    assert len(hasil.klip_berhasil) == 1
    klip = hasil.klip_berhasil[0]
    assert proses.ukuran_video(klip) == (1080, 1920)
    assert proses.punya_audio(klip)
    with zipfile.ZipFile(hasil.path_zip) as z:
        srt = z.read("klip_01.srt").decode("utf-8").lower()
    assert "test" in srt
