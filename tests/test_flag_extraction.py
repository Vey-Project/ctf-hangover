"""Unit tests for flag/answer extraction — no Docker or 9Router needed.

Run:  .venv/bin/python -m pytest tests/ -q
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ctf_hangover.solver.core import find_flag, find_all_flags


class TestBraceFormats(unittest.TestCase):
    def test_ca_full_prefix(self):
        for text, want in [
            ("flag found: FLAG_CTF_CA{abc123}", "FLAG_CTF_CA{abc123}"),
            ("The flag is CA_FLAG_CTF{deadbeef}", "CA_FLAG_CTF{deadbeef}"),
            ("submit CA_Flag_Ctf{87cd8ba2649d32ca0ff1883b9281b93c}", "CA_Flag_Ctf{87cd8ba2649d32ca0ff1883b9281b93c}"),
            ("value = CA_Flag_CTF{x}", "CA_Flag_CTF{x}"),
        ]:
            assert find_flag(text) == want, text

    def test_classic_brace(self):
        assert find_flag("flag{integration_test_ok}") == "flag{integration_test_ok}"
        assert find_flag("FLAG{af412cf6226605f9365a5849da8d91ec}") == "FLAG{af412cf6226605f9365a5849da8d91ec}"
        # prefix must NOT be truncated to inner CTF{...}
        m = find_flag("CA_FLAG_CTF{deadbeef}")
        assert m is not None and "CA_FLAG_CTF" in m


class TestAnswerFormats(unittest.TestCase):
    def test_md5_sha1_sha256(self):
        assert find_flag("flag = 912ec803b2ce49e4a541068d495ab570") == "912ec803b2ce49e4a541068d495ab570"
        assert find_flag("1a365806c1753eab28645236afc0f56e") == "1a365806c1753eab28645236afc0f56e"
        assert find_flag("2fa046e99d195a96120bf83ef611ab6e05ceb1aa8c37c0e240085ee64a9d2fcc") == "2fa046e99d195a96120bf83ef611ab6e05ceb1aa8c37c0e240085ee64a9d2fcc"

    def test_timestamp(self):
        assert find_flag("answer: Nov 18, 2025 @ 15:09:53.000") == "Nov 18, 2025 @ 15:09:53.000"
        assert find_flag("exec at Nov 23, 2025 @ 10:28:11.874") == "Nov 23, 2025 @ 10:28:11.874"

    def test_cve(self):
        assert find_flag("vuln CVE-2021-43798 LFI") == "CVE-2021-43798"
        assert find_flag("CVE-2018-15473") == "CVE-2018-15473"

    def test_pipe_joined(self):
        assert find_flag("ppid|pid = 3204|5192") == "3204|5192"
        assert find_flag("ids 17|18") == "17|18"

    def test_url_wrapper(self):
        assert find_flag("path is @url:http://10.10.0.104") == "@url:http://10.10.0.104"

    def test_filename_with_extension(self):
        assert find_flag("initial access: cs2cheat (1).exe") == "cs2cheat (1).exe"
        assert find_flag("the file enc-nyan.ps1 started it") == "enc-nyan.ps1"
        assert find_flag("uploaded nyan.html") == "nyan.html"

    def test_windows_path(self):
        assert find_flag("dir: C:\\Users\\victim\\Downloads") == "C:\\Users\\victim\\Downloads"
        assert find_flag("C:\\Users\\Victim\\Documents") == "C:\\Users\\Victim\\Documents"

    def test_negative(self):
        assert find_flag("no flag here, just prose") is None
        assert find_flag("run ls -la and whoami") is None
        # bare words with a dot but no plausible answer shape
        assert find_flag("version 2.4.38") is None


class TestAllFlags(unittest.TestCase):
    def test_find_all_multiple(self):
        text = (
            "decoy 912ec803b2ce49e4a541068d495ab570 then real "
            "1a365806c1753eab28645236afc0f56e and CVE-2021-43798"
        )
        got = find_all_flags(text)
        assert "912ec803b2ce49e4a541068d495ab570" in got
        assert "1a365806c1753eab28645236afc0f56e" in got
        assert "CVE-2021-43798" in got

    def test_all_flags_returns_unique(self):
        got = find_all_flags("a 1a365806c1753eab28645236afc0f56e b 1a365806c1753eab28645236afc0f56e")
        assert got == ["1a365806c1753eab28645236afc0f56e"]

    def test_noise_filenames_excluded(self):
        # Common filenames in prose must NOT be treated as answers by
        # find_all_flags (the coordinator-facing candidate extractor).
        # (find_flag single-match is intentionally noise-unaware — it is only
        # used to grab the first plausible token from a solver's final text.)
        text = "found index.html and config.php, uploaded backup.zip, login page at login.php"
        got = find_all_flags(text)
        assert got == [], f"expected no noise matches, got {got}"

    def test_windows_path_no_partial_match(self):
        # "C:\Users\My Folder" must not match the partial "C:\Users\My".
        assert find_flag("C:\\Users\\My Folder\\x") is None
        # Real directory answers still match.
        assert find_flag("dir C:\\Users\\victim\\Downloads") == "C:\\Users\\victim\\Downloads"
        assert find_flag("C:\\Users\\Victim\\Documents") == "C:\\Users\\Victim\\Documents"


if __name__ == "__main__":
    # Allow running without pytest:  python tests/test_flag_extraction.py
    unittest.main()
