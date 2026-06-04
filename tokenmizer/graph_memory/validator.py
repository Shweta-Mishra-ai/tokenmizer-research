"""
GraphValidator — confidence scoring and noise rejection.
Equation (5) from the paper.
"""
from __future__ import annotations
import re


class GraphValidator:
    """
    Scores candidate nodes before graph insertion.
    Rejects nodes with confidence < min_confidence.
    """
    def __init__(self, min_confidence: float = 0.50):
        self.min_confidence = min_confidence
        self._file_pat  = re.compile(r'[\w./\-]+\.(?:py|js|ts|go|rs|tf|yaml|json|md)')
        self._url_pat   = re.compile(r'https?://')
        self._ver_pat   = re.compile(r'\d+\.\d+')
        self._verb_only = re.compile(r'^(?:fix|add|run|set|use|get|put|make|do|try)$', re.I)

    def score(self, node) -> float:
        label = node.label or ""
        kappa = 0.50
        if self._file_pat.search(label):  kappa += 0.20
        if len(label) > 15:               kappa += 0.10
        if self._ver_pat.search(label):   kappa += 0.10
        if len(label) < 8:                kappa -= 0.20
        if self._verb_only.match(label.strip()): kappa -= 0.40
        if self._url_pat.search(label):
            from ..graph_memory.graph import NodeType
            node.type = NodeType.API
        return round(max(0.0, min(1.0, kappa)), 3)
