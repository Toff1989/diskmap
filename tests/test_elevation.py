import sys

import pytest

from diskmap import __main__ as entry
from diskmap import elevation


def test_is_admin_returns_bool():
    assert isinstance(elevation.is_admin(), bool)


def test_build_command_forwards_arguments_and_quotes_spaces():
    exe, params = elevation.build_command([r"C:\Mes Dossiers\x"], executable=r"C:\Py\python.exe")
    assert exe == r"C:\Py\python.exe"
    assert params == '-m diskmap "C:\\Mes Dossiers\\x"'


def test_build_command_without_path():
    _, params = elevation.build_command([], executable="python.exe")
    assert params == "-m diskmap"


def test_build_command_frozen_relaunches_the_exe_directly(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    exe, params = elevation.build_command(["F:\\"], executable=r"C:\App\DiskMap.exe")
    assert exe == r"C:\App\DiskMap.exe"
    assert params == "F:\\"  # pas de « -m diskmap » dans un exécutable PyInstaller


def test_relaunch_is_noop_off_windows(monkeypatch):
    monkeypatch.setattr(elevation.os, "name", "posix")
    assert elevation.relaunch_as_admin([]) is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows uniquement")
def test_relaunch_reports_uac_refusal(monkeypatch):
    import ctypes
    calls = []

    class FakeShell:
        @staticmethod
        def ShellExecuteW(*args):
            calls.append(args)
            return 5  # accès refusé : l'utilisateur a annulé l'UAC

    monkeypatch.setattr(ctypes.windll, "shell32", FakeShell, raising=False)
    assert elevation.relaunch_as_admin(["F:\\"]) is False
    assert calls[0][1] == "runas"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows uniquement")
def test_main_does_not_start_gui_when_relaunched(monkeypatch):
    monkeypatch.setattr(entry, "is_admin", lambda: False)
    monkeypatch.setattr(entry, "relaunch_as_admin", lambda args: True)
    entry.main([])  # doit simplement rendre la main, sans ouvrir de fenêtre
