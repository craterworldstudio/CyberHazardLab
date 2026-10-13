"""Penetrator entry point."""

import argparse

from penetrator.executor import TerminalExecutor


def main() -> None:
    parser = argparse.ArgumentParser(description="CHL Penetrator")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="Base URL of the running CHL server.",
    )
    parser.add_argument(
        "--device",
        required=True,
        help="Name of the Penetrator's assigned device.",
    )

    args = parser.parse_args()

    executor = TerminalExecutor(
        base_url=args.url,
        device_name=args.device,
    )

    print(f"Penetrator connected to {args.url}")
    print(f"Assigned device: {args.device}")
    print("Interactive testing mode. Type 'exit' to quit.")

    while True:
        try:
            command = input("penetrator> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if command.lower() in {"exit", "quit"}:
            break

        if not command:
            continue

        result = executor.execute(command)

        print(f"[{result.outcome.value}]")

        if result.output:
            print(result.output)

        if result.prompt:
            print(result.prompt)


if __name__ == "__main__":
    main()
