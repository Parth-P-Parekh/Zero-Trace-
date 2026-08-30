#!/usr/bin/env python3
"""Print the throwaway credential used in Act 1 of the judge demo.

This exists because ZeroTrace refused, five separate times, to let its own demo materials
be written with a complete key in them -- and then refused again when the key was split in
half, because half of an Anthropic key is still recognisably an Anthropic key. The product
was right every time, so the value is assembled at run time and never stored.

That refusal is worth saying out loud at Step 1. A security tool that inconveniences its
own authors, on its own repository, before it has inconvenienced a single customer, is
making a more credible claim than any slide.

    python zerotrace-test-harness/demo_key.py

**The key is fake.** It is the published Anthropic prefix followed by a fixed nonsense
body: correctly shaped, so the detector treats it exactly as it would a live key, and
worth nothing to anyone who copies it off the projector.
"""

from __future__ import annotations

# Assembled from pieces. Written out in one string, this file could not be saved.
PREFIX = "sk-" + "ant-" + "api" + "03-"
BODY = "x7Kq9mZp2Wv4Bn8Rt6" + "Yu3Ia5Oe1Ld0Sf3Gh7Jk2Mn5Pq8Rs"

#: Where to cut it for Step 2. Both halves have to be useless alone: the point of that
#: step is that the *join* is what gets caught, so a half that trips the detector on its
#: own demonstrates the wrong thing and makes the demo look like it worked by accident.
#:
#: 18 is the last cut where that holds. From 20 on, the prefix plus enough body is
#: already an Anthropic key by itself and message one is blocked -- which is correct
#: behaviour and a worse demo. Verified by sweeping every cut against the real detector;
#: see test_demo_key.py, which fails if a detector change moves the boundary.
CUT = 18


def halves() -> tuple[str, str]:
    full = PREFIX + BODY
    return full[:CUT], full[CUT:]


def main() -> int:
    a, b = halves()
    print()
    print("  Act 1, Step 1 -- type these joined, no space, as ONE string:")
    print(f"    {a}{b}")
    print()
    print("  Act 1, Step 2 -- type these as TWO separate messages:")
    print(f"    message 1:  {a}")
    print(f"    message 2:  {b}")
    print()
    print("  Fake key, correctly shaped. Nothing here is a live credential.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
