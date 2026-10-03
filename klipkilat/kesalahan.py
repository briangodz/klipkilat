"""Jenis error KlipKilat. pesan_pengguna ditampilkan ke pengguna, detail_teknis hanya ke log."""


class KlipKilatError(Exception):
    def __init__(self, pesan_pengguna: str, detail_teknis: str = ""):
        super().__init__(pesan_pengguna)
        self.pesan_pengguna = pesan_pengguna
        self.detail_teknis = detail_teknis


class GagalAI(KlipKilatError):
    """Gagal memakai Gemini. jenis: 'key', 'kuota', 'sibuk', 'model', 'format', atau 'lain'."""

    def __init__(self, jenis: str, pesan_pengguna: str, detail_teknis: str = ""):
        super().__init__(pesan_pengguna, detail_teknis)
        self.jenis = jenis
