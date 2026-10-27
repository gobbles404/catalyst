"""A stand-in for the desk's API, for the tests of the cleared-futures import,
docs/engineering-tickets/import-cleared-futures.md: an HTTP server on the loopback interface that
answers the filter request by its path with a recorded answer, whatever the method, and keeps
every request it received, the method, the path, the content type and the body, for a test to
read. `uv run python tools/import_standin.py --log FILE` runs it as a process for the hidden-Excel
group: it prints its port on one line, writes each request it receives as one JSON line to the
log, and exits when its standard input closes, so the PowerShell that started it ends it by
closing the pipe and nothing is left running. A Python test imports `serve` and runs it in a
thread, reading `requests` off the server instead.

The paths, each the answer the importer must read or refuse:

    /ids/three     200  [103, 105, 104]       the issue's table, in no particular order
    /ids/none      200  []                    an empty answer
    /ids/many      200  1 to 30, shuffled     more IDs than the status line names
    /ids/repeat    200  [105, 104, 104]       a trade ID twice
    /ids/object    200  {"ids": [105]}        an answer that is no list
    /ids/fraction  200  [105.5]               an ID that is no whole number
    /ids/text      200  not json              an answer that is no JSON
    /ids/bytes     200  two bytes of no text  an answer that is no UTF-8
    /status/500    500  a failure             the API failing
    /slow          no answer until the server stops; a read that times out
    anything else  404
"""

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final

ANSWERS: Final[dict[str, tuple[int, bytes]]] = {
    "/ids/three": (200, b"[103, 105, 104]"),
    "/ids/none": (200, b"[]"),
    "/ids/many": (
        200,
        b"[7, 22, 1, 30, 15, 3, 28, 9, 19, 12, 25, 4, 17, 10, 2, 27, 14, 20,"
        b" 6, 23, 29, 11, 16, 8, 26, 5, 21, 13, 24, 18]",
    ),
    "/ids/repeat": (200, b"[105, 104, 104]"),
    "/ids/object": (200, b'{"ids": [105]}'),
    "/ids/fraction": (200, b"[105.5]"),
    "/ids/text": (200, b"not json"),
    "/ids/bytes": (200, b"\xff\xfe"),
    "/status/500": (500, b"the stand-in failed on purpose"),
}


class StandIn(ThreadingHTTPServer):
    """The server, with what it has received and the signal that ends a slow answer."""

    daemon_threads = True
    block_on_close = False

    def __init__(self, port: int, log: str | None) -> None:
        super().__init__(("127.0.0.1", port), Handler)
        self.requests: list[dict[str, object]] = []
        self.log = log
        if log is not None:
            open(log, "w", encoding="utf-8").close()  # there from the start, empty until a request
        self.stopping = threading.Event()

    def record(self, request: dict[str, object]) -> None:
        self.requests.append(request)
        if self.log is not None:
            with open(self.log, "a", encoding="utf-8") as log:
                log.write(json.dumps(request) + "\n")

    def shutdown(self) -> None:
        self.stopping.set()
        super().shutdown()


class Handler(BaseHTTPRequestHandler):
    server: StandIn

    def _answer(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self.server.record(
            {
                "method": self.command,
                "path": self.path,
                "content_type": self.headers.get("Content-Type"),
                "body": body.decode("utf-8", errors="replace"),
            }
        )
        if self.path == "/slow":
            self.server.stopping.wait()
            return
        status, answer = ANSWERS.get(self.path, (404, b"no such path"))
        self.send_response(status)
        self.send_header("Content-Type", "application/json" if status == 200 else "text/plain")
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)

    do_GET = _answer
    do_POST = _answer

    def log_message(self, format: str, *args: object) -> None:
        """Nothing on stderr: the requests are recorded, not printed."""


def serve(port: int = 0, log: str | None = None) -> StandIn:
    """The stand-in listening on the port, 0 for one the system picks, served on a thread of its
    own until `shutdown`; its port is `server_address[1]`."""
    server = StandIn(port, log)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="a stand-in for the desk's API")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--log", default=None, help="the file each request is appended to")
    args = parser.parse_args()
    server = serve(args.port, args.log)
    print(server.server_address[1], flush=True)
    sys.stdin.read()  # until the pipe closes
    server.shutdown()


if __name__ == "__main__":
    main()
