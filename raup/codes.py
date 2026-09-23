"""Generation of the short code the clinician shares with the patient.

Not a strong authentication mechanism: it's the only access barrier in the
MVP (no login), a conscious decision for this phase — see DECISIONS.md
D-010. Visually ambiguous characters (0/O, 1/I/L) are excluded so the code
is easy to read and copy by hand.
"""

from __future__ import annotations

import secrets

_ALPHABET = "".join(c for c in "ABCDEFGHJKMNPQRSTUVWXYZ23456789")
_DEFAULT_LENGTH = 6


def generate_code(length: int = _DEFAULT_LENGTH) -> str:
    """Generates a cryptographically secure random code, e.g. "7K9XQP"."""

    if length < 4:
        raise ValueError("The code must be at least 4 characters long")
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
