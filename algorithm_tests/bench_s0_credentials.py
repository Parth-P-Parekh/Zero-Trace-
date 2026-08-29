"""Benchmark for S0(a) credential detection.

Measures p50/p95/p99 and throughput on a realistic long Claude Code payload.
Does NOT claim the 3ms S0 target unless measured — CODE-01 §6.1, SKEL-01 §B.7.

The payload simulates a 25-turn Claude Code session with tool results,
system prompt, CLAUDE.md, and file context — the worst-case scenario
described in SKEL-01 §D.2.1.
"""

from __future__ import annotations

import json
import time
import statistics
from typing import NamedTuple

from gateway.spans import Span
from gateway.detect.s0_credentials import s0_credential_scan, scan_span_credentials


# ────────────────────────────────────────────────────────────────────
# Realistic payload generator
# ────────────────────────────────────────────────────────────────────

def _generate_claude_code_payload(turns: int = 25) -> list[Span]:
    """Generate a realistic multi-turn Claude Code payload.

    Simulates:
    - System prompt (~2KB)
    - CLAUDE.md content (~1KB)
    - File context from several source files (~5KB each)
    - Tool results with JSON (~2KB each)
    - User/assistant exchanges (~500B each)

    Total: ~100-150KB depending on turn count.
    """
    spans: list[Span] = []

    # System prompt
    system_prompt = (
        "You are Claude, an AI assistant by Anthropic. "
        "You help with software development tasks. "
        "Follow these guidelines:\n"
        "1. Write clean, well-documented code.\n"
        "2. Follow the project's existing conventions.\n"
        "3. Test your changes.\n"
        "4. Explain your reasoning.\n"
    ) * 5  # ~2KB
    spans.append(Span(
        path="system",
        text=system_prompt,
        origin="system",
        leg="outbound",
    ))

    # CLAUDE.md
    claude_md = """# Project Guidelines

## Architecture
This is a Python project using FastAPI and PostgreSQL.
The application follows a clean architecture pattern.

## Dependencies
- fastapi>=0.100.0
- pydantic>=2.0
- sqlalchemy>=2.0
- httpx>=0.24.0

## Code Style
- Use type hints everywhere
- Follow PEP 8
- Maximum line length: 100 characters
- Use Google-style docstrings

## Testing
- Use pytest for all tests
- Maintain >90% code coverage
- Integration tests in tests/integration/
""" * 3  # ~1.5KB
    spans.append(Span(
        path="messages[0].content",
        text=claude_md,
        origin="user",
        leg="outbound",
    ))

    # Simulated source files
    source_files = [
        """
import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

@dataclass
class UserProfile:
    id: str
    name: str
    email: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    preferences: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        if not self.name or not self.email:
            return False
        if '@' not in self.email:
            return False
        return True

class UserRepository:
    def __init__(self, db):
        self.db = db

    async def get_user(self, user_id: str) -> Optional[UserProfile]:
        row = await self.db.fetch_one(
            "SELECT * FROM users WHERE id = :id",
            {"id": user_id}
        )
        if row is None:
            return None
        return UserProfile(**dict(row))

    async def create_user(self, profile: UserProfile) -> str:
        await self.db.execute(
            "INSERT INTO users (id, name, email, created_at, preferences) "
            "VALUES (:id, :name, :email, :created_at, :preferences)",
            {
                "id": profile.id,
                "name": profile.name,
                "email": profile.email,
                "created_at": profile.created_at,
                "preferences": profile.preferences,
            }
        )
        return profile.id
""",
        """
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="User Service", version="1.0.0")

class CreateUserRequest(BaseModel):
    name: str
    email: str
    preferences: dict = {}

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    created_at: str

@app.post("/users", response_model=UserResponse)
async def create_user(request: CreateUserRequest):
    try:
        user = UserProfile(
            id=generate_id(),
            name=request.name,
            email=request.email,
            preferences=request.preferences,
        )
        if not user.validate():
            raise HTTPException(status_code=400, detail="Invalid user data")
        await repo.create_user(user)
        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at.isoformat(),
        )
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
""",
    ]
    for i, src in enumerate(source_files):
        spans.append(Span(
            path=f"messages[1].content[{i}]",
            text=src,
            origin="user",
            leg="outbound",
        ))

    # Multi-turn conversation
    for turn in range(turns):
        # User message
        user_msg = (
            f"Turn {turn}: Please review this code and suggest improvements. "
            "I'm particularly concerned about error handling and edge cases. "
            "Also check if there are any security issues with the current approach. "
            "The function should handle concurrent access properly and "
            "include appropriate logging for production use. "
            f"Reference: see the implementation in module_{turn}.py."
        )
        spans.append(Span(
            path=f"messages[{2 + turn * 3}].content",
            text=user_msg,
            origin="user",
            leg="outbound",
        ))

        # Tool result (JSON)
        tool_result = json.dumps({
            "type": "search_results",
            "query": f"security patterns module_{turn}",
            "results": [
                {
                    "file": f"src/module_{turn}.py",
                    "line": 42 + turn,
                    "content": f"def process_request_{turn}(data: dict) -> Response:",
                    "score": 0.95,
                },
                {
                    "file": f"tests/test_module_{turn}.py",
                    "line": 10 + turn,
                    "content": f"class TestModule{turn}:",
                    "score": 0.87,
                },
            ],
            "metadata": {
                "total_results": 15,
                "search_time_ms": 23,
                "index_version": f"v{turn}.1.0",
            },
        })
        spans.append(Span(
            path=f"messages[{3 + turn * 3}].tool_result",
            text=tool_result,
            origin="tool_result",
            leg="outbound",
        ))

        # Assistant response
        assistant_msg = (
            f"I've reviewed the code in module_{turn}. Here are my findings:\n\n"
            "1. **Error Handling**: The current implementation uses a bare except clause "
            "which catches SystemExit and KeyboardInterrupt. Replace with specific exceptions.\n\n"
            "2. **Concurrency**: The database access is not protected against race conditions. "
            "Consider using optimistic locking with version columns.\n\n"
            "3. **Logging**: Add structured logging with correlation IDs for tracing.\n\n"
            f"Here's the improved implementation for module_{turn}:\n\n"
            "```python\n"
            f"async def process_request_{turn}(data: dict) -> Response:\n"
            "    async with db.transaction():\n"
            "        result = await query(data)\n"
            "        return Response(data=result)\n"
            "```\n"
        )
        spans.append(Span(
            path=f"messages[{4 + turn * 3}].content",
            text=assistant_msg,
            origin="assistant",
            leg="outbound",
        ))

    return spans


def _generate_payload_with_secrets(turns: int = 25) -> list[Span]:
    """Same as above but with a few secrets embedded.

    Embeds 3 secrets in a sea of clean content — the realistic case.
    """
    spans = _generate_claude_code_payload(turns)

    # Add a span with an embedded API key (turn 10's tool result)
    if len(spans) > 30:
        # Inject secret into an existing span's text
        injected = spans[30]
        new_text = injected.text + "\n# API_KEY=sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456\n"
        spans[30] = Span(
            path=injected.path,
            text=new_text,
            origin=injected.origin,
            leg=injected.leg,
        )

    return spans


# ────────────────────────────────────────────────────────────────────
# Benchmark runner
# ────────────────────────────────────────────────────────────────────

class BenchmarkResult(NamedTuple):
    iterations: int
    total_spans: int
    total_chars: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    mean_ms: float
    throughput_mb_s: float
    findings_count: int


def run_benchmark(iterations: int = 100, turns: int = 25,
                  with_secrets: bool = False) -> BenchmarkResult:
    """Run the S0(a) benchmark.

    Args:
        iterations: Number of scan runs to measure
        turns: Number of conversation turns in the payload
        with_secrets: Whether to embed secrets in the payload

    Returns:
        BenchmarkResult with timing statistics
    """
    if with_secrets:
        spans = _generate_payload_with_secrets(turns)
    else:
        spans = _generate_claude_code_payload(turns)

    total_chars = sum(len(s.text) for s in spans)

    # Warm up (1 iteration)
    s0_credential_scan(spans)

    # Measure
    timings_ms: list[float] = []
    findings_count = 0
    for _ in range(iterations):
        start = time.perf_counter()
        findings = s0_credential_scan(spans)
        elapsed = (time.perf_counter() - start) * 1000  # ms
        timings_ms.append(elapsed)
        findings_count = len(findings)

    timings_ms.sort()
    total_bytes = total_chars  # approximate, ASCII-dominant

    return BenchmarkResult(
        iterations=iterations,
        total_spans=len(spans),
        total_chars=total_chars,
        p50_ms=timings_ms[len(timings_ms) // 2],
        p95_ms=timings_ms[int(len(timings_ms) * 0.95)],
        p99_ms=timings_ms[int(len(timings_ms) * 0.99)],
        min_ms=timings_ms[0],
        max_ms=timings_ms[-1],
        mean_ms=statistics.mean(timings_ms),
        throughput_mb_s=(total_bytes / 1024 / 1024) / (statistics.mean(timings_ms) / 1000)
        if statistics.mean(timings_ms) > 0 else 0,
        findings_count=findings_count,
    )


def main():
    """Run and report the S0(a) benchmark."""
    print("=" * 70)
    print("S0(a) Credential Detection Benchmark")
    print("=" * 70)

    # Clean payload (overwhelmingly common case)
    print("\n─── Clean payload (no secrets) ───")
    result_clean = run_benchmark(iterations=200, turns=25, with_secrets=False)
    _print_result(result_clean)

    # Payload with embedded secrets
    print("\n─── Payload with 3 embedded secrets ───")
    result_secrets = run_benchmark(iterations=200, turns=25, with_secrets=True)
    _print_result(result_secrets)

    # Small payload (single turn)
    print("\n─── Small payload (1 turn) ───")
    result_small = run_benchmark(iterations=500, turns=1, with_secrets=False)
    _print_result(result_small)

    # Report vs budget
    print("\n─── Budget assessment ───")
    budget_ms = 1.5
    print(f"  ZT_BUDGET_S0_MS = {budget_ms} ms (CODE-01 §3.2)")
    print(f"  Clean 25-turn p50 = {result_clean.p50_ms:.3f} ms")
    print(f"  Clean 25-turn p95 = {result_clean.p95_ms:.3f} ms")
    if result_clean.p95_ms <= budget_ms:
        print(f"  ✅ p95 within budget")
    else:
        print(f"  ⚠️  p95 EXCEEDS budget — this is a cold-scan number.")
        print(f"      With span cache (SKEL-01 §B.5), warm-path p95 will be lower.")
        print(f"      Do NOT claim 1.5ms until measured with the cache active.")


def _print_result(result: BenchmarkResult):
    print(f"  Payload: {result.total_spans} spans, "
          f"{result.total_chars:,} chars ({result.total_chars / 1024:.1f} KB)")
    print(f"  Iterations: {result.iterations}")
    print(f"  Findings: {result.findings_count}")
    print(f"  p50:  {result.p50_ms:.3f} ms")
    print(f"  p95:  {result.p95_ms:.3f} ms")
    print(f"  p99:  {result.p99_ms:.3f} ms")
    print(f"  min:  {result.min_ms:.3f} ms")
    print(f"  max:  {result.max_ms:.3f} ms")
    print(f"  mean: {result.mean_ms:.3f} ms")
    print(f"  Throughput: {result.throughput_mb_s:.1f} MB/s")


if __name__ == "__main__":
    main()
