import dataclasses
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
