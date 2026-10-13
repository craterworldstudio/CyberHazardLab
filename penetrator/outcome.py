"""Classification of terminal responses."""

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


def classify_outcome(
    output: str,
    prompt: str,
) -> CommandOutcome:
    """Classify the response without assuming that output means success."""

    lower_output = output.lower()
    lower_prompt = prompt.lower()

    if "password:" in lower_prompt or "password:" in lower_output:
        return CommandOutcome.AUTH_REQUIRED

    if output.startswith("__NANO_OPEN__"):
        return CommandOutcome.INTERACTIVE

    rejection_markers = (
        "command not found",
        "command not recognized",
        "unknown command",
        "permission denied",
    )

    if any(marker in lower_output for marker in rejection_markers):
        return CommandOutcome.COMMAND_REJECTED

    if not output.strip():
        return CommandOutcome.EMPTY

    return CommandOutcome.OUTPUT
