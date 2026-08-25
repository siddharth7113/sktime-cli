"""The bundled agent skill must stay where package-bundled skills are found.

Its location is a packaging detail that nothing else exercises, so a build
config change could drop it from the wheel without any other test noticing.
"""

import pathlib

import sktime_cli

SKILL = (
    pathlib.Path(sktime_cli.__file__).parent
    / ".agents"
    / "skills"
    / "sktime-cli"
    / "SKILL.md"
)


def test_skill_ships_with_the_package():
    assert SKILL.is_file()


def test_skill_has_the_frontmatter_agents_read():
    lines = SKILL.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    closing = lines.index("---", 1)
    frontmatter = lines[1:closing]
    assert "name: sktime-cli" in frontmatter
    assert any(line.startswith("description:") for line in frontmatter)
