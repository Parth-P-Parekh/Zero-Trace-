"""Reading the hook event off stdin, on a platform that will not send it cleanly.

Both hooks used to do this:

    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print("zerotrace: could not parse hook input; allowing", file=sys.stderr)
        sys.exit(0)

Two bugs in five lines, and together they switched the product off on Windows without
anyone noticing.

**The decoding.** PowerShell 5.1 does not hand a native process the bytes you piped into
it. It re-encodes the pipeline through the console output encoding, which on a default
Windows install means UTF-16LE or ANSI, usually with a BOM. `json.load(sys.stdin)` then
sees `\\xff\\xfe{\\x00"\\x00s...` and raises. Measured directly: the identical hook command
blocks a credential when `cmd.exe` redirects a file into it, and fails to parse when
PowerShell pipes the same bytes.

**The failure posture.** On that parse error the hook exited 0, which means *allow*. So a
guard that could not read its input waved the request through, printed one line to a
stderr nobody reads, and left `zerotrace status` reporting both hooks healthy. "I could
not read the question" is not "the answer is yes" -- least of all here.

So: decode defensively, and if the event genuinely cannot be read, honour `ZT_FAIL`, which
defaults to closed like every other failure path in this product.
"""

from __future__ import annotations

import json
import os
import sys

#: Tried in order. `utf-8` first because it is what every well-behaved caller sends;
#: `utf-8-sig` and the UTF-16 variants are the shapes PowerShell produces.
ENCODINGS = ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "latin-1")


def decode(raw: bytes) -> str:
    """Text from whatever the shell handed us, or "" when nothing works.

    `latin-1` is last and never fails, which is deliberate: it turns an undecodable byte
    string into text that will then fail *JSON* parsing with a clear error, rather than
    raising a UnicodeDecodeError from somewhere further up that reads as a crash.
    """
    if not raw:
        return ""
    # A UTF-16 BOM is the common PowerShell case and worth checking before guessing.
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    for encoding in ENCODINGS:
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        # PowerShell's UTF-16 sometimes survives a utf-8 decode as text riddled with
        # NULs. That decodes "successfully" and then fails to parse, so strip them.
        text = text.replace("\x00", "").lstrip("﻿").strip()
        if text.startswith("{"):
            return text
    return raw.decode("latin-1", "replace").replace("\x00", "").strip()


def read_event(deny) -> dict:
    """The hook event, or a decision. Never returns something unusable.

    `deny` is the caller's own refusal function, so the message reaches the harness in
    whatever shape that host expects -- the two hooks differ, and this module has no
    business knowing which one it is talking to.
    """
    try:
        raw = sys.stdin.buffer.read()
    except (AttributeError, ValueError):
        # No buffer (a test harness swapped stdin for StringIO); fall back to text.
        raw = (sys.stdin.read() or "").encode("utf-8", "replace")

    text = decode(raw)
    if text:
        try:
            event = json.loads(text)
            if isinstance(event, dict):
                return event
        except ValueError:
            pass

    if os.environ.get("ZT_FAIL", "closed").lower() == "open":
        print("zerotrace: could not parse hook input; allowing because ZT_FAIL=open",
              file=sys.stderr)
        sys.exit(0)

    deny(
        "ZeroTrace could not read this hook event, so it could not check the request. "
        "Nothing was sent. This is a ZeroTrace bug or a harness that delivered stdin in "
        "an unexpected encoding -- not a problem with what you typed. Set ZT_FAIL=open "
        "to proceed unprotected."
    )
    raise SystemExit(2)  # unreachable; deny() exits, and this satisfies the type checker
