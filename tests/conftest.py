import shutil
import subprocess

import pytest

from klipkilat.model import Kata, Segmen, Transkrip


def _buat_video(path, dengan_audio=True, detik=10):
    args = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size=1280x720:rate=30:duration={detik}"]
    if dengan_audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={detik}"]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if dengan_audio:
        args += ["-c:a", "aac", "-shortest"]
    args.append(str(path))
    subprocess.run(args, check=True, capture_output=True)
    return path


@pytest.fixture(scope="session")
def perlu_ffmpeg():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe tidak terpasang")


@pytest.fixture(scope="session")
def video_sintetis(perlu_ffmpeg, tmp_path_factory):
    return _buat_video(tmp_path_factory.mktemp("media") / "sintetis.mp4")


@pytest.fixture(scope="session")
def video_bisu(perlu_ffmpeg, tmp_path_factory):
    return _buat_video(tmp_path_factory.mktemp("media") / "bisu.mp4", dengan_audio=False)


def buat_transkrip_uji(kalimat, durasi=None, bahasa="id"):
    """kalimat: daftar (mulai, selesai, teks). Waktu kata dibagi rata di dalam segmen."""
    segmen = []
    for mulai, selesai, teks in kalimat:
        kata_teks = teks.split()
        langkah = (selesai - mulai) / len(kata_teks)
        kata = [
            Kata(t, round(mulai + i * langkah, 3), round(mulai + (i + 1) * langkah, 3))
            for i, t in enumerate(kata_teks)
        ]
        segmen.append(Segmen(teks, float(mulai), float(selesai), kata))
    if durasi is None:
        durasi = kalimat[-1][1] if kalimat else 0.0
    return Transkrip(bahasa, float(durasi), segmen)


@pytest.fixture
def buat_tr():
    return buat_transkrip_uji
