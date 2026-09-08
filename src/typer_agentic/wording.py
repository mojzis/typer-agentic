"""Every agent-facing string (the "copy"), in one place.

Tone rules (normative): calm, imperative, concrete. No exclamation marks,
no apologies, no "please". The classification and directive sentences are
identical for every error type so that models can key on them across turns.
"""

from __future__ import annotations

CLASSIFICATION = "This is a recoverable input mistake, not a bug in the tool."
"""One sentence framing the failure as fixable input, not a broken tool."""

DIRECTIVE = (
    "Do not switch tools, edit files or state to work around it, or invent flags; "
    "apply the one change below and re-run the command."
)
"""One sentence naming and forbidding the panic behaviours."""

EXAMPLE_NOTE = "The error block always contains exactly one corrected example; run it."

HEADER = "✗ Usage error in `{command_path}`: {message}"
FOOTER = "Full reference: {command_path} --help"
DID_YOU_MEAN = "Did you mean: {best}"
FIX_HEADING = "Fix and retry (one change): {action}"
OPTIONS_HEADING = "Valid options:"
ARGUMENTS_HEADING = "Required arguments: {names}"
OPTIONAL_ARGUMENTS_HEADING = "Optional arguments: {names}"
SUBCOMMANDS_HEADING = "Valid subcommands:"
OPTIONS_TRUNCATED = "  …and {count} more — run '{command_path} --help'"

ACTION_NO_SUCH_OPTION = "Replace '{offending}' with '{best}'."
ACTION_MISSING_PARAMETER = "Add the required {kind} '{param}'."
ACTION_BAD_PARAMETER_CHOICES = "Use one of: {choices}."
ACTION_BAD_PARAMETER = "Give '{param}' a valid {type} value."
ACTION_NO_SUCH_COMMAND = "Use the subcommand '{best}'."
ACTION_MISSING_COMMAND = "Add one of the subcommands listed below."
ACTION_BAD_OPTION_USAGE = "Fix how '{offending}' is used, then retry."
ACTION_BAD_ARGUMENT_USAGE = "Pass only the arguments listed below."
ACTION_HELP_FALLBACK = (
    "Run '{command_path} --help' and retry with a flag from its output."
)
ACTION_EXAMPLE_SUFFIX = " Run the corrected example."
ACTION_CLICK_EXCEPTION = "Read the message above, adjust the input, and retry."

ESCALATION_SECOND = (
    "Second identical failure. Stop retrying variations. Run "
    "`{command_path} --help`, read the option list, then construct the command "
    "fresh from the example below."
)
ESCALATION_THIRD = (
    ESCALATION_SECOND
    + " If `--help` does not resolve this, report the exact error above to the "
    "user instead of working around it."
)

SKILL_WHEN_TO_USE = "## When to use"
SKILL_COMMANDS = "## Commands"
SKILL_ON_ERRORS = "## On usage errors"
