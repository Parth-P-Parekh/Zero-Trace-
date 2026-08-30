#!/usr/bin/env python3
"""Render the two-minute ZeroTrace demo to an MP4, with narration.

    python scripts/make_demo_video.py

Everything is produced locally and nothing is uploaded:

    narration   Windows SAPI (System.Speech) via PowerShell -> one WAV per shot
    frames      Pillow, drawn in memory and piped to ffmpeg as raw RGB
    encode      the ffmpeg binary bundled with `imageio-ffmpeg`

**The audio drives the timing, not a guess.** Each shot lasts exactly as long as its
narration takes to speak, measured from the rendered WAV rather than estimated from a
words-per-minute figure. A demo whose captions drift out of sync with the voice reads as
broken even when every individual asset is right.

The terminal content is real output from this repository -- the refusals are the strings
the hooks actually emit, and `run.py rag_e2e` prints that clearance table. Nothing here is
a mock-up of a feature that does not exist.

Requires: Pillow, imageio-ffmpeg, and Windows (for SAPI). On another platform, supply
WAV files yourself in `build/audio/` named `shot-0.wav` .. and the renderer will use them.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import struct
import subprocess
import sys
import textwrap
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
AUDIO = BUILD / "audio"
OUT = BUILD / "zerotrace-demo.mp4"

W, H, FPS = 1920, 1080, 24

# ------------------------------------------------------------------ palette --
# Committed dark, painted explicitly. These are the README's terminal semantics:
# amber is the "amber band", sage is allow, clay is block.
GROUND = (20, 24, 31)
SURFACE = (27, 33, 43)
SURFACE2 = (34, 42, 53)
LINE = (46, 56, 70)
INK = (232, 227, 217)
DIM = (154, 164, 178)
FAINT = (102, 112, 126)
AMBER = (217, 164, 65)
ALLOW = (127, 163, 127)
BLOCK = (196, 104, 90)
YOU = (169, 196, 222)

FONTS = Path("C:/Windows/Fonts")


def font(name: str, size: int):
    return ImageFont.truetype(str(FONTS / name), size)


# -------------------------------------------------------------------- shots --
# Narration is the two-minute cut. `say` is spoken verbatim; `caption` is what appears
# on screen, which is the same words minus the stage directions.

SHOTS = [
    dict(
        title="the problem",
        term="claude code",
        say=("An A I coding agent reads your files and runs your commands. "
             "Everything it touches lands in a transcript you cannot recall. "
             "ZeroTrace asks two questions. May this person send this, "
             "and may this person see this."),
        lines=[
            ("note", "an agent reads your files, runs your commands,"),
            ("note", "and everything it touches enters a transcript you cannot recall"),
            ("blank", ""),
            ("out", "   may this person SEND this?      may this person SEE this?"),
            ("out", "   ─────────────────────────      ────────────────────────"),
            ("out", "   you ─► prompt ─► [outbound]      model ─► [inbound] ─► you"),
            ("out", "     agent ─► tool args ─►             file ─► tool result ─►"),
            ("out", "                                   retriever ─► documents ─►"),
        ],
    ),
    dict(
        title="the half everyone has",
        term="claude code",
        say=("An A P I key in a prompt. Blocked before it left the machine. "
             "Every tool does that."),
        lines=[
            ("you", "my key is sk-ant-api03-x7Kq9mZp2Wv4Bn8Rt6Yu3Ia5... is it valid?", True),
            ("blank", ""),
            ("block", "ZeroTrace blocked this prompt: it contains a credential"),
            ("block", "(ANTHROPIC_KEY). Nothing was sent."),
            ("blank", ""),
            ("note", "table stakes. every tool in this category does this."),
        ],
    ),
    dict(
        title="one key, two messages",
        term="claude code",
        say=("Now the same key, split across two messages. "
             "The first half goes through, because on its own it is clean. "
             "The second is blocked. Joined with what came before, it forms a credential. "
             "The conversation holds both halves. So the check has to hold both halves."),
        lines=[
            ("you", "remember this prefix, I'll need it in a second: sk-ant-api03-x7Kq9", True),
            ("allow", "▸ allowed - no credential in this message"),
            ("blank", ""),
            ("you", "and the rest is mZp2Wv4Bn8Rt6Yu3Ia5... now check the format", True),
            ("block", "ZeroTrace blocked this prompt: joined with what you sent just"),
            ("block", "before, it forms ANTHROPIC_KEY. Nothing was sent. Splitting a"),
            ("block", "secret across two messages does not divide it -- the conversation"),
            ("block", "holds both halves."),
        ],
    ),
    dict(
        title="what you may not read",
        term="claude code  ·  signed in as s.iyer",
        say=("A caseworker opens a citizen case file. It works. Now a payslip. "
             "Withheld. She is in citizen services. This is an H R record. "
             "And look at what the refusal does not contain. "
             "Not one figure from that payslip. "
             "The model reads our refusals, so the refusal is the last place a file can leak."),
        lines=[
            ("cmd", "zerotrace login s.iyer", True),
            ("out", "Acting as s.iyer in bharat-digital   groups: citizen-services"),
            ("blank", ""),
            ("you", "read the grievance file GRV-2291 and summarise the action needed", True),
            ("allow", "▸ Field officer to verify residence and re-seed the account."),
            ("blank", ""),
            ("you", "now read hr-personnel/payslip-2026-03-EMP4471.md, what is the net pay?", True),
            ("block", "ZeroTrace withheld 1 file(s) from this read: s.iyer"),
            ("block", "(citizen-services) is not cleared for them. Nothing was read"),
            ("block", "and nothing entered the transcript."),
            ("block", "  - payslip-2026-03-EMP4471.md: HR_RECORD (rule 3, org policy: mask)"),
        ],
    ),
    dict(
        title="the same file, a different person",
        term="claude code  ·  signed in as m.khan",
        say=("Different person. Same file. Same prompt. It works. "
             "Nothing changed except who was asking, and that came from a policy file "
             "neither of them wrote. The agent cannot route around it either. "
             "Cat, grep, a shell redirect: all the same read."),
        lines=[
            ("cmd", "zerotrace logout && zerotrace login m.khan", True),
            ("out", "Acting as m.khan in bharat-digital   groups: hr-personnel"),
            ("blank", ""),
            ("you", "now read hr-personnel/payslip-2026-03-EMP4471.md, what is the net pay?", True),
            ("allow", "▸ Net pay for March 2026 is 99,442 after PF of 8,688"),
            ("allow", "  and tax of 14,110."),
            ("blank", ""),
            ("note", "same file · same prompt · same agent · different person"),
        ],
    ),
    dict(
        title="the independent audit",
        term="terminal",
        say=("We gave this code to someone outside the team. They wrote their own harness, "
             "and found real holes. "
             "Four of five sensitive documents released to everyone, including an auditor "
             "with no clearance at all. That was ours. "
             "This is their script, unedited. Five of five now. "
             "And infosec still gets the runbook, because a rule has to leave someone "
             "able to do the job."),
        lines=[
            ("cmd", "python zerotrace-test-harness/run.py rag_e2e", True),
            ("out", "--- cag.audit   role=auditor    groups=('audit',)"),
            ("allow", "    visible (3): ['benefits-faq', 'tender-public', 'org-chart']"),
            ("block", "    withheld: doc-clinical-note     AADHAAR,QUASI_IDENT…  -> mask"),
            ("block", "    withheld: doc-citizen-record    AADHAAR,PAN           -> mask"),
            ("block", "    withheld: doc-infosec-incident  AWS_ACCESS_KEY        -> block"),
            ("block", "    withheld: doc-runbook           DB_URI                -> block"),
            ("blank", ""),
            ("out", "--- a.das       role=officer    groups=('infosec',)"),
            ("allow", "    visible (5): [… 'doc-infosec-incident', 'doc-runbook']"),
        ],
    ),
    dict(
        title="the receipt",
        term="terminal",
        say=("When our detectors are unsure, a model is asked after the response has gone, "
             "and it never sees the text. Only a shape. "
             "Every decision is on a hash chained ledger. "
             "Everyone stops a key going out. We also stop the payslip coming back."),
        lines=[
            ("note", "ACM-4417-KP  ─►  AAA-9999-AA     the model never sees the value"),
            ("blank", ""),
            ("cmd", "python scripts/verify_ledger.py", True),
            ("out", "  ok   bharat-digital     508 records   head 6c01ac5838e00f73…"),
            ("allow", "PASS -- every chain verifies from genesis."),
        ],
    ),
]

#: Typing speed and the pause between lines. Chosen so a whole shot's content is on
#: screen within about five seconds, whatever the shot's length.
CPS = 30.0
GAP_TYPED = 0.45
GAP_LINE = 0.30

COLOURS = {"cmd": INK, "you": YOU, "out": DIM, "allow": ALLOW,
           "block": BLOCK, "note": FAINT, "blank": DIM}


# ---------------------------------------------------------------- narration --

def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.?!])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def speak(text: str, path: Path, voice: str = "Microsoft Zira Desktop",
          rate: int = 1) -> None:
    """Render one shot's narration with Windows SAPI.

    44.1 kHz 16-bit rather than the 22 kHz default. That, plus the loudnorm pass at
    the mux, is where the intelligibility actually comes from -- a synthetic voice is
    judged on clarity long before realism, and one at half the sample rate with drifting
    levels sounds like a hold queue. The speaking *rate* turned out to matter much less,
    so it stays at +1 and the two-minute cap survives.
    """
    fmt = ("New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo("
           "44100, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, "
           "[System.Speech.AudioFormat.AudioChannel]::Mono)")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SelectVoice('{voice}'); $s.Rate = {rate}; "
        f"$f = {fmt}; "
        f"$s.SetOutputToWaveFile('{path}', $f); "
        f"$s.Speak([Console]::In.ReadToEnd()); $s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                   input=text, text=True, check=True, capture_output=True)


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


# ------------------------------------------------------------------ drawing --

def base_frame(shot: dict, fonts: dict) -> Image.Image:
    """Everything that does not move: chrome, titles, the terminal shell."""
    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)

    # Header
    d.text((80, 58), "Zero", font=fonts["brand"], fill=INK)
    w = d.textlength("Zero", font=fonts["brand"])
    d.text((80 + w, 58), "Trace", font=fonts["brand"], fill=AMBER)
    d.text((80, 112), shot["title"].upper(), font=fonts["eyebrow"], fill=FAINT)

    # Terminal shell
    tx, ty, tw, th = 80, 180, W - 160, 660
    d.rounded_rectangle([tx, ty, tx + tw, ty + th], radius=14, fill=SURFACE,
                        outline=LINE, width=2)
    d.rounded_rectangle([tx, ty, tx + tw, ty + 52], radius=14, fill=SURFACE2)
    d.rectangle([tx, ty + 38, tx + tw, ty + 52], fill=SURFACE2)
    d.line([tx, ty + 52, tx + tw, ty + 52], fill=LINE, width=2)
    for i in range(3):
        cx = tx + 26 + i * 22
        d.ellipse([cx, ty + 20, cx + 12, ty + 32], fill=LINE)
    d.text((tx + 104, ty + 16), shot["term"], font=fonts["small"], fill=FAINT)

    # Caption band
    d.line([0, H - 210, W, H - 210], fill=LINE, width=2)
    return img


def line_schedule(shot: dict) -> list[tuple[float, float]]:
    """When each line starts and finishes, in seconds from the shot's start.

    Absolute, not a share of the shot. The first version spread the lines across the
    shot's duration, which meant the *longest* shot typed most slowly -- so the 34-second
    audit shot sat on a half-typed command for seven seconds while the narrator was
    already three sentences in. A viewer needs the content up early and held, not
    dribbled out to fill the time.
    """
    out, t = [], 0.5
    for ln in shot["lines"]:
        typed = len(ln) > 2 and ln[2]
        dur = len(ln[1]) / CPS if typed else 0.0
        out.append((t, t + dur))
        t += dur + (GAP_TYPED if typed else GAP_LINE)
    return out


def draw_terminal(d: ImageDraw.ImageDraw, shot: dict, elapsed: float, fonts: dict):
    """Reveal the shot's lines on the wall clock, typing the marked ones."""
    x, y, lh = 128, 268, 44
    for (start, end), ln in zip(line_schedule(shot), shot["lines"]):
        if elapsed < start:
            break
        kind, text = ln[0], ln[1]
        typed = len(ln) > 2 and ln[2]

        if kind == "blank":
            y += lh
            continue

        if typed and elapsed < end:
            frac = (elapsed - start) / max(1e-6, end - start)
            shown = text[: max(1, int(len(text) * frac))]
        else:
            shown = text

        prefix = "$ " if kind == "cmd" else ("> " if kind == "you" else "")
        if prefix:
            d.text((x, y), prefix, font=fonts["mono"],
                   fill=AMBER if kind == "cmd" else FAINT)
        px = d.textlength(prefix, font=fonts["mono"]) if prefix else 0
        d.text((x + px, y), shown, font=fonts["mono"], fill=COLOURS[kind])

        if typed and elapsed < end:
            cw = d.textlength(prefix + shown, font=fonts["mono"])
            d.rectangle([x + cw + 2, y + 4, x + cw + 14, y + 36], fill=AMBER)
        y += lh


def draw_caption(d: ImageDraw.ImageDraw, text: str, fonts: dict):
    wrapped = textwrap.wrap(text, width=88)[:2]
    y = H - 168
    for row in wrapped:
        tw = d.textlength(row, font=fonts["caption"])
        d.text(((W - tw) / 2, y), row, font=fonts["caption"], fill=INK)
        y += 58


def draw_progress(d: ImageDraw.ImageDraw, frac: float):
    d.rectangle([0, H - 6, W, H], fill=LINE)
    d.rectangle([0, H - 6, int(W * frac), H], fill=AMBER)


# -------------------------------------------------------------------- build --

def main() -> int:
    if sys.platform != "win32" and not AUDIO.exists():
        print("SAPI narration needs Windows; supply build/audio/shot-N.wav instead.")
        return 2

    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    BUILD.mkdir(exist_ok=True)
    AUDIO.mkdir(parents=True, exist_ok=True)

    fonts = {
        "brand": font("segoeuib.ttf", 40),
        "eyebrow": font("seguisb.ttf", 21),
        "small": font("consola.ttf", 22),
        "mono": font("consola.ttf", 27),
        # Arial for the subtitle band: it is what a viewer expects a subtitle to
        # look like, and bold carries better over a dark terminal at 1080p.
        "caption": font("arialbd.ttf", 40),
    }

    # 1. Narration, and the durations it implies.
    print("narrating...")
    plan = []
    for i, shot in enumerate(SHOTS):
        wav = AUDIO / f"shot-{i}.wav"
        if not wav.exists():
            speak(shot["say"], wav)
        dur = wav_seconds(wav) + 0.38          # a beat of air after each shot
        plan.append(dur)
        print(f"  shot {i + 1}  {dur:5.1f}s  {shot['title']}")
    total = sum(plan)
    print(f"  total   {total:5.1f}s")

    # 2. Frames, straight into ffmpeg.
    print("rendering frames...")
    silent = BUILD / "silent.mp4"
    proc = subprocess.Popen(
        [ffmpeg, "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", str(silent)],
        stdin=subprocess.PIPE)

    done = 0.0
    for i, shot in enumerate(SHOTS):
        base = base_frame(shot, fonts)
        says = sentences(shot["say"])
        words = [max(1, len(s.split())) for s in says]
        bounds, acc = [], 0.0
        for wcount in words:
            acc += wcount / sum(words)
            bounds.append(acc)

        n = max(1, int(round(plan[i] * FPS)))
        for f in range(n):
            local = f / n
            img = base.copy()
            d = ImageDraw.Draw(img)
            draw_terminal(d, shot, local * plan[i], fonts)
            k = next((j for j, b in enumerate(bounds) if local < b), len(says) - 1)
            draw_caption(d, says[k], fonts)
            draw_progress(d, (done + local * plan[i]) / total)
            proc.stdin.write(img.tobytes())
        done += plan[i]
        print(f"  shot {i + 1} done")

    proc.stdin.close()
    if proc.wait() != 0:
        print("ffmpeg failed on the video pass")
        return 1

    # 3. One audio track, then mux.
    print("muxing audio...")
    listing = BUILD / "audio.txt"
    listing.write_text(
        "".join(f"file '{(AUDIO / f'shot-{i}.wav').as_posix()}'\n"
                f"duration {plan[i]:.3f}\n" for i in range(len(SHOTS))),
        encoding="utf-8")
    track = BUILD / "narration.wav"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", str(track)], check=True)
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(silent),
                    "-i", str(track), "-c:v", "copy",
                    # Broadcast-ish speech levelling: SAPI drifts a few dB between
                    # shots, which reads as the narrator moving away from the mic.
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                    "-shortest", str(OUT)], check=True)

    size = OUT.stat().st_size / 1e6
    print(f"\n{OUT}  ({size:.1f} MB, {total:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
