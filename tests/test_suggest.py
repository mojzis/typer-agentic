"""§8 ranking and §9 examples (spec tests 2, 5, 6)."""

from __future__ import annotations

from typer_agentic import AgentErrorsConfig, suggest
from typer_agentic.example import Fix, build_example
from typer_agentic.payload import ArgumentInfo, OptionInfo


def test_unknown_subcommand(json_payload) -> None:
    data = json_payload(["synk"])
    assert data["error"]["type"] == "no_such_command"
    assert data["error"]["offending"] == "synk"
    assert data["suggestions"][0] == "sync"
    assert data["example"] == "myapp sync"
    assert [s["name"] for s in data["subcommands"]][:3] == ["sync", "push", "fail"]
    assert "Did you mean" not in data["error"]["message"]


def test_bad_choice(json_payload) -> None:
    data = json_payload(["sync", "./x", "--env", "prd"])
    assert data["error"]["type"] == "bad_parameter"
    assert data["suggestions"] == ["prod"]
    assert data["example"] == "myapp sync ./PATH --env prod"
    assert "dev, prod" in data["recovery"]["action"]


def test_bad_choice_no_close_match_has_no_suggestions(json_payload, run) -> None:
    data = json_payload(["sync", "./x", "--env", "zzz"])
    assert data["suggestions"] == []
    assert data["example"] == "myapp sync ./PATH --env dev"
    assert "dev, prod" in data["recovery"]["action"]
    text = run(
        ["sync", "./x", "--env", "zzz"], config=AgentErrorsConfig(mode="agent")
    ).err
    assert "Did you mean" not in text


def test_extra_argument(json_payload) -> None:
    data = json_payload(["sync", "./x", "extra"])
    assert data["error"]["type"] == "bad_argument_usage"
    assert data["error"]["offending"] == "extra"
    assert data["example"] == "myapp sync ./PATH"


def test_missing_command(json_payload) -> None:
    data = json_payload([])
    assert data["error"]["type"] == "missing_command"
    assert data["example"] == "myapp sync"
    assert data["subcommands"][0] == {"name": "sync", "help": "Sync a path."}
    assert "subcommands listed below" in data["recovery"]["action"]


def test_rank_prefers_primary_and_typer_possibilities() -> None:
    names = ["--verbose", "--no-verbose", "-v", "--version"]
    ranked = suggest.rank(
        "--verbos",
        names,
        possibilities=["--no-verbose"],
        primary={"--verbose", "-v", "--version"},
    )
    assert ranked[0] == "--verbose"
    assert "--no-verbose" in ranked
    assert len(ranked) <= 3


def test_rank_case_insensitive_fallback() -> None:
    assert suggest.rank("--ENV", ["--env", "--count"]) == ["--env"]


def test_rank_no_match() -> None:
    assert suggest.rank("--zzzzzz", ["--env", "--count"]) == []


def test_rank_limit() -> None:
    names = [f"--opt{i}" for i in range(10)]
    assert len(suggest.rank("--opt", names, limit=2)) == 2


def _opt(name: str, type_: str = "TEXT", *, required: bool = False, **kw) -> OptionInfo:
    return OptionInfo(names=[name], type=type_, required=required, primary=[name], **kw)


def test_example_placeholders() -> None:
    args = [
        ArgumentInfo("n", "N", "INTEGER", True, 1),
        ArgumentInfo("f", "F", "FLOAT", True, 2),
        ArgumentInfo("opt", "OPT", "TEXT", False, 1),
    ]
    options = [
        _opt("--req", "UUID", required=True),
        _opt("--flag", "BOOL", is_flag=True),
        _opt("--many", "TEXT", multiple=True, required=True),
        _opt("--dt", "DATETIME"),
    ]
    assert build_example("app run", args, options) == (
        "app run 1 1.0 1.0 --req 00000000-0000-0000-0000-000000000000 --many VALUE --many VALUE"
    )
    assert build_example("app run", [], options, fix=Fix(options[1])) == (
        "app run --req 00000000-0000-0000-0000-000000000000 --flag --many VALUE --many VALUE"
    )
    assert (
        build_example("app", [], [], fix=Fix(options[3], "2020-02-02"))
        == "app --dt 2020-02-02"
    )


def test_option_tokens_nargs() -> None:
    opt = _opt("--pair", "INTEGER", nargs=2)
    assert build_example("app", [], [], fix=Fix(opt)) == "app --pair 1 1"


def test_example_variadic_argument_and_extra() -> None:
    args = [ArgumentInfo("files", "FILES", "PATH", True, -1)]
    assert build_example("app", args, [], extra=["--go"]) == "app ./PATH ./PATH --go"
