"""Terminal API client for the Penetrator agent."""

from urllib.parse import quote

from penetrator.outcome import (
    CommandResult,
    classify_outcome,
)


class TerminalExecutor:
    """Execute terminal commands through CHL's existing API."""

    def __init__(self, api, device_name: str):
        if not device_name or not device_name.strip():
            raise ValueError("A device name is required.")

        self._api = api
        self.device_name = device_name

    def execute(self, command: str) -> CommandResult:
        """Submit one command and return its terminal response."""

        if not isinstance(command, str):
            raise TypeError("Command must be a string.")

        path = (
            "/api/ncm/devices/"
            f"{quote(self.device_name, safe='')}/terminal"
        )

        try:
            response = self._api.handle(
                "POST",
                path,
                {"command": command},
            )

            if not isinstance(response, dict):
                return self._error(
                    command,
                    "The API returned an invalid response.",
                )

            output = str(response.get("output") or "")
            prompt = str(response.get("prompt") or "")

            # The existing API represents missing devices as terminal output.
            if output == "Device not found.":
                return self._error(command, output, prompt)

            outcome = classify_outcome(
                output,
                prompt,
                api_ok=True,
            )

            return CommandResult(
                device=self.device_name,
                command=command,
                output=output,
                prompt=prompt,
                outcome=outcome,
            )

        except Exception as exc:
            # Return a controlled failure instead of crashing the agent loop.
            return self._error(
                command,
                f"{type(exc).__name__}: {exc}",
            )

    def _error(
        self,
        command: str,
        message: str,
        prompt: str = "",
    ) -> CommandResult:
        return CommandResult(
            device=self.device_name,
            command=command,
            output=message,
            prompt=prompt,
            outcome=classify_outcome(
                message,
                prompt,
                api_ok=False,
            ),
        )
