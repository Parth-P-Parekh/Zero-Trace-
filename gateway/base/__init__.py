"""Part B base classes. Subclass `Detector`; everything else is already wired."""
from .budget import BudgetExceeded, Deadline, ScanLimits, ScanTooLarge, StageTimer
from .cache import InMemorySpanCache, NullSpanCache, SpanCache, cache_key
from .checker import Checker, CheckerConfig
from .detector import Detector, DetectorDefinitionError, Match
from .policy import StubPolicyClient
from .scanner import DetectorPack, EngineUnavailable, assert_production_engines

__all__ = [
    "BudgetExceeded", "Deadline", "ScanLimits", "ScanTooLarge", "StageTimer",
    "InMemorySpanCache", "NullSpanCache", "SpanCache", "cache_key",
    "Checker", "CheckerConfig", "Detector", "DetectorDefinitionError", "Match",
    "StubPolicyClient", "DetectorPack", "EngineUnavailable",
    "assert_production_engines",
]
