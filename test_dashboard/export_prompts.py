"""Write out the five million prompts the benchmark actually ran, in plain English.

`corpus.py` generates rather than stores, which is what makes the run reproducible
from a seed instead of from a multi-gigabyte artefact. That is the right default for
running the test and the wrong one for reading it: "trust me, shard 47 contains an
Aadhaar number" is not something anybody can check.

So this replays the identical generator - same seed, same shard layout, same order as
`benchmark.py --records 5000000 --workers 20 --shards 240` - and writes every record
out with its prompt readable, its expectation in words, and no machine constants.

    python test_dashboard/export_prompts.py                    # all 5,000,000
    python test_dashboard/export_prompts.py --records 2000     # a readable sample

**Size.** The full file is a few gigabytes. It is deliberately not committed - the
generator is, and it reproduces the file byte for byte. `--records` writes a smaller
one that is committable and still representative, because the scenario mix is drawn
the same way at any size.

**Every value in it is synthetic.** The keys match the shape of real credentials so
the detector is exercised honestly, and the character bodies are random. Nothing here
is a live secret, and the file can be read, shared and attached to a report.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import corpus  # noqa: E402

# --------------------------------------------------------------- plain English --

#: What each scenario family is, said the way it would be said out loud. The corpus
#: names are fine in code and useless in a document somebody has to review.
SCENARIOS: dict[str, str] = {
    "clean_code": "Ordinary engineering work. Nothing sensitive.",
    "clean_prose": "Ordinary office work. Nothing sensitive.",
    "clean_agent_trace": "An AI agent reading a file and reporting back. Nothing sensitive.",
    "decoy_placeholder": "A config template full of blanks like <your-password>. Looks like secrets, is not.",
    "decoy_docs_example": "Documentation quoting a vendor's published example key.",
    "decoy_high_entropy": "Build output with long random-looking strings. Checksums, not secrets.",
    "decoy_near_miss_id": "A twelve-digit order number that is not an Aadhaar and has no record around it.",
    "cred_anthropic": "A live Anthropic API key pasted into a prompt.",
    "cred_openai": "A live OpenAI API key pasted into a prompt.",
    "cred_github": "A GitHub access token pasted into a prompt.",
    "cred_aws": "An AWS access key pasted into a prompt.",
    "cred_razorpay": "A Razorpay payment key pasted into a prompt.",
    "cred_slack": "A Slack token pasted into a prompt.",
    "cred_google": "A Google API key pasted into a prompt.",
    "cred_stripe": "A Stripe payment key pasted into a prompt.",
    "cred_jwt": "A login token pasted into a prompt.",
    "cred_private_key": "A private key pasted into a prompt.",
    "cred_db_uri": "A database connection string with the password in it.",
    "cred_obfuscated": "A live key broken up, so it no longer looks like one at a glance.",
    "cred_encoded": "A live key scrambled the way a config file or a shell would store it.",
    "india_pan": "A PAN number in a request about a customer.",
    "india_aadhaar": "An Aadhaar number in a request about a citizen.",
    "india_gstin": "A GST registration number.",
    "india_ifsc": "A bank IFSC code.",
    "india_upi": "A UPI ID.",
    "india_voter": "A voter ID number.",
    "s1_config_assign": "A runbook telling someone to export a password into their shell.",
    "s1_config_yaml": "A service config with a password in it, copied out of a wiki.",
    "s1_table": "A handover document with a table of service credentials in it.",
    "composite_record": "A citizen's record. No single field identifies them; together they do.",
    "composite_weak": "An invoice with a long number and one incidental detail. Not a record.",
    "nested_tool_result": "A customer record returned by a tool, buried inside the response.",
    "readonly_system": "A key sitting in the assistant's own setup instructions.",
    "readonly_tool_def": "A key in a tool's published documentation, which no user can edit.",
    "inbound_medical": "A clinical note coming back from the model.",
    "inbound_hr": "An employee record coming back from the model.",
    "inbound_financial": "A financial reconciliation coming back from the model.",
    "inbound_customer": "A customer record coming back from the model.",
    "multi_leak": "One request carrying a key, a PAN, a phone number and a bank code at once.",
}

#: Evasion styles, named by what was done rather than by the variable name.
VARIANTS: dict[str, str] = {
    "spaced": "The key was typed with spaces every few characters.",
    "zerowidth": "The key was padded with invisible characters.",
    "wrapped": "The key was split across several lines.",
    "k8s_secret": "The key was base64-encoded, as a Kubernetes secret stores it.",
    "powershell": "The key was base64-encoded, as PowerShell emits it.",
    "url_encoded": "The key was URL-encoded, as it would appear in a web address.",
}

THINGS: dict[str, str] = {
    "ANTHROPIC_KEY": "Anthropic key", "OPENAI_KEY": "OpenAI key",
    "GITHUB_TOKEN": "GitHub token", "AWS_ACCESS_KEY": "AWS key",
    "GOOGLE_API_KEY": "Google API key", "SLACK_TOKEN": "Slack token",
    "STRIPE_KEY": "Stripe key", "RAZORPAY_KEY": "Razorpay key",
    "JWT": "Login token", "PRIVATE_KEY": "Private key",
    "DB_URI": "Database password", "GENERIC_SECRET": "Password or token",
    "PAN": "PAN", "AADHAAR": "Aadhaar number", "GSTIN": "GST number",
    "IFSC": "Bank IFSC code", "UPI_VPA": "UPI ID", "VOTER_ID": "Voter ID",
    "EMAIL": "Email address", "PHONE": "Phone number",
    "QUASI_IDENTIFIER_SET": "Personal record",
    "HIGH_ENTROPY_STRING": "Random-looking text",
}

ACTIONS: dict[str, str] = {
    "allow": "Let it through",
    "tokenize": "Swap the value for a stand-in, then send",
    "mask": "Hide the value, then send",
    "block": "Stop the request",
}

ROLES: dict[str, str] = {
    "officer": "Case officer", "auditor": "Auditor", "director": "Director",
    "contractor": "Outside contractor", "support_agent": "Support agent",
    "service": "An application, not a person", "unregistered": "Nobody we recognise",
}


def readable_text(payload: dict) -> list[str]:
    """Pull the human-readable text out of a provider envelope, in order.

    The payload is an Anthropic or OpenAI request. What a reviewer wants to read is
    the words in it, not the JSON around them - so the envelope is unwrapped and each
    piece of text comes back as its own line with a label.
    """
    out: list[str] = []

    if payload.get("system"):
        out.append(f"[setup instructions] {payload['system']}")

    for tool in payload.get("tools") or ():
        desc = tool.get("description")
        if desc:
            out.append(f"[tool description: {tool.get('name', '?')}] {desc}")

    for message in payload.get("messages") or ():
        role = message.get("role", "?")
        content = message.get("content")
        if isinstance(content, str):
            out.append(f"[{role}] {content}")
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    inner = part.get("content") or part.get("text")
                    kind = part.get("type", "part")
                    if inner:
                        out.append(f"[{role}, {kind}] {inner}")

    # An inbound record is the model's reply rather than a request.
    for choice in payload.get("choices") or ():
        text = (choice.get("message") or {}).get("content")
        if text:
            out.append(f"[model reply] {text}")
    for part in payload.get("content") or ():
        if isinstance(part, dict) and part.get("text"):
            out.append(f"[model reply] {part['text']}")

    return out


def describe(rec) -> dict:
    """One record, with nothing in it that needs a lookup table to read."""
    expected = sorted(THINGS.get(c, c) for c in rec.expect)
    reported_only = sorted(THINGS.get(c, c) for c in rec.expect_readonly)

    entry: dict = {
        "id": rec.index,
        "case": SCENARIOS.get(rec.scenario, rec.scenario),
        "case_id": rec.scenario,
        "direction": "Going to the model" if rec.leg == "outbound"
                     else "Coming back from the model",
        "sent_by": {
            "who": rec.actor[0],
            "role": ROLES.get(rec.actor[1], rec.actor[1]),
            "teams": list(rec.actor[2]) or ["none"],
        },
        "app": rec.workload,
        "ai_tool": rec.harness,
        "environment": "Live" if rec.env == "production" else "Test",
        "text": readable_text(rec.payload),
        "should_find": expected or ["Nothing"],
        "should_do": ACTIONS.get(rec.expect_action, rec.expect_action),
    }
    if rec.variant:
        entry["evasion"] = VARIANTS.get(rec.variant, rec.variant)
    if reported_only:
        entry["report_but_do_not_block"] = reported_only
        entry["why"] = ("It sits in text the person writing the prompt cannot edit, "
                        "so blocking them for it would punish the wrong person.")
    return entry


# ------------------------------------------------------------------------ main --

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=int, default=5_000_000)
    ap.add_argument("--shards", type=int, default=240)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    out = Path(args.out) if args.out else here / (
        "prompts.json" if args.records >= 5_000_000
        else f"prompts.sample.{args.records}.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    total = args.records
    # The same shard layout benchmark.py used, so record N here is record N there.
    per = -(-total // args.shards)

    started = time.time()
    written = 0
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("[\n")
        offset = 0
        remaining = total
        for shard_id in range(args.shards):
            n = min(per, remaining)
            if n <= 0:
                break
            for rec in corpus.shard(shard_id, n, offset):
                fh.write("  " if written == 0 else ",\n  ")
                json.dump(describe(rec), fh, ensure_ascii=False)
                written += 1
            offset += n
            remaining -= n
            if shard_id % 20 == 0 or remaining <= 0:
                mb = out.stat().st_size / 1e6 if out.exists() else 0
                print(f"  {written:>9,} records  {mb:>8,.0f} MB  "
                      f"{time.time() - started:>6.1f}s", flush=True)
        fh.write("\n]\n")

    size = out.stat().st_size
    print(f"\nwrote {out}")
    print(f"{written:,} prompts · {size / 1e6:,.1f} MB · {time.time() - started:.1f}s")
    if size > 90_000_000:
        print("\nToo large for git. The generator is committed and reproduces this "
              "file exactly; re-run this script to recreate it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
