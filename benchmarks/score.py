"""Validate and score recorded sktime-cli model benchmark runs.

Outcome judgments are deliberately human-entered after a blind review. Protocol
points and telemetry are derived from the complete tool trace.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SUITE_DIRS = {
    "sktime-cli-adversarial": HERE,
    "sktime-cli-adversarial-hard": HERE / "hard",
}


class RunError(ValueError):
    """A run record is incomplete or inconsistent with the fixed suite."""


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise RunError(f"{path}: expected a JSON object")
    return value


def _has_json_flag(argv: list[str]) -> bool:
    if "--json" in argv:
        return True
    return any(
        arg == "--format" and index + 1 < len(argv) and argv[index + 1] == "json"
        for index, arg in enumerate(argv)
    )


def _is_json_error(call: dict[str, Any]) -> bool:
    if call.get("exit_code") == 0:
        return False
    for key in ("stderr", "stdout"):
        raw = call.get(key, "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            return True
    return False


def _validate_header(run: dict[str, Any], prompts: dict[str, Any]) -> None:
    for key in (
        "run_id",
        "suite_id",
        "suite_version",
        "model",
        "environment",
        "skill",
        "complete_tool_trace",
        "tasks",
    ):
        if key not in run:
            raise RunError(f"missing run field: {key}")
    if run["suite_id"] != prompts["suite_id"]:
        raise RunError(f"unexpected suite_id: {run['suite_id']!r}")
    if run["suite_version"] != prompts["suite_version"]:
        raise RunError(f"unexpected suite_version: {run['suite_version']!r}")
    if run["complete_tool_trace"] is not True:
        raise RunError("complete_tool_trace must be true for a comparable score")
    if not isinstance(run["tasks"], list):
        raise RunError("tasks must be a list")
    model = run["model"]
    if not isinstance(model, dict) or any(
        key not in model for key in ("provider", "name", "version", "settings")
    ):
        raise RunError("model must include provider, name, version, and settings")
    environment = run["environment"]
    if not isinstance(environment, dict):
        raise RunError("environment must be an object")
    for key, expected in prompts["target"].items():
        if environment.get(key) != expected:
            raise RunError(
                f"environment {key}={environment.get(key)!r}; expected {expected!r}"
            )
    if environment.get("network") != "disabled":
        raise RunError("benchmark runs require network=disabled")
    soft_dependencies = environment.get("soft_dependencies", {})
    for dependency, expected in prompts.get("environment_requirements", {}).items():
        if soft_dependencies.get(dependency) != expected:
            raise RunError(
                f"benchmark requires {dependency}={expected}, got "
                f"{soft_dependencies.get(dependency)!r}"
            )
    skill = run["skill"]
    if not isinstance(skill, dict) or skill.get("path") != prompts["skill_path"]:
        raise RunError("run does not identify the benchmark's sktime-cli skill")
    sha256 = skill.get("sha256")
    if (
        skill.get("injected") is not True
        or not isinstance(sha256, str)
        or len(sha256) != 64
        or set(sha256) == {"0"}
    ):
        raise RunError("skill must be injected and have its real 64-character SHA-256")
    try:
        int(sha256, 16)
    except ValueError as error:
        raise RunError("skill SHA-256 must be hexadecimal") from error


def score_run(
    run: dict[str, Any],
    prompts: dict[str, Any],
    scoring: dict[str, Any],
    *,
    allow_partial: bool = False,
) -> dict[str, Any]:
    """Validate and calculate one run's score and trace telemetry."""
    _validate_header(run, prompts)
    if (
        scoring.get("suite_id") != prompts["suite_id"]
        or scoring.get("suite_version") != prompts["suite_version"]
    ):
        raise RunError("scoring key does not match the prompt suite")
    prompt_tasks = {task["id"]: task for task in prompts["tasks"]}
    scoring_tasks = {task["id"]: task for task in scoring["tasks"]}
    if set(prompt_tasks) != set(scoring_tasks):
        raise RunError("prompt and scoring task IDs differ")

    recorded: dict[str, dict[str, Any]] = {}
    for task in run["tasks"]:
        task_id = task.get("id")
        if task_id not in prompt_tasks:
            raise RunError(f"unknown task ID: {task_id!r}")
        if task_id in recorded:
            raise RunError(f"duplicate task ID: {task_id}")
        recorded[task_id] = task
    missing = set(prompt_tasks) - set(recorded)
    if missing and not allow_partial:
        raise RunError("missing tasks: " + ", ".join(sorted(missing)))

    task_results = []
    total_calls = successful_calls = failed_calls = json_errors = 0
    total_duration_ms = 0.0
    input_tokens = output_tokens = 0
    token_usage_complete = True
    recovered_tasks = 0

    for task_id in prompt_tasks:
        if task_id not in recorded:
            continue
        task = recorded[task_id]
        calls = task.get("tool_calls")
        judgments = task.get("judgments")
        if not isinstance(calls, list) or not isinstance(judgments, list):
            raise RunError(f"{task_id}: tool_calls and judgments must be lists")
        if any(not isinstance(call, dict) for call in calls):
            raise RunError(f"{task_id}: every tool call must be an object")
        if any(not isinstance(judgment, dict) for judgment in judgments):
            raise RunError(f"{task_id}: every judgment must be an object")
        assistant_messages = task.get("assistant_messages")
        if not isinstance(assistant_messages, list) or any(
            not isinstance(message, str) for message in assistant_messages
        ):
            raise RunError(f"{task_id}: assistant_messages must be a string list")
        if not isinstance(task.get("final_answer"), str):
            raise RunError(f"{task_id}: final_answer must be a string")
        token_usage = task.get("token_usage")
        if token_usage is None:
            token_usage_complete = False
        elif not isinstance(token_usage, dict) or any(
            not isinstance(token_usage.get(key), int) or token_usage[key] < 0
            for key in ("input", "output")
        ):
            raise RunError(f"{task_id}: invalid token_usage")
        else:
            input_tokens += token_usage["input"]
            output_tokens += token_usage["output"]

        expected_criteria = {
            item["id"]: float(item["points"])
            for item in scoring_tasks[task_id]["criteria"]
        }
        earned_by_id: dict[str, float] = {}
        for judgment in judgments:
            criterion_id = judgment.get("criterion_id")
            if criterion_id not in expected_criteria:
                raise RunError(f"{task_id}: unknown criterion {criterion_id!r}")
            if criterion_id in earned_by_id:
                raise RunError(f"{task_id}: duplicate criterion {criterion_id!r}")
            earned = judgment.get("earned")
            if not isinstance(earned, (int, float)):
                raise RunError(f"{task_id}/{criterion_id}: earned must be numeric")
            if not 0 <= float(earned) <= expected_criteria[criterion_id]:
                raise RunError(
                    f"{task_id}/{criterion_id}: earned must be between 0 and "
                    f"{expected_criteria[criterion_id]:g}"
                )
            earned_by_id[criterion_id] = float(earned)
        absent_criteria = set(expected_criteria) - set(earned_by_id)
        if absent_criteria:
            raise RunError(
                f"{task_id}: missing judgments: " + ", ".join(sorted(absent_criteria))
            )

        command_calls = [call for call in calls if call.get("kind") == "command"]
        cli_only = (
            bool(calls)
            and len(command_calls) == len(calls)
            and all(
                isinstance(call.get("argv"), list)
                and bool(call["argv"])
                and call["argv"][0] == "sktime-cli"
                for call in command_calls
            )
        )
        json_discipline = bool(command_calls) and all(
            _has_json_flag(call["argv"]) for call in command_calls
        )
        within_budget = len(calls) <= int(prompt_tasks[task_id]["max_cli_calls"])

        manual_score = sum(earned_by_id.values())
        protocol_score = float(cli_only) + float(json_discipline and within_budget)
        score = manual_score + protocol_score
        if not cli_only and scoring["scoring"]["non_cli_tool_disqualifies_task"]:
            score = 0.0

        exits = []
        for call in command_calls:
            exit_code = call.get("exit_code")
            duration = call.get("duration_ms", 0)
            if not isinstance(exit_code, int):
                raise RunError(f"{task_id}: command exit_code must be an integer")
            if not isinstance(duration, (int, float)) or duration < 0:
                raise RunError(f"{task_id}: duration_ms must be non-negative")
            if not isinstance(call.get("stdout"), str) or not isinstance(
                call.get("stderr"), str
            ):
                raise RunError(f"{task_id}: stdout/stderr must be strings")
            exits.append(exit_code)
            total_calls += 1
            total_duration_ms += float(duration)
            if exit_code == 0:
                successful_calls += 1
            else:
                failed_calls += 1
                json_errors += int(_is_json_error(call))
        if any(code != 0 for code in exits) and exits and exits[-1] == 0:
            recovered_tasks += 1

        task_results.append(
            {
                "id": task_id,
                "score": score,
                "max_score": 10,
                "manual_score": manual_score,
                "protocol_score": protocol_score,
                "cli_only": cli_only,
                "json_discipline": json_discipline,
                "within_budget": within_budget,
                "calls": len(calls),
            }
        )

    model = run["model"]
    model_label = "/".join(
        str(model.get(key, "unknown")) for key in ("provider", "name", "version")
    )
    max_score = len(task_results) * 10
    return {
        "run_id": run["run_id"],
        "model": model_label,
        "score": sum(item["score"] for item in task_results),
        "max_score": max_score,
        "tasks": task_results,
        "telemetry": {
            "cli_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "successful_call_rate": (
                successful_calls / total_calls if total_calls else None
            ),
            "json_error_rate": json_errors / failed_calls if failed_calls else None,
            "recovered_tasks": recovered_tasks,
            "cli_duration_ms": total_duration_ms,
            "input_tokens": input_tokens if token_usage_complete else None,
            "output_tokens": output_tokens if token_usage_complete else None,
        },
        "reported_gaps": run.get("reported_gaps", []),
    }


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"


def _fmt_int(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def _markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Model | Score | CLI calls | Output tokens | Call success | "
        "JSON error contract | Recovered tasks |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in sorted(results, key=lambda item: item["score"], reverse=True):
        telemetry = result["telemetry"]
        lines.append(
            f"| {result['model']} | {result['score']:g}/{result['max_score']} | "
            f"{telemetry['cli_calls']} | "
            f"{_fmt_int(telemetry['output_tokens'])} | "
            f"{_fmt(telemetry['successful_call_rate'])} | "
            f"{_fmt(telemetry['json_error_rate'])} | "
            f"{telemetry['recovered_tasks']} |"
        )
    if len(results) == 1:
        lines.extend(
            [
                "",
                "| Task | Score | Calls | CLI only | JSON + budget |",
                "|---|---:|---:|:---:|:---:|",
            ]
        )
        for task in results[0]["tasks"]:
            json_and_budget = task["json_discipline"] and task["within_budget"]
            lines.append(
                f"| {task['id']} | {task['score']:g}/{task['max_score']} | "
                f"{task['calls']} | {'yes' if task['cli_only'] else 'no'} | "
                f"{'yes' if json_and_budget else 'no'} |"
            )
    gaps: dict[tuple[str, str], set[str]] = {}
    for result in results:
        for gap in result["reported_gaps"]:
            if not isinstance(gap, dict):
                continue
            key = (str(gap.get("capability", "unspecified")), str(gap.get("status")))
            gaps.setdefault(key, set()).add(result["model"])
    if gaps:
        lines.extend(
            [
                "",
                "| Reported capability | Status | Models |",
                "|---|---|---:|",
            ]
        )
        for (capability, status), models in sorted(gaps.items()):
            lines.append(f"| {capability} | {status} | {len(models)}/{len(results)} |")
    return "\n".join(lines)


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()

    try:
        loaded_runs = [_load(path) for path in args.runs]
        suite_ids = {run.get("suite_id") for run in loaded_runs}
        if len(suite_ids) != 1:
            raise RunError("cannot compare runs from different benchmark suites")
        suite_id = next(iter(suite_ids))
        if suite_id not in SUITE_DIRS:
            raise RunError(f"unknown benchmark suite: {suite_id!r}")
        suite_dir = SUITE_DIRS[suite_id]
        prompts = _load(suite_dir / "prompts.json")
        scoring = _load(suite_dir / "scoring.json")
        results = [
            score_run(run, prompts, scoring, allow_partial=args.allow_partial)
            for run in loaded_runs
        ]
    except (OSError, json.JSONDecodeError, RunError) as error:
        print(f"benchmark record error: {error}", file=sys.stderr)
        return 2

    if args.as_json:
        print(json.dumps(results, indent=2))
    else:
        print(_markdown(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
