"""The baseline S1 ruleset. Compiled in, immutable, cannot be weakened.

``rules.yaml`` is configuration, and configuration is an attack surface. A detection
rule that lives only in an editable file can be removed, renamed, or have its confidence
dropped below the enforcement threshold -- and the result is a control that reports
itself healthy while catching nothing. Nobody has to be malicious for this to happen; a
tenant tuning away a false positive at 2am does it by accident.

So the baseline lives here, in code, and the config layer can only move in one
direction:

* **Add** rules the baseline does not have -- a tenant's own internal key names.
* **Raise** the confidence of a baseline rule.
* **Add** placeholder patterns, which reduce false positives.

It may **not** delete a baseline rule, lower its confidence, or loosen its pattern.
Attempting to is a load-time error naming the rule, not a silent downgrade.

This is deliberately the same property as the policy action lattice (CODE-01 §8.2), where
a business unit may move an action up but never down. One direction is safe; the other is
how a security control quietly stops working.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..contracts.entity_classes import EntityClass


@dataclass(frozen=True, slots=True)
class BaselineRule:
    name: str
    entity_class: EntityClass
    pattern: str
    confidence: float


#: Key names that type their value whatever the value looks like.
#:
#: Patterns are matched against a key normalised so ``_`` and ``-`` become spaces, hence
#: ``[ _-]?`` rather than ``[_-]?``. See ``ContextRules.classify_key``.
BASELINE_KEY_RULES: tuple[BaselineRule, ...] = (
    BaselineRule("password_key", EntityClass.GENERIC_SECRET,
                 r"(?i)\b(pass(word|wd|phrase)?|pwd)\b", 0.90),
    BaselineRule("secret_key", EntityClass.GENERIC_SECRET,
                 r"(?i)\b(secret|client[ _-]?secret|private[ _-]?token)\b", 0.90),
    BaselineRule("api_key_key", EntityClass.GENERIC_SECRET,
                 r"(?i)\b(api[ _-]?key|apikey|access[ _-]?key|auth[ _-]?token|bearer)\b", 0.88),
    BaselineRule("credential_key", EntityClass.GENERIC_SECRET,
                 r"(?i)\b(credential|cred|authorization)\b", 0.85),
    # Deliberately below the enforcement threshold: "token" is everywhere in ordinary
    # engineering prose -- token limit, token count, tokenizer. It escalates, never blocks.
    BaselineRule("bare_token_key", EntityClass.GENERIC_SECRET,
                 r"(?i)\b(token|session[ _-]?id)\b", 0.55),
)

#: Where a key/value pair can be written. Group ``k`` is the key, ``v`` the value.
BASELINE_STRUCTURES: tuple[tuple[str, str], ...] = (
    ("env_assignment",
     r"(?m)^[ \t]*(?:export[ \t]+)?(?P<k>[A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*(?P<v>[^\r\n#]+)"),
    ("yaml_or_json",
     r"""(?m)^[ \t]*["']?(?P<k>[A-Za-z_][A-Za-z0-9_.\-]*)["']?[ \t]*:[ \t]*["']?(?P<v>[^\r\n,"']+)"""),
    ("cli_flag",
     r"--(?P<k>[a-zA-Z][a-zA-Z0-9\-]*)[= ](?P<v>[^\s]+)"),
    ("http_header",
     r"(?im)^[ \t]*(?P<k>authorization|x-api-key|x-auth-token)[ \t]*:[ \t]*(?:bearer[ \t]+)?(?P<v>[^\r\n]+)"),
)

#: Values that are documentation, not secrets. Config *may* add to this list -- more
#: placeholders means fewer false positives, which is the safe direction.
BASELINE_IGNORE_VALUES: tuple[str, ...] = (
    r"(?i)^(x{3,}|\*{3,}|\.{3,}|-+)$",
    r"(?i)^<[^>]*>$",
    r"(?i)^\$\{[^}]*\}$",
    r"(?i)^\$[A-Z_][A-Z0-9_]*$",
    r"(?i)^%[A-Z_]+%$",
    r"(?i)^(none|null|nil|todo|tbd|changeme|example|placeholder|redacted|omitted)$",
    r"(?i)^(true|false|yes|no|enabled|disabled)$",
    r"(?i)^\{\{[^}]*\}\}$",
    r"^[0-9]+$",
)

BASELINE_TABLE_HEADER = r"(?i)^\s*(pass(word)?|secret|token|api[ _-]?key|credential|key)\s*$"
BASELINE_TABLE_CONFIDENCE = 0.85

#: Floors. Config may raise these; lowering them would widen what counts as a
#: placeholder, which is the unsafe direction.
BASELINE_MIN_LENGTH = 4
BASELINE_MAX_LENGTH = 512

#: Entropy floor for a credential value. Found by running against real traffic: a
#: placeholder like `xx_xxxxxxxxxxxxxxxxxxx` measures 0.77, while `hunter2` -- a weak but
#: genuine password -- measures 2.81. Anything this repetitive is filler, not a secret.
BASELINE_MIN_VALUE_ENTROPY = 1.8

#: A credential value does not contain internal whitespace. This one came straight out of
#: the real-traffic run: the env-assignment pattern captures to end of line, so a
#: transcript line reading `... DB_PASSWORD=` followed by formatted output was matched
#: with a "value" of `12/34  100.0%`. Requiring no spaces removes that whole class.
BASELINE_REJECT_WHITESPACE_VALUES = True


class RuleWeakened(ValueError):
    """Config tried to remove, loosen, or lower a baseline rule.

    Loud on purpose. The alternative -- accepting the weaker value and logging a
    warning -- is precisely how a control ends up reporting itself healthy while
    enforcing nothing.
    """

    def __init__(self, rule: str, detail: str) -> None:
        super().__init__(
            f"rules.yaml weakens baseline rule {rule!r}: {detail}. "
            f"Configuration may add rules or raise confidence; it may not lower the "
            f"floor (gateway/detect/baseline_rules.py)."
        )


def compile_baseline() -> tuple[list, list, list]:
    """(key_rules, structures, ignore_values), compiled. Never fails at runtime --
    these patterns are tested, so a compile error here is a build-time bug."""
    from .s1_context import KeyRule

    keys = [
        KeyRule(r.name, r.entity_class, re.compile(r.pattern), r.confidence)
        for r in BASELINE_KEY_RULES
    ]
    structs = [(n, re.compile(p)) for n, p in BASELINE_STRUCTURES]
    ignores = [re.compile(p) for p in BASELINE_IGNORE_VALUES]
    return keys, structs, ignores
