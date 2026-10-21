"""Formatage des tailles."""
from __future__ import annotations

_UNITS = ("o", "Ko", "Mo", "Go", "To")


def human_size(b: float) -> str:
    """1536 -> '1.5 Ko'."""
    for unit in _UNITS:
        if b < 1024 or unit == _UNITS[-1]:
            return "%d o" % b if unit == "o" else "%.1f %s" % (b, unit)
        b /= 1024.0
    return ""  # inatteignable


def signed_size(b: float) -> str:
    """1536 -> '+1.5 Ko', -2048 -> '-2.0 Ko', 0 -> '0 o'."""
    if b == 0:
        return "0 o"
    return ("+" if b > 0 else "-") + human_size(abs(b))
