"""The invocation loop: resolve mode, run the app, structure usage errors."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Sequence
from typing import Any, TextIO

from . import compat, repeat
from .builder import build_click_exception_payload, build_payload
from .config import AgentErrorsConfig, ArgvScan, resolve_format, resolve_mode, scan_argv
from .payload import ErrorPayload
from .render import render
from .skill import render_skill

KEYBOARD_INTERRUPT_EXIT = 130


def agent_errors(
    app: Any, config: AgentErrorsConfig | None = None
) -> Callable[..., Any]:
    """Wrap a Typer app; returns a zero-arg callable for ``[project.scripts]``.

    The app itself is never mutated and nothing is monkeypatched: all
    interception happens at invocation time. ``argv`` may be passed explicitly
    (tests); it defaults to ``sys.argv[1:]``.
    """
    cfg = config or AgentErrorsConfig()

    def main(argv: Sequence[str] | None = None) -> Any:
        return _run(app, cfg, list(sys.argv[1:] if argv is None else argv))

    return main


def _run(app: Any, config: AgentErrorsConfig, argv: list[str]) -> Any:
    scan = scan_argv(config, argv)
    mode = resolve_mode(config, argv, os.environ, scan=scan)
    if scan.skill_flag:
        sys.stdout.write(render_skill(app, config=config))
        sys.stdout.flush()
        sys.exit(0)
    status = compat.current()
    if mode == "human" or not status.ok:
        if mode == "agent":
            compat.warn_unsupported_once(status)
        return _passthrough(app, scan)
    return _run_agent(app, config, scan.args)


def _passthrough(app: Any, scan: ArgvScan) -> Any:
    """Human mode: Typer untouched. Only strip argv if a sentinel was present."""
    if scan.agent_flag or scan.human_flag:
        return app(scan.args)
    return app()


def _completion_requested(prog_name: str) -> bool:
    """Click's shell-completion trigger: ``_<PROG>_COMPLETE`` in the environment."""
    complete_var = f"_{prog_name}_COMPLETE".replace("-", "_").upper()
    return os.environ.get(complete_var) is not None


def _run_agent(app: Any, config: AgentErrorsConfig, args: list[str]) -> Any:
    """Click's standalone loop, with usage errors routed through our renderer.

    ``main(standalone_mode=False)`` cannot tell a command that *returned* an
    int from ``Exit(code)``, so we drive ``make_context``/``invoke`` ourselves
    and get standalone exit-code semantics exactly.
    """
    status = compat.current()
    command = compat.get_command(app)
    prog_name = compat.detect_program_name()
    if _completion_requested(prog_name):
        return command.main(args, prog_name=prog_name)
    compat.install_pretty_exceptions()
    try:
        try:
            with command.make_context(prog_name, args) as ctx:
                command.invoke(ctx)
                ctx.exit()
        except EOFError:
            sys.stderr.write("\nAborted!\n")
            sys.exit(1)
        except KeyboardInterrupt:
            sys.exit(KEYBOARD_INTERRUPT_EXIT)
        except status.get("NoArgsIsHelpError") as exc:
            _show(exc)
            sys.exit(getattr(exc, "exit_code", 2))
        except status.get("UsageError") as exc:
            usage_error = exc  # a lambda may not close over the `except` name
            _emit_or_fallback(
                usage_error,
                config,
                lambda: build_payload(
                    usage_error,
                    root=command,
                    prog_name=prog_name,
                    argv=args,
                    config=config,
                ),
                repeat_key=(prog_name, args),
            )
        except status.get("ClickException") as exc:
            if not config.intercept_click_exceptions:
                _show(exc)
                sys.exit(getattr(exc, "exit_code", 1))
            click_error = exc
            _emit_or_fallback(
                click_error,
                config,
                lambda: build_click_exception_payload(
                    click_error, command_path=prog_name
                ),
            )
    except status.get("Exit") as exc:
        sys.exit(getattr(exc, "exit_code", 0))
    except status.get("Abort"):
        sys.stderr.write("Aborted!\n")
        sys.exit(1)
    except Exception as exc:
        compat.tag_developer_exception(app, exc)
        raise


def _show(exc: Any) -> None:
    """Click's own rendering of the exception, as standalone mode would."""
    exc.show()


def _stream(config: AgentErrorsConfig) -> TextIO:
    return sys.stdout if config.stream == "stdout" else sys.stderr


def _emit_or_fallback(
    exc: Any,
    config: AgentErrorsConfig,
    build: Callable[[], ErrorPayload],
    *,
    repeat_key: tuple[str, list[str]] | None = None,
) -> None:
    """Render and write the payload; on any internal failure, show Click's own."""
    try:
        payload = build()
        if repeat_key is not None and config.repeat_detection:
            prog_name, args = repeat_key
            count = repeat.record_failure(
                prog_name, args, payload.error.type, base_dir=config.repeat_state_dir
            )
            payload = repeat.escalate(payload, count)
        text = render(payload, resolve_format(config, os.environ))
    except Exception:
        _show(exc)
        sys.exit(getattr(exc, "exit_code", 1))
    stream = _stream(config)
    stream.write(text)
    stream.flush()
    sys.exit(payload.exit_code)
