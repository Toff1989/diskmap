"""Logique métier indépendante de l'interface (testable sans tkinter)."""
from .drives import detect_drives
from .formatting import human_size
from .explain import REASON_LABEL, explain
from .models import Node, ScanResult, SkipEntry
from .scanner import Scanner, ScanCancelled
from .treemap import squarify

__all__ = ["Node", "ScanResult", "SkipEntry", "Scanner", "ScanCancelled", "squarify",
           "detect_drives", "human_size", "explain", "REASON_LABEL"]
