"""§12 SKILL.md emitter (spec test 18)."""

from __future__ import annotations

import typer

from typer_agentic import AgentErrorsConfig, render_skill, wording

from . import fixture_app
from .conftest import CliResult, golden, golden_only


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


@golden_only
def test_skill_golden(run) -> None:
    golden("SKILL.md", run(["--agent-skill"]).out)


def test_flag_works_even_with_broken_argv(run) -> None:
    result: CliResult = run(["sync", "--verbos", "--agent-skill"])
    assert result.code == 0
    assert result.out.startswith("---\n")


def test_frontmatter_and_inventory() -> None:
    text = render_skill(fixture_app.app, prog_name="myapp")
    meta = _frontmatter(text)
    assert meta == {"name": "myapp", "description": "Demo tool for tests."}, (
        "frontmatter"
    )
    assert "### myapp sync" in text, "command heading"
    assert "--verbose, -v" in text, "all option names"
    assert "--count        INTEGER" in text, "aligned type column"
    assert "--env          CHOICE[dev|prod]" in text, "choices rendered"
    assert "--secret" not in text, "hidden option excluded"
    assert "--help" not in text, "built-in help excluded"
    assert text.count("```") == 2 * 6, "one fenced example per command"
    assert wording.CLASSIFICATION in text and wording.DIRECTIVE in text, "copy"
    assert wording.EXAMPLE_NOTE in text, "example note"


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


def _big_app(commands: int = 11) -> typer.Typer:
    app = typer.Typer(help="Big app.")
    group = typer.Typer(help="Group.")
    app.add_typer(group, name="grp")
    for i in range(commands):

        def _cmd(name: str, count: int = typer.Option(1, help="How many.")) -> None:
            """Numbered.

            A longer body that only fits when the CLI is small.
            """

        group.command(name=f"c{i}")(_cmd)
    return app


def test_above_cap_keeps_inventory_per_command() -> None:
    text = render_skill(_big_app(), prog_name="big")
    assert "### big grp c10" in text
    assert "  NAME  TEXT  required" in text
    assert "  --count  INTEGER  How many." in text
    assert text.count("```") == 2 * 11, "one fenced example per command"


def test_above_cap_trims_help_to_first_line() -> None:
    text = render_skill(_big_app(), prog_name="big")
    assert "Numbered." in text
    assert "A longer body" not in text


def test_help_body_kept_below_cap() -> None:
    app = typer.Typer()

    @app.command()
    def one() -> None:
        """First line.

        Body paragraph.
        """

    text = render_skill(app, prog_name="small")
    assert "First line." in text
    assert "Body paragraph." in text


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
