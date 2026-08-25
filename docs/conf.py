"""Sphinx configuration for the sktime-cli documentation.

Project metadata is read from the installed distribution rather than repeated
here, so the version shown on the site can never drift from the package.
"""

import sys
from datetime import date
from importlib.metadata import metadata, version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "_ext"))

_meta = metadata("sktime-cli")

project = "sktime-cli"
author = _meta["Author"] or "sktime-cli contributors"
project_copyright = f"{date.today().year}, {author} (BSD-3-Clause)"
release = version("sktime-cli")
version = release

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinxcontrib.mermaid",
    "typer_cli",
]

exclude_patterns = ["_build", "assets/generate.py", "Thumbs.db", ".DS_Store"]

# -- Markdown ---------------------------------------------------------------

myst_enable_extensions = ["colon_fence", "deflist", "substitution"]
# Render ```mermaid fences through sphinxcontrib-mermaid.
myst_fence_as_directive = ["mermaid"]
myst_heading_anchors = 3

# -- HTML output ------------------------------------------------------------

html_theme = "pydata_sphinx_theme"
html_title = f"sktime-cli {release}"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_show_sourcelink = False

_repo = "https://github.com/siddharth7113/sktime-cli"

html_theme_options = {
    "github_url": _repo,
    "show_prev_next": True,
    "navigation_with_keys": False,
    "show_toc_level": 2,
    "navbar_align": "left",
    "icon_links": [
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/sktime-cli/",
            "icon": "fa-solid fa-box",
        },
        {
            "name": "sktime",
            "url": "https://github.com/sktime/sktime",
            "icon": "fa-solid fa-chart-line",
        },
    ],
    "footer_start": ["copyright"],
    "footer_end": ["theme-version"],
}

html_context = {
    "github_user": "siddharth7113",
    "github_repo": "sktime-cli",
    "github_version": "main",
    "doc_path": "docs",
    "default_mode": "auto",
}

nitpicky = False
