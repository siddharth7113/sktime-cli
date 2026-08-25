import json

import pandas as pd
import pytest

from sktime_cli._errors import CliError
from sktime_cli._output import (
    OutputFormat,
    emit_frame,
    emit_record,
    emit_table,
    resolve_format,
)


def test_resolve_format_json_flag():
    assert resolve_format(OutputFormat.auto, True) == OutputFormat.json


def test_resolve_format_conflict():
    with pytest.raises(CliError):
        resolve_format(OutputFormat.agent, True)


def test_emit_record_json(capsys):
    emit_record({"a": 1, "b": [1, 2]}, OutputFormat.json)
    assert json.loads(capsys.readouterr().out) == {"a": 1, "b": [1, 2]}


def test_emit_record_agent_tsv(capsys):
    emit_record({"a": 1, "b": "x"}, OutputFormat.agent)
    assert capsys.readouterr().out == "a\t1\nb\tx\n"


def test_emit_record_quiet(capsys):
    emit_record({"a": 1}, OutputFormat.quiet, quiet_value="only-this")
    assert capsys.readouterr().out == "only-this\n"


def test_emit_table_agent(capsys):
    emit_table([{"x": 1, "y": "a"}, {"x": 2, "y": "b"}], OutputFormat.agent)
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == ["x\ty", "1\ta", "2\tb"]


def test_emit_table_quiet_key(capsys):
    emit_table([{"x": 1}, {"x": 2}], OutputFormat.quiet, quiet_key="x")
    assert capsys.readouterr().out == "1\n2\n"


def test_emit_frame_json_period_index(capsys):
    idx = pd.period_range("2020-01", periods=3, freq="M")
    emit_frame(pd.Series([1.0, 2.0, 3.0], index=idx, name="v"), OutputFormat.json)
    payload = json.loads(capsys.readouterr().out)
    assert payload["index"] == ["2020-01", "2020-02", "2020-03"]
    assert payload["columns"] == ["v"]
    assert payload["data"] == [[1.0], [2.0], [3.0]]


@pytest.mark.parametrize(
    "field, text",
    [
        ("message", "requires missing package(s): sktime[dev]"),
        ("hint", 'uv pip install "sktime-cli[parquet]"'),
        ("detail", "ExpandingWindowSplitter(fh=[1,2,3], bogus=1)"),
    ],
)
def test_square_brackets_survive_human_error_output(capsys, field, text):
    """Rich reads [dev] as a markup tag and drops it, losing the extra."""
    from sktime_cli._output import print_error

    body = {"code": "missing_dependency", "message": "x", field: text}
    print_error({"error": body}, human=True)
    assert text in capsys.readouterr().err
