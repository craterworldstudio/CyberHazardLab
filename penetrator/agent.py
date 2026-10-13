"""Penetrator agent foundation."""

from penetrator.executor import TerminalExecutor
from penetrator.outcome import CommandResult


class PenetratorAgent:
    """An agent that interacts with CHL through a terminal API."""

    def __init__(self, api, device_name: str):
        self.executor = TerminalExecutor(api, device_name)
        self.device_name = device_name
        self.history: list[CommandResult] = []

    def observe_prompt(self) -> str:
        """Retrieve the assigned device's current terminal prompt."""

        from urllib.parse import quote

        path = (
            "/api/ncm/devices/"
            f"{quote(self.device_name, safe='')}/terminal"
        )

        response = self.executor._api.handle("GET", path, {})

        if not isinstance(response, dict):
            raise RuntimeError("The terminal API returned an invalid response.")

        if "prompt" not in response:
            raise RuntimeError(
                response.get("output", "Could not retrieve terminal prompt.")
            )

        return str(response["prompt"])

    def execute(self, command: str) -> CommandResult:
        """Execute a command and record its result."""

        result = self.executor.execute(command)
        self.history.append(result)
        return result

    def get_history(self) -> tuple[CommandResult, ...]:
        """Return an immutable view of recorded command results."""

        return tuple(self.history)
