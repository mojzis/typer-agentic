"""§6.1 inventory (spec tests 3, 4, 13) and helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from typer_agentic import AgentErrorsConfig, introspect
from typer_agentic.compat import get_command
from typer_agentic.payload import OptionInfo, RangeInfo

from . import fixture_app


def test_missing_argument(json_payload) -> None:
    data = json_payload(["sync"])
    assert data["error"]["type"] == "missing_parameter", "error type"
    assert data["error"]["param"] == "path", "canonical param name"
    assert "'path'" in data["recovery"]["action"], "action names the param"
    assert "./PATH" in data["example"], "example fills the missing argument"
    [arg] = data["valid_arguments"]
    # Typer < 0.26 drops argument help
    assert arg["help"] in ("Where to sync.", None), "argument help"
    del arg["help"]
    assert arg == {
        "name": "path",
        "metavar": "PATH",
        "type": "PATH",
        "required": True,
        "nargs": 1,
        "choices": None,
        "range": None,
    }


def test_bad_integer(json_payload) -> None:
    data = json_payload(["sync", "./x", "--count", "abc"])
    assert data["error"]["type"] == "bad_parameter", "error type"
    assert data["error"]["offending"] == "abc", "offending value"
    assert data["error"]["param"] == "count", "canonical param name"
    count = next(o for o in data["valid_options"] if "--count" in o["names"])
    assert count["type"] == "INTEGER", "normalised type"
    assert count["default"] == 1, "default carried"
    assert data["example"] == "myapp sync ./PATH --count 1", "example uses placeholder"


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
        "range": None,
    }


def test_range_bounds_are_captured(json_payload) -> None:
    data = json_payload(["push", "x", "--retries", "9"])
    retries = next(o for o in data["valid_options"] if "--retries" in o["names"])
    assert retries["type"] == "INTEGER RANGE"
    assert retries["range"] == {
        "min": 0,
        "max": 5,
        "min_open": False,
        "max_open": False,
    }


def test_bad_range_value_names_bounds_and_example_is_in_range(json_payload) -> None:
    data = json_payload(["push", "x", "--retries", "9"])
    assert data["error"]["type"] == "bad_parameter"
    assert "valid INTEGER[0..5] value" in data["recovery"]["action"]
    assert data["example"] == "myapp push VALUE --retries 0"


def _ranged_options() -> dict[str, OptionInfo]:
    app = typer.Typer()

    @app.command()
    def cmd(
        days: int = typer.Option(1, min=1),
        ratio: float = typer.Option(0.5, min=0.0, max=1.0),
        plain: int = typer.Option(0),
    ) -> None:
        """Doc."""

    _, options = introspect.inventory(get_command(app), AgentErrorsConfig())
    return {o.names[0]: o for o in options}


def test_range_info_open_upper_bound() -> None:
    assert _ranged_options()["--days"].range == RangeInfo(min=1)


def test_range_info_float_bounds() -> None:
    ratio = _ranged_options()["--ratio"]
    assert (ratio.type, ratio.range) == ("FLOAT RANGE", RangeInfo(min=0.0, max=1.0))


def test_range_info_absent_for_plain_int() -> None:
    assert _ranged_options()["--plain"].range is None


def test_range_of_reads_open_bounds() -> None:
    open_below = SimpleNamespace(
        name="int range", min=1, max=None, min_open=True, max_open=False
    )
    assert introspect.range_of(SimpleNamespace(type=open_below)) == RangeInfo(
        min=1, min_open=True
    )


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
    assert by_name["--tags"].multiple is True, "list option is multiple"
    assert by_name["--tags"].default == [], "list default"
    assert by_name["--color"].names == ["--color", "--no-color"], "both flag names"
    assert by_name["--color"].primary == ["--color"], "secondary excluded from primary"
    assert by_name["--where"].required is True, "Ellipsis default means required"
    assert by_name["--where"].default is None, "required option has no default"
    assert by_name["--where"].type == "PATH", "Path type normalised"


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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Ellipsis, None),
        (lambda: 1, None),
        (Path("a/b"), "a/b"),
        ((1, "x"), [1, "x"]),
    ],
)
def test_sanitise_default_variants(value: object, expected: object) -> None:
    assert introspect._sanitise(value) == expected


def test_sanitise_default_falls_back_to_repr() -> None:
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
