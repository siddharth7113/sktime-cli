"""Regenerate the SVG terminal captures embedded in the README.

Runs real ``sktime-cli`` commands in a scratch workspace and renders their
ANSI output as terminal-window SVGs using rich. Regenerate after CLI output
changes with::

    uv run python docs/assets/generate.py

The SVGs are committed so the README renders without any build step.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.terminal_theme import MONOKAI
from rich.text import Text

ASSETS_DIR = Path(__file__).resolve().parent
TERMINAL_WIDTH = 100

# Animation timing (seconds); the whole scene loops as one CSS timeline.
CHAR_WIDTH_PX = 12.2
LEAD_IN = 0.6
TYPE_CHAR_SECONDS = 0.04
TYPE_MIN_SECONDS = 0.5
PAUSE_AFTER_TYPE = 0.4
OUT_LINE_STAGGER = 0.08
PAUSE_AFTER_BLOCK = 0.9
FINAL_HOLD = 3.0

_HIDDEN_CLIP = "inset(-30% 102% -30% -1%)"
_SHOWN_CLIP = "inset(-30% -1% -30% -1%)"


@dataclass
class Step:
    """One prompt line in a scene: a display string and the argv to run."""

    display: str
    argv: list[str] = field(default_factory=list)
    show_exit_code: bool = False


@dataclass
class Scene:
    """A sequence of steps captured into one SVG file."""

    filename: str
    title: str
    steps: list[Step]
    animate: bool = False


SCENES = [
    Scene(
        filename="demo.svg",
        title="sktime-cli — discover, fit, predict",
        animate=True,
        steps=[
            Step(
                "sktime-cli registry search forecaster"
                " -t capability:missing_values=true --limit 5",
                [
                    "registry",
                    "search",
                    "forecaster",
                    "-t",
                    "capability:missing_values=true",
                    "--limit",
                    "5",
                ],
            ),
            Step(
                "sktime-cli datasets load airline --output airline.csv",
                ["datasets", "load", "airline", "--output", "airline.csv"],
            ),
            Step(
                'sktime-cli run fit "NaiveForecaster(sp=12)"'
                " --data airline.csv --model-out model.zip",
                [
                    "run",
                    "fit",
                    "NaiveForecaster(sp=12)",
                    "--data",
                    "airline.csv",
                    "--model-out",
                    "model.zip",
                ],
            ),
            Step(
                "sktime-cli run predict --model model.zip --fh 1:3",
                ["run", "predict", "--model", "model.zip", "--fh", "1:3"],
            ),
        ],
    ),
    Scene(
        filename="doctor.svg",
        title="sktime-cli doctor",
        steps=[Step("sktime-cli doctor", ["doctor"])],
    ),
    Scene(
        filename="agent.svg",
        title="sktime-cli — machine-readable mode",
        steps=[
            Step(
                "sktime-cli run predict --model model.zip --fh 1:3 --json",
                ["run", "predict", "--model", "model.zip", "--fh", "1:3", "--json"],
            ),
            Step(
                'sktime-cli run fit "AutoARIMA()" --data airline.csv --json',
                ["run", "fit", "AutoARIMA()", "--data", "airline.csv", "--json"],
                show_exit_code=True,
            ),
        ],
    ),
]


def run_step(step: Step, cwd: Path) -> tuple[str, int]:
    """Run one CLI command with color forced on; return merged output and exit."""
    env = os.environ | {"FORCE_COLOR": "1", "COLUMNS": str(TERMINAL_WIDTH)}
    result = subprocess.run(
        ["sktime-cli", "--format", "human", *step.argv]
        if "--json" not in step.argv
        else ["sktime-cli", *step.argv],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout + result.stderr, result.returncode


@dataclass
class _Line:
    """One terminal row of the rendered SVG, located by character y offset."""

    start: int
    end: int
    n_chars: int
    is_command: bool
    text_count: int = 1


def _scan_lines(body: str) -> list[_Line]:
    """Group the matrix ``<text>`` elements of an SVG body into visual lines."""
    lines: list[_Line] = []
    last_y = None
    pattern = re.compile(
        r'<text [^>]*?y="([0-9.]+)"[^>]*?textLength="([0-9.]+)"[^>]*>(.*?)</text>',
        re.S,
    )
    for match in pattern.finditer(body):
        y, length, content = match.group(1), float(match.group(2)), match.group(3)
        n_chars = max(int(round(length / CHAR_WIDTH_PX)), 1)
        if y == last_y:
            line = lines[-1]
            line.end = match.end()
            line.n_chars += n_chars
            line.text_count += 1
        else:
            lines.append(
                _Line(match.start(), match.end(), n_chars, content == "\u276f")
            )
            last_y = y
    return lines


def _timeline(lines: list[_Line]) -> tuple[list[float], list[float], float]:
    """Compute per-line start times, command typing durations, and total loop."""
    starts: list[float] = []
    durations: list[float] = []
    t = LEAD_IN
    for i, line in enumerate(lines):
        if line.is_command:
            if i > 0:
                t += PAUSE_AFTER_BLOCK
            typing = max(line.n_chars * TYPE_CHAR_SECONDS, TYPE_MIN_SECONDS)
            starts.append(t)
            durations.append(typing)
            t += typing + PAUSE_AFTER_TYPE
        else:
            starts.append(t)
            durations.append(0.0)
            t += OUT_LINE_STAGGER
    return starts, durations, t + FINAL_HOLD


def animate_svg(svg: str) -> str:
    """Add a looping termynal-style typing animation to a rich terminal SVG.

    Command lines (those starting with the prompt glyph) are revealed
    character-by-character via a stepped ``clip-path``; output lines fade in
    line-by-line afterwards. Everything is plain CSS inside the SVG, so it
    animates when embedded with ``<img>`` on GitHub and degrades to the
    static screenshot where unsupported.
    """
    open_tag = re.search(r'<g class="terminal-\d+-matrix">', svg)
    if not open_tag:
        return svg
    body_start = open_tag.end()
    body_end = svg.index("</g>", body_start)
    body = svg[body_start:body_end]

    lines = _scan_lines(body)
    starts, durations, total = _timeline(lines)

    def pct(seconds: float) -> float:
        return round(seconds / total * 100, 4)

    pieces: list[str] = []
    css: list[str] = []
    pos = 0
    for i, line in enumerate(lines):
        pieces.append(body[pos : line.start])
        segment = body[line.start : line.end]
        if line.is_command:
            pieces.append(f'<g class="ac{i}">{segment}</g>')
            begin, finish = pct(starts[i]), pct(starts[i] + durations[i])
            css.append(
                f".ac{i} {{ clip-path: {_HIDDEN_CLIP};"
                f" animation: kac{i} {total}s linear infinite; }}\n"
                f"@keyframes kac{i} {{\n"
                f"  0% {{ clip-path: {_HIDDEN_CLIP}; }}\n"
                f"  {begin}% {{ clip-path: {_HIDDEN_CLIP};"
                f" animation-timing-function: steps({line.n_chars}, end); }}\n"
                f"  {finish}% {{ clip-path: {_SHOWN_CLIP}; }}\n"
                f"  100% {{ clip-path: {_SHOWN_CLIP}; }}\n"
                f"}}"
            )
        else:
            pieces.append(segment.replace('<text class="', f'<text class="ao{i} '))
            css.append(
                f".ao{i} {{ animation: kao{i} {total}s step-end infinite; }}\n"
                f"@keyframes kao{i} {{ 0% {{ opacity: 0; }}"
                f" {pct(starts[i])}% {{ opacity: 1; }}"
                f" 100% {{ opacity: 1; }} }}"
            )
        pos = line.end
    pieces.append(body[pos:])

    new_body = "".join(pieces)
    style = "<style>\n" + "\n".join(css) + "\n</style>\n"
    return (
        svg[: open_tag.start()] + style + open_tag.group(0) + new_body + svg[body_end:]
    )


def render_scene(scene: Scene, cwd: Path) -> None:
    """Capture every step of a scene and save it as one SVG."""
    console = Console(record=True, width=TERMINAL_WIDTH, file=open(os.devnull, "w"))
    for step in scene.steps:
        prompt = "[bold green]\u276f[/bold green]"
        console.print(f"{prompt} [bold]{step.display}[/bold]")
        output, exit_code = run_step(step, cwd)
        console.print(Text.from_ansi(output.rstrip("\n")))
        if step.show_exit_code:
            console.print(f"{prompt} [bold]echo $?[/bold]")
            console.print(str(exit_code))
        console.print()
    target = ASSETS_DIR / scene.filename
    console.save_svg(str(target), title=scene.title, theme=MONOKAI)
    if scene.animate:
        target.write_text(animate_svg(target.read_text(encoding="utf-8")), "utf-8")
    print(f"wrote {target}")


def main() -> None:
    """Regenerate all scenes in a shared scratch workspace."""
    with tempfile.TemporaryDirectory(prefix="sktime-cli-svg-") as tmp:
        for scene in SCENES:
            render_scene(scene, Path(tmp))


if __name__ == "__main__":
    main()
