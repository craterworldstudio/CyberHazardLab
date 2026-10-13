"""Classification of terminal API responses."""

from dataclasses import dataclass
from enum import Enum


class CommandOutcome(Enum):
    OUTPUT = "output"
    EMPTY = "empty"
    AUTH_REQUIRED = "auth_required"
    INTERACTIVE = "interactive"
    COMMAND_REJECTED = "command_rejected"
    API_ERROR = "api_error"


@dataclass(frozen=True)
class CommandResult:
    device: str
    command: str
    output: str
    prompt: str
    outcome: CommandOutcome

    @property
    def has_output(self) -> bool:
        return bool(self.output.strip())


def classify_outcome(
    output: str,
    prompt: str,
    *,
    api_ok: bool = True,
) -> CommandOutcome:
    """Classify a terminal response without claiming semantic success."""

    if not api_ok:
        return CommandOutcome.API_ERROR

    output = output or ""
    prompt = prompt or ""

    lower_output = output.lower()
    lower_prompt = prompt.lower()

    if "password:" in lower_prompt or "password:" in lower_output:
        return CommandOutcome.AUTH_REQUIRED

    if output.startswith("__NANO_OPEN__"):
        return CommandOutcome.INTERACTIVE

    if any(
        marker in lower_output
        for marker in (
            "command not found",
            "command not recognized",
            "unknown command",
            "not recognized as an internal",
        )
    ):
        return CommandOutcome.COMMAND_REJECTED

    if not output.strip():
        return CommandOutcome.EMPTY

    return CommandOutcome.OUTPUT
