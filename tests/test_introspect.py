"""§6.1 inventory (spec tests 3, 4, 13) and helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from typer_agentic import AgentErrorsConfig, introspect
from typer_agentic.compat import get_command

from . import fixture_app


def test_missing_argument(json_payload) -> None:
    data = json_payload(["sync"])
    assert data["error"]["type"] == "missing_parameter"
    assert data["error"]["param"] == "path"
    assert "'path'" in data["recovery"]["action"]
    assert "./PATH" in data["example"]
    [arg] = data["valid_arguments"]
    assert arg["help"] in ("Where to sync.", None)  # Typer < 0.26 drops argument help
    del arg["help"]
    assert arg == {
        "name": "path",
        "metavar": "PATH",
        "type": "PATH",
        "required": True,
        "nargs": 1,
        "choices": None,
    }


def test_bad_integer(json_payload) -> None:
    data = json_payload(["sync", "./x", "--count", "abc"])
    assert data["error"]["type"] == "bad_parameter"
    assert data["error"]["offending"] == "abc"
    assert data["error"]["param"] == "count"
    count = next(o for o in data["valid_options"] if "--count" in o["names"])
    assert count["type"] == "INTEGER"
    assert count["default"] == 1
    assert data["example"] == "myapp sync ./PATH --count 1"


def test_hidden_option_excluded_by_default(json_payload) -> None:
    data = json_payload(["sync"])
    names = [n for o in data["valid_options"] for n in o["names"]]
    assert "--secret" not in names
    assert "--help" not in names
    assert "--install-completion" not in names


def test_hidden_option_included_when_configured(json_payload) -> None:
    cfg = AgentErrorsConfig(mode="agent", format="json", include_hidden=True)
    data = json_payload(["sync"], config=cfg)
    names = [n for o in data["valid_options"] for n in o["names"]]
    assert "--secret" in names


def test_option_shapes(json_payload) -> None:
    data = json_payload(["sync"])
    by_name = {o["names"][0]: o for o in data["valid_options"]}
    assert by_name["--verbose"]["names"] == ["--verbose", "-v"]
    assert by_name["--verbose"]["is_flag"] is True
    assert by_name["--env"] == {
        "names": ["--env"],
        "type": "CHOICE",
        "required": False,
        "default": "dev",
        "multiple": False,
        "is_flag": False,
        "choices": ["dev", "prod"],
        "help": "Target environment.",
        "nargs": 1,
    }


def test_multiple_option_and_no_flag_pairs() -> None:
    app = typer.Typer()

    @app.command()
    def cmd(
        tags: list[str] = typer.Option([]),
        color: bool = typer.Option(True, "--color/--no-color"),
        where: Path = typer.Option(..., help="Required path."),
    ) -> None:
        """Doc."""

    _, options = introspect.inventory(get_command(app), AgentErrorsConfig())
    by_name = {o.names[0]: o for o in options}
    assert by_name["--tags"].multiple is True
    assert by_name["--tags"].default == []
    assert by_name["--color"].names == ["--color", "--no-color"]
    assert by_name["--color"].primary == ["--color"]
    assert by_name["--where"].required is True
    assert by_name["--where"].default is None
    assert by_name["--where"].type == "PATH"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("int", "INTEGER"),
        ("integer", "INTEGER"),
        ("str", "TEXT"),
        ("text", "TEXT"),
        ("boolean", "BOOL"),
        ("choice", "CHOICE"),
        ("filename", "FILE"),
        ("int range", "INTEGER RANGE"),
        ("uuid", "UUID"),
    ],
)
def test_normalise_type_name(raw: str, expected: str) -> None:
    class Fake:
        name = raw

    assert introspect.normalise_type_name(Fake()) == expected


def test_sanitise_default_variants() -> None:
    assert introspect._sanitise(Ellipsis) is None
    assert introspect._sanitise(lambda: 1) is None
    assert introspect._sanitise(Path("a/b")) == "a/b"
    assert introspect._sanitise((1, "x")) == [1, "x"]
    assert introspect._sanitise(object()).startswith("<object")


def test_subcommands_list_visible_only() -> None:
    app = typer.Typer()
    sub = typer.Typer(help="Sub group.")
    app.add_typer(sub, name="sub")

    @app.command(hidden=True)
    def secret() -> None:
        """Hidden."""

    @app.command()
    def shown() -> None:
        """Shown one."""

    subs = introspect.subcommands(get_command(app))
    assert [s.name for s in subs] == ["shown", "sub"]
    assert subs[0].help == "Shown one."


def test_resolve_from_argv_walks_groups() -> None:
    root = get_command(fixture_app.app)
    command, path = introspect.resolve_from_argv(root, "myapp", ["--x", "sync", "./p"])
    assert path == "myapp sync"
    assert command.name == "sync"
    command, path = introspect.resolve_from_argv(root, "myapp", ["nope"])
    assert path == "myapp"
    assert command is root
