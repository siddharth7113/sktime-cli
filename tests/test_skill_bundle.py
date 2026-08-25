"""The agent skill must stay where both skill indexers and the wheel expect it.

The skill is authored at the repo root, under ``skills/``, because that is
where skill indexers and ``npx skills add`` walk. Installed users find it
through the package instead, at the path package-bundled skills are
discovered from, and the wheel build copies it there. Neither location is
exercised by anything else, so a move or a build config change could break
one of them without another test noticing.
"""

import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "sktime-cli" / "SKILL.md"
PACKAGED_AT = "sktime_cli/.agents/skills/sktime-cli/SKILL.md"


def test_skill_is_authored_where_indexers_look():
    assert SKILL.is_file()


def test_skill_has_the_frontmatter_agents_read():
    lines = SKILL.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    closing = lines.index("---", 1)
    frontmatter = lines[1:closing]
    assert "name: sktime-cli" in frontmatter
    assert any(line.startswith("description:") for line in frontmatter)


def test_the_wheel_still_carries_the_skill_into_the_package():
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    mapping = f'"skills/sktime-cli/SKILL.md" = "{PACKAGED_AT}"'
    assert mapping in pyproject
