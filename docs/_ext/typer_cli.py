"""Sphinx directive that documents a Typer application.

``sphinx-click`` cannot be used here: Typer vendors its own copy of Click, so
the command objects returned by :func:`typer.main.get_command` are not
instances of the public ``click`` classes that ``sphinx-click`` type-checks
against. This directive walks the vendored command tree instead, which keeps
the CLI reference generated from the live application and therefore always in
step with ``sktime-cli --help``.

Usage in a MyST document::

    ```{typer-cli} sktime_cli.app:app
    :prog: sktime-cli
    ```
"""

from __future__ import annotations

import importlib
import inspect

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from docutils.statemachine import StringList

#: Heading level of the outermost generated section. The directive is used on
#: a page whose own title is level 1, so commands start at level 2.
_BASE_LEVEL = 2


def _load(target: str):
    """Import ``module:attribute`` and return the Typer app it names."""
    module_name, _, attr = target.partition(":")
    if not attr:
        raise ValueError(f"expected 'module:attribute', got {target!r}")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def _is_group(command) -> bool:
    return bool(getattr(command, "commands", None))


def _clean(text: str | None) -> str:
    """Normalise a help string for embedding in reStructuredText."""
    if not text:
        return ""
    return inspect.cleandoc(text).replace("\x08", "").strip()


def _short_help(command) -> str:
    text = _clean(getattr(command, "short_help", None) or command.help)
    return text.split("\n\n")[0].replace("\n", " ")


def _type_name(param) -> str:
    param_type = getattr(param, "type", None)
    choices = getattr(param_type, "choices", None)
    if choices:
        return "|".join(str(choice) for choice in choices)
    name = getattr(param_type, "name", None)
    return str(name).upper() if name else ""


def _invocation(param) -> str:
    """Render the ``--flag / --no-flag VALUE`` half of a definition item."""
    names = list(param.opts) + list(getattr(param, "secondary_opts", []) or [])
    rendered = ", ".join(f"`{name}`" for name in names)
    if getattr(param, "is_flag", False):
        return rendered
    metavar = param.metavar or _type_name(param)
    return f"{rendered} {metavar}".strip() if metavar else rendered


def _annotations(param) -> list[str]:
    """Collect the trailing notes for a parameter: default, env var, ..."""
    notes = []
    if getattr(param, "required", False):
        notes.append("**required**")
    if getattr(param, "multiple", False):
        notes.append("repeatable")
    default = getattr(param, "default", None)
    if not getattr(param, "required", False) and default not in (None, False, [], ()):
        value = getattr(default, "value", default)
        notes.append(f"default: `{value}`")
    envvar = getattr(param, "envvar", None)
    if envvar:
        names = envvar if isinstance(envvar, (list, tuple)) else [envvar]
        joined = ", ".join(f"`{name}`" for name in names)
        notes.append(f"environment variable: {joined}")
    return notes


def _param_lines(title: str, params: list) -> list[str]:
    """Render one definition list covering ``params`` under ``title``."""
    if not params:
        return []
    lines = [f"**{title}**", ""]
    for param in params:
        lines.append(_invocation(param))
        body = _clean(getattr(param, "help", None)).replace("\n", " ")
        notes = _annotations(param)
        if notes:
            body = f"{body} ({', '.join(notes)})" if body else f"({', '.join(notes)})"
        lines.append(f": {body or 'No description.'}")
        lines.append("")
    return lines


def _command_lines(
    command, path: list[str], depth: int, globals_: frozenset[str] = frozenset()
) -> list[str]:
    """Render ``command`` and, for groups, every visible subcommand.

    Options in ``globals_`` are documented once on the root command and
    skipped everywhere else, which keeps ``--format`` and ``--json`` from
    repeating on all 20 leaf commands.
    """
    title = " ".join(path)
    lines = ["#" * (_BASE_LEVEL + depth) + f" `{title}`", ""]

    help_text = _clean(command.help)
    if help_text:
        lines.extend([help_text, ""])

    args = " ".join(
        child.name if getattr(child, "required", False) else f"[{child.name}]"
        for child in command.params
        if type(child).__name__.endswith("Argument")
    )
    tail = "COMMAND [ARGS]..." if _is_group(command) else args
    usage = f"{title} [OPTIONS] {tail}".strip()
    lines.extend(["```text", usage, "```", ""])

    arguments = [p for p in command.params if type(p).__name__.endswith("Argument")]
    options = [
        p
        for p in command.params
        if not type(p).__name__.endswith("Argument")
        and not getattr(p, "hidden", False)
        and not globals_.issuperset(p.opts)
    ]
    lines.extend(_param_lines("Arguments", arguments))
    lines.extend(_param_lines("Options", options))

    if not _is_group(command):
        return lines

    children = sorted(
        (name, child)
        for name, child in command.commands.items()
        if not getattr(child, "hidden", False)
    )
    if children:
        lines.extend(["**Subcommands**", ""])
        for name, child in children:
            lines.append(f"`{name}`")
            lines.extend([f": {_short_help(child) or 'No description.'}", ""])
    for name, child in children:
        lines.extend(_command_lines(child, path + [name], depth + 1, globals_))
    return lines


class TyperCliDirective(Directive):
    """Document a Typer application and all of its subcommands."""

    has_content = False
    required_arguments = 1
    option_spec = {"prog": directives.unchanged}

    def run(self):
        """Build the command reference for the configured application."""
        import typer.main

        app = _load(self.arguments[0])
        command = typer.main.get_command(app)
        prog = self.options.get("prog") or command.name or "cli"

        globals_ = frozenset(
            opt
            for param in command.params
            if not type(param).__name__.endswith("Argument")
            for opt in param.opts
        )
        lines = _command_lines(command, [prog], 0, globals_)
        node = nodes.section()
        node.document = self.state.document
        self.state.nested_parse(
            StringList(lines, source=self.arguments[0]), self.content_offset, node
        )
        return node.children


def setup(sphinx_app):
    """Register the ``typer-cli`` directive."""
    sphinx_app.add_directive("typer-cli", TyperCliDirective)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
