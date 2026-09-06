"""§12 SKILL.md emitter (spec test 18)."""

from __future__ import annotations

import typer

from typer_agentic import AgentErrorsConfig, render_skill, wording

from . import fixture_app
from .conftest import VENDORED_CLICK, CliResult, golden


def _frontmatter(text: str) -> dict[str, str]:
    assert text.startswith("---\n")
    block = text.split("---\n")[1]
    pairs = (line.split(": ", 1) for line in block.strip().splitlines())
    return {k: v.strip('"') for k, v in pairs}


def test_flag_prints_skill_and_exits_zero(run) -> None:
    result: CliResult = run(["--agent-skill"])
    assert result.code == 0
    assert result.err == ""
    assert result.out == render_skill(fixture_app.app, prog_name="myapp")
    if VENDORED_CLICK:
        golden("SKILL.md", result.out)


def test_flag_works_even_with_broken_argv(run) -> None:
    result: CliResult = run(["sync", "--verbos", "--agent-skill"])
    assert result.code == 0
    assert result.out.startswith("---\n")


def test_frontmatter_and_inventory() -> None:
    text = render_skill(fixture_app.app, prog_name="myapp")
    meta = _frontmatter(text)
    assert meta == {"name": "myapp", "description": "Demo tool for tests."}
    assert "### myapp sync" in text
    assert "--verbose, -v" in text
    assert "--count        INTEGER" in text
    assert "--env          CHOICE[dev|prod]" in text
    assert "--secret" not in text
    assert "--help" not in text
    assert text.count("```") == 2 * 6, "one fenced example per command"
    assert wording.CLASSIFICATION in text and wording.DIRECTIVE in text
    assert wording.EXAMPLE_NOTE in text


def test_custom_name_description_and_quoting() -> None:
    text = render_skill(
        fixture_app.app, name="my-tool", description='Say "hi"', prog_name="myapp"
    )
    assert 'name: "my-tool"' in text
    assert 'description: "Say \\"hi\\""' in text


def test_frontmatter_escapes_newlines() -> None:
    text = render_skill(fixture_app.app, name="a\nb", prog_name="myapp")
    assert 'name: "a\\nb"' in text
    assert text.split("---\n")[1].count("\n") == 2


def test_hidden_included_when_configured() -> None:
    text = render_skill(
        fixture_app.app,
        config=AgentErrorsConfig(include_hidden=True),
        prog_name="myapp",
    )
    assert "--secret" in text


def test_nested_groups_and_budget() -> None:
    app = typer.Typer(help="Big app.")
    group = typer.Typer(help="Group.")
    app.add_typer(group, name="grp")
    for i in range(11):

        def _cmd() -> None:
            """Numbered."""

        group.command(name=f"c{i}")(_cmd)
    text = render_skill(app, prog_name="big")
    assert "This CLI has 11 commands" in text
    assert "  big grp c10  Numbered." in text
    assert "```" not in text
    assert len(text.splitlines()) < 200


def test_single_command_app() -> None:
    app = typer.Typer()

    @app.command()
    def only(name: str) -> None:
        """Only one."""

    text = render_skill(app, prog_name="solo")
    assert "### solo" in text
    assert "solo VALUE" in text
    assert 'description: "Only one."' in text


def test_description_fallback_without_help() -> None:
    app = typer.Typer()

    @app.command()
    def a() -> None:
        pass

    @app.command()
    def b() -> None:
        pass

    text = render_skill(app, prog_name="solo")
    assert 'description: "Use the solo CLI."' in text
    assert "Use `solo` for the commands listed below." in text
