"""Span extraction and the byte-splice serialiser."""
from .jsonspan import MalformedJSON, extract_spans
from .model import (
    Edit, OverlappingEdits, Span, SpanNotFound, SpanOffsetError, SpanTree,
)

__all__ = [
    "Edit", "MalformedJSON", "OverlappingEdits", "Span", "SpanNotFound",
    "SpanOffsetError", "SpanTree", "extract_spans",
]
