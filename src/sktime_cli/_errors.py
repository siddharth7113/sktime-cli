"""Structured errors with stable codes and exit-code mapping.

Error codes are part of the CLI contract (documented in SKILL.md):
agents branch on them, so codes are append-only and never renamed.
"""

from __future__ import annotations

EXIT_CODES: dict[str, int] = {
    "usage": 2,
    "missing_dependency": 3,
    "not_found": 4,
    "data_error": 5,
    "spec_error": 5,
    "sktime_error": 1,
    "internal": 1,
}


class CliError(Exception):
    """A CLI failure with a stable machine-readable code.

    Parameters
    ----------
    code : str
        One of the keys of ``EXIT_CODES``.
    message : str
        Human-readable one-line description of the failure.
    hint : str, optional
        Actionable next step, e.g. an install command.
    detail : str, optional
        Longer context, e.g. the underlying exception text.
    """

    def __init__(
        self,
        code: str,
        message: str,
        hint: str | None = None,
        detail: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.detail = detail
        self.exit_code = EXIT_CODES.get(code, 1)

    def to_dict(self, command: str | None = None) -> dict:
        """Return the error as the JSON-envelope dict emitted on stderr."""
        body: dict = {"code": self.code, "message": self.message}
        if self.hint:
            body["hint"] = self.hint
        if self.detail:
            body["detail"] = self.detail
        if command:
            body["command"] = command
        return {"error": body}


def missing_dependency(what: str, packages: list[str] | str) -> CliError:
    """Build a ``missing_dependency`` error with a ready-to-run install hint."""
    if isinstance(packages, str):
        packages = [packages]
    pkgs = " ".join(f'"{p}"' if any(c in p for c in "<>=!") else p for p in packages)
    return CliError(
        code="missing_dependency",
        message=f"{what} requires missing package(s): {', '.join(packages)}",
        hint=f"uv pip install {pkgs}" if pkgs else None,
    )
