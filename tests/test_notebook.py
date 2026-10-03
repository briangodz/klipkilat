import dataclasses
import importlib.util
import json
from pathlib import Path

from klipkilat.pipeline import Pengaturan

NOTEBOOK = Path(__file__).resolve().parents[1] / "KlipKilat.ipynb"


def _nb():
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def _kode(nb):
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def test_notebook_meminta_gpu():
    assert _nb()["metadata"]["accelerator"] == "GPU"


def test_sel_kode_valid_python():
    kode = _kode(_nb())
    assert len(kode) == 2
    for sumber in kode:
        tanpa_shell = "\n".join(b for b in sumber.splitlines() if not b.lstrip().startswith("!"))
        compile(tanpa_shell, "sel", "exec")


def test_semua_pengaturan_diteruskan():
    sel_pengaturan = _kode(_nb())[1]
    for f in dataclasses.fields(Pengaturan):
        if f.name != "model_whisper":
            assert f"{f.name}=" in sel_pengaturan, f.name


def test_menginstal_dari_repo_ini():
    assert "git+https://github.com/briangodz/klipkilat" in _kode(_nb())[0]


def test_notebook_sesuai_script_pembuatnya():
    path = NOTEBOOK.parent / "scripts" / "buat_notebook.py"
    spec = importlib.util.spec_from_file_location("buat_notebook", path)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert modul.buat_notebook() == _nb(), "Jalankan ulang: python scripts/buat_notebook.py"


def test_unduhan_didahulukan_dan_drive_tidak_membuat_traceback():
    sel = _kode(_nb())[1]
    assert sel.index("files.download(") < sel.index("shutil.copy(hasil.path_zip")
    assert "Google Drive tidak bisa dihubungkan" in sel
    assert "Unduhan otomatis gagal" in sel
    assert "Video tersimpan di" in sel
