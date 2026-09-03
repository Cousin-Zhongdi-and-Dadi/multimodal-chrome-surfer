import os
import sys
from typing import Any

from agent_service import LocalAgentService
from native_messaging import read_message, write_message


def main() -> None:
    native_stdin = sys.stdin.buffer
    native_stdout = sys.stdout.buffer

    # Native Messaging reserves stdout for protocol messages only.
    sys.stdout = open(os.devnull, "w", encoding="utf-8")

    def send_to_extension(message: Any) -> None:
        write_message(native_stdout, message)

    service = LocalAgentService(send_to_extension)
    service.start()

    while True:
        message = read_message(native_stdin)
        if message is None:
            break
        service.handle_message(message)


if __name__ == "__main__":
    main()
