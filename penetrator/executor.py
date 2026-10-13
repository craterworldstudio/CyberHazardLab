"""HTTP client for the Cyber Hazard Lab terminal API."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from penetrator.outcome import CommandOutcome, CommandResult, classify_outcome


class TerminalExecutor:
    """Send terminal commands to a running CHL instance."""

    def __init__(
        self,
        base_url: str,
        device_name: str,
        timeout: float = 10.0,
    ):
        if not device_name.strip():
            raise ValueError("A device name is required.")

        self.base_url = base_url.rstrip("/")
        self.device_name = device_name
        self.timeout = timeout

    @property
    def terminal_url(self) -> str:
        device = quote(self.device_name, safe="")
        return f"{self.base_url}/api/ncm/devices/{device}/terminal"

    def _request(self, method: str, payload: dict | None = None) -> dict:
        data = None

        headers = {"Accept": "application/json"}

        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            self.terminal_url,
            data=data,
            headers=headers,
            method=method,
        )

        with urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read().decode("utf-8"))

        if not isinstance(result, dict):
            raise ValueError("CHL returned an invalid JSON response.")

        return result

    def get_prompt(self) -> str:
        """Retrieve the current terminal prompt."""

        response = self._request("GET")

        if "prompt" not in response:
            raise RuntimeError(
                response.get("output", "Could not retrieve terminal prompt.")
            )

        return str(response["prompt"])

    def execute(self, command: str) -> CommandResult:
        """Execute one command through the terminal API."""

        if not isinstance(command, str):
            raise TypeError("Command must be a string.")

        try:
            response = self._request("POST", {"command": command})

            output = str(response.get("output") or "")
            prompt = str(response.get("prompt") or "")

            if output == "Device not found.":
                outcome = CommandOutcome.API_ERROR
            else:
                outcome = classify_outcome(output, prompt)

            return CommandResult(
                device=self.device_name,
                command=command,
                output=output,
                prompt=prompt,
                outcome=outcome,
            )

        except HTTPError as exc:
            return self._failure(
                command,
                f"HTTP error {exc.code}: {exc.reason}",
            )

        except (URLError, TimeoutError, OSError) as exc:
            return self._failure(
                command,
                f"Connection error: {exc}",
            )

        except (ValueError, json.JSONDecodeError) as exc:
            return self._failure(
                command,
                f"Invalid response from CHL: {exc}",
            )

    def _failure(self, command: str, message: str) -> CommandResult:
        return CommandResult(
            device=self.device_name,
            command=command,
            output=message,
            prompt="",
            outcome=CommandOutcome.API_ERROR,
        )
