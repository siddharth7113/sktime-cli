# sktime-cli documentation

Internal documentation for contributors and the terminally curious. If you
just want to *use* the CLI, start with the [project README](../README.md);
if you are wiring it into an agent, read the
[agent skill](../skills/sktime-cli/SKILL.md).

| Document | Contents |
|---|---|
| [architecture.md](architecture.md) | Repository layout, module map, dependency layering, the life of a command |
| [design.md](design.md) | Design decisions and their rationale: state model, output contract, error model, spec engine, caching, data IO |
| [cli-reference.md](cli-reference.md) | The full command tree with options and environment variables |

## Regenerating the README screenshots

The terminal captures in the README are SVGs generated from real CLI runs
(the hero image carries a CSS animation that replays the session). After
changing CLI output, regenerate them with:

```bash
uv run python docs/assets/generate.py
```
