"""§6.2/§6.3 renderers and §7 invariants (spec tests 1, 14, 15)."""

from __future__ import annotations

import json
import re

import pytest

from typer_agentic import AgentErrorsConfig, render_json, render_markdown, wording
from typer_agentic.payload import ErrorInfo, ErrorPayload, OptionInfo, RecoveryCopy

from .conftest import VENDORED_CLICK, CliResult, golden, golden_only

CASES = {
    "no_such_option.md": ["sync", "--verbos"],
    "bad_choice.md": ["sync", "./x", "--env", "prd"],
    "missing_argument.md": ["sync"],
    "no_such_command.md": ["synk"],
    "bad_integer.md": ["sync", "./x", "--count", "abc"],
    "extra_argument.md": ["sync", "./x", "extra"],
    "option_requires_value.md": ["sync", "./x", "--count"],
}


@golden_only
@pytest.mark.parametrize(("name", "argv"), list(CASES.items()), ids=list(CASES))
def test_markdown_golden(run, agent, name: str, argv: list[str]) -> None:
    result: CliResult = run(argv, config=agent)
    assert result.code == 2
    golden(name, result.err)


@pytest.mark.parametrize(("name", "argv"), list(CASES.items()), ids=list(CASES))
def test_deescalation_invariants(run, agent, name: str, argv: list[str]) -> None:
    text: str = run(argv, config=agent).err
    assert text.startswith("✗ Usage error in `myapp")
    assert wording.CLASSIFICATION in text
    assert wording.DIRECTIVE in text
    assert text.count("```") == 2, "exactly one fenced example"
    framing = text.split("\n\n")[1]
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", framing.strip()) if s]
    assert len(sentences) <= 2
    assert "!" not in text.replace("✗", "")
    assert "please" not in text.lower()
    assert "Full reference: myapp" in text.splitlines()[-1]
    assert not re.search(r"\x1b\[|[─│╭╮╰╯]", text), "no ANSI, no box drawing"


def test_no_such_option_specifics(run, agent) -> None:
    text: str = run(["sync", "--verbos"], config=agent).err
    assert "Did you mean: --verbose\n" in text
    assert (
        "--no-verbose" not in text.split("Did you mean")[1].split("\n", maxsplit=1)[0]
    )
    assert "\n```\nmyapp sync ./PATH --verbose\n```\n" in text
    assert "CHOICE[dev|prod]" in text
    assert "INTEGER" in text
    assert "Required arguments: PATH" in text
    assert len(text.splitlines()) <= 30


def test_json_parseable_with_schema_fields(run) -> None:
    cfg = AgentErrorsConfig(mode="agent")
    result: CliResult = run(
        ["sync", "--verbos"], config=cfg, env={"AGENT_ERRORS_FORMAT": "json"}
    )
    assert result.code == 2
    assert result.err.endswith("}\n")
    data = json.loads(result.err)
    assert data["schema"] == "typer-agentic/v1"
    assert data["error"]["type"] == "no_such_option"
    assert "--verbos" in data["error"]["message"]
    assert data["error"]["offending"] == "--verbos"
    assert data["error"]["param"] is None
    assert data["suggestions"][0] == "--verbose"
    assert data["command_path"] == "myapp sync"
    assert data["exit_code"] == 2
    assert data["example"] == "myapp sync ./PATH --verbose"
    assert set(data["recovery"]) == {
        "classification",
        "directive",
        "action",
        "escalation",
    }
    assert set(data) == {
        "schema",
        "error",
        "command_path",
        "suggestions",
        "valid_arguments",
        "valid_options",
        "subcommands",
        "example",
        "recovery",
        "exit_code",
    }
    if VENDORED_CLICK:
        golden("no_such_option.json", result.err)


def test_json_config_format(run) -> None:
    result: CliResult = run(
        ["sync"], config=AgentErrorsConfig(mode="agent", format="json")
    )
    assert json.loads(result.err)["error"]["type"] == "missing_parameter"


def _payload(options: list[OptionInfo], suggestions: list[str] = []) -> ErrorPayload:
    return ErrorPayload(
        error=ErrorInfo(
            type="no_such_option", message="No such option: --x", offending="--x"
        ),
        command_path="app cmd",
        recovery=RecoveryCopy(wording.CLASSIFICATION, wording.DIRECTIVE, "Do it."),
        exit_code=2,
        suggestions=suggestions,
        valid_options=options,
    )


def test_markdown_truncates_long_option_lists() -> None:
    options = [
        OptionInfo(
            names=[f"--opt{i:02d}"],
            type="TEXT",
            required=False,
            primary=[f"--opt{i:02d}"],
        )
        for i in range(25)
    ]
    options.append(
        OptionInfo(names=["--must"], type="TEXT", required=True, primary=["--must"])
    )
    text = render_markdown(_payload(options, ["--opt24"]))
    lines = [line for line in text.splitlines() if line.startswith("  --")]
    assert len(lines) == 20
    assert lines[0].startswith("  --opt24")
    assert lines[1].startswith("  --must")
    assert "…and 6 more — run 'app cmd --help'" in text


def test_markdown_omits_empty_sections_and_example() -> None:
    payload = ErrorPayload(
        error=ErrorInfo(type="usage_error", message="custom"),
        command_path="app",
        recovery=RecoveryCopy(
            wording.CLASSIFICATION, wording.DIRECTIVE, "Run 'app --help'."
        ),
        exit_code=2,
    )
    text = render_markdown(payload)
    assert "Valid options" not in text
    assert "```" not in text
    assert text.endswith("Full reference: app --help\n")


def test_json_matches_to_dict() -> None:
    payload = _payload([])
    assert json.loads(render_json(payload)) == payload.to_dict()
