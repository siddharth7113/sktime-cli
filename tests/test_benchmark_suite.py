import copy
import json
from pathlib import Path
from runpy import run_path

ROOT = Path(__file__).parents[1]
score_run = run_path(ROOT / "benchmarks" / "score.py")["score_run"]


def _load(name):
    return json.loads((ROOT / "benchmarks" / name).read_text())


def _load_hard(name):
    return json.loads((ROOT / "benchmarks" / "hard" / name).read_text())


def test_fixed_suite_and_scoring_are_aligned():
    prompts = _load("prompts.json")
    scoring = _load("scoring.json")
    schema = _load("run.schema.json")
    prompt_ids = [task["id"] for task in prompts["tasks"]]
    scoring_ids = [task["id"] for task in scoring["tasks"]]

    assert prompt_ids == [f"B{index:02d}" for index in range(1, 11)]
    assert scoring_ids == prompt_ids
    assert prompts["suite_id"] in schema["properties"]["suite_id"]["enum"]
    assert all(task["max_cli_calls"] > 0 for task in prompts["tasks"])
    assert all(
        sum(item["points"] for item in task["criteria"]) == 8
        for task in scoring["tasks"]
    )


def test_fixture_setup_uses_only_json_sktime_cli_calls():
    prompts = _load("prompts.json")
    for task in prompts["tasks"]:
        for argv in task["setup"]:
            assert argv[0] == "sktime-cli"
            assert "--json" in argv


def test_every_task_has_a_reviewer_detail_file():
    prompts = _load("prompts.json")
    details = ROOT / "benchmarks" / "tasks"

    assert (details / "README.md").is_file()
    assert {path.stem for path in details.glob("B*.md")} == {
        task["id"] for task in prompts["tasks"]
    }
    for task in prompts["tasks"]:
        text = (details / f"{task['id']}.md").read_text()
        assert text.startswith(f"# {task['id']} — {task['title']}")
        assert "Reviewer-only" in text


def test_hard_suite_is_end_to_end_and_documented():
    prompts = _load_hard("prompts.json")
    scoring = _load_hard("scoring.json")
    details = ROOT / "benchmarks" / "hard" / "tasks"
    prompt_ids = [task["id"] for task in prompts["tasks"]]

    assert prompt_ids == [f"H{index:02d}" for index in range(1, 7)]
    assert [task["id"] for task in scoring["tasks"]] == prompt_ids
    assert all(task["max_cli_calls"] >= 9 for task in prompts["tasks"])
    assert all(
        sum(item["points"] for item in task["criteria"]) == 8
        for task in scoring["tasks"]
    )
    assert {path.stem for path in details.glob("H*.md")} == set(prompt_ids)
    for task in prompts["tasks"]:
        text = (details / f"{task['id']}.md").read_text()
        assert text.startswith(f"# {task['id']} — {task['title']}")
        assert "Reviewer-only" in text
        for argv in task["setup"]:
            assert argv[0] == "sktime-cli"
            assert "--json" in argv


def test_scorer_combines_manual_and_protocol_points():
    prompts = _load("prompts.json")
    scoring = _load("scoring.json")
    run = _load("run.template.json")
    run["run_id"] = "test"
    run["skill"]["sha256"] = "1" * 64
    run["complete_tool_trace"] = True
    run["tasks"] = []

    for task in scoring["tasks"]:
        run["tasks"].append(
            {
                "id": task["id"],
                "assistant_messages": [],
                "tool_calls": [
                    {
                        "kind": "command",
                        "argv": ["sktime-cli", "version", "--json"],
                        "stdout": "{}",
                        "stderr": "",
                        "exit_code": 0,
                        "duration_ms": 1,
                    }
                ],
                "final_answer": "reviewed separately",
                "judgments": [
                    {
                        "criterion_id": criterion["id"],
                        "earned": 2,
                        "notes": "test",
                    }
                    for criterion in task["criteria"]
                ],
            }
        )

    result = score_run(run, prompts, scoring)
    assert result["score"] == 100
    assert result["max_score"] == 100

    violated = copy.deepcopy(run)
    violated["tasks"][0]["tool_calls"][0] = {
        "kind": "other",
        "name": "python",
        "input": "import sktime",
        "output": "",
    }
    result = score_run(violated, prompts, scoring)
    assert result["tasks"][0]["score"] == 0


def test_scorer_accepts_a_partial_hard_suite_run():
    prompts = _load_hard("prompts.json")
    scoring = _load_hard("scoring.json")
    run = _load_hard("run.template.json")
    run["run_id"] = "hard-test"
    run["skill"]["sha256"] = "1" * 64
    run["complete_tool_trace"] = True
    run["tasks"] = [
        {
            "id": "H01",
            "assistant_messages": [],
            "tool_calls": [
                {
                    "kind": "command",
                    "argv": ["sktime-cli", "version", "--json"],
                    "stdout": "{}",
                    "stderr": "",
                    "exit_code": 0,
                    "duration_ms": 1,
                }
            ],
            "final_answer": "reviewed separately",
            "judgments": [
                {
                    "criterion_id": criterion["id"],
                    "earned": 2,
                    "notes": "test",
                }
                for criterion in scoring["tasks"][0]["criteria"]
            ],
        }
    ]

    result = score_run(run, prompts, scoring, allow_partial=True)
    assert result["score"] == 10
    assert result["max_score"] == 10
