"""Logique métier indépendante de l'interface (testable sans tkinter)."""
from .age import BUCKETS, age_bucket
from .cleanup import ColdEntry, Finding, Rule, classify, find_cleanup, find_cold
from .diff import diff_trees, growth_map
from .drives import detect_drives
from .duplicates import DupGroup, DupResult, DuplicateFinder
from .explain import REASON_LABEL, explain
from .export import export_html
from .formatting import human_size, signed_size
from .models import Node, ScanResult, SkipEntry
from .projects import ProjectInfo, find_projects
from .scanner import Scanner, ScanCancelled
from .removal import Outcome, Plan, Remover, plan_removal
from .snapshot import SnapshotInfo, list_snapshots, load_snapshot, save_snapshot
from .tree import find_chain, join, walk
from .treemap import squarify

__all__ = ["Node", "ScanResult", "SkipEntry", "Scanner", "ScanCancelled", "squarify",
           "detect_drives", "human_size", "signed_size", "explain", "REASON_LABEL",
           "BUCKETS", "age_bucket", "ColdEntry", "Finding", "Rule", "classify", "find_cleanup",
           "find_cold", "diff_trees", "growth_map", "DupGroup", "DupResult", "DuplicateFinder",
           "export_html", "ProjectInfo", "find_projects", "SnapshotInfo", "list_snapshots",
           "load_snapshot", "save_snapshot", "find_chain", "join", "walk",
           "Outcome", "Plan", "Remover", "plan_removal"]
