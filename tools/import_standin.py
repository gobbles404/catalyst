"""A stand-in for the desk's API, for the tests of the cleared-futures import,
docs/engineering-tickets/import-cleared-futures.md: an HTTP server on the loopback interface that
answers the filter request, a GET with the filter's name as the last part of its path, by that
name with a recorded answer, refuses a POST, and keeps every request it received, the method, the
path, the Accept and User-Agent headers, the content type and the body, for a test to read.
`uv run python tools/import_standin.py --log FILE` runs it as a process for the hidden-Excel
group: it prints its port on one line, writes each request it receives as one JSON line to the
log, and exits when its standard input closes, so the PowerShell that started it ends it by
closing the pipe and nothing is left running. A Python test imports `serve` and runs it in a
thread, reading `requests` off the server instead.

The paths, the endpoint's part first and the filter's name last, each the answer the importer
must read or refuse:

    /gettradeids/three     200  {"tradeIds": [103, 105, 104]}     the issue's table, in no order
    /gettradeids/none      200  {"tradeIds": []}                  an empty answer
    /gettradeids/many      200  {"tradeIds": [1 to 30, shuffled]} more IDs than the line names
    /gettradeids/repeat    200  {"tradeIds": [105, 104, 104]}     a trade ID twice
    /gettradeids/list      200  [103, 105, 104]                   the IDs bare, no object
    /gettradeids/alias     200  {"ids": [105]}                    an object without tradeIds
    /gettradeids/null      200  {"tradeIds": null}                nothing under tradeIds
    /gettradeids/fraction  200  {"tradeIds": [105.5]}             an ID that is no whole number
    /gettradeids/string    200  {"tradeIds": ["104"]}             an ID as text
    /gettradeids/long      200  {"tradeIds": [1000000000000000]}  sixteen digits
    /gettradeids/text      200  not json                          an answer that is no JSON
    /gettradeids/bytes     200  two bytes of no text              an answer that is no UTF-8
    /status/N/<filter>     N    the issue's table, or a failure text from 400 up; any filter
    /redirect/<filter>     302  to /gettradeids/three             a redirect, never followed
    /slow/N/<filter>       200  the issue's table after N seconds; a run caught mid-request
    /slow/<filter>         no answer until the server stops; a read that times out
    a POST to any path     405
    anything else          404
"""

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Final, cast

ISSUE: Final = b'{"tradeIds": [103, 105, 104]}'

ANSWERS: Final[dict[str, tuple[int, bytes]]] = {
    "three": (200, ISSUE),
    "none": (200, b'{"tradeIds": []}'),
    "many": (
        200,
        b'{"tradeIds": [7, 22, 1, 30, 15, 3, 28, 9, 19, 12, 25, 4, 17, 10, 2, 27, 14, 20,'
        b" 6, 23, 29, 11, 16, 8, 26, 5, 21, 13, 24, 18]}",
    ),
    "repeat": (200, b'{"tradeIds": [105, 104, 104]}'),
    "list": (200, b"[103, 105, 104]"),
    "alias": (200, b'{"ids": [105]}'),
    "null": (200, b'{"tradeIds": null}'),
    "fraction": (200, b'{"tradeIds": [105.5]}'),
    "string": (200, b'{"tradeIds": ["104"]}'),
    "long": (200, b'{"tradeIds": [1000000000000000]}'),
    "text": (200, b"not json"),
    "bytes": (200, b"\xff\xfe"),
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
    def do_GET(self) -> None:
        standin = cast(StandIn, self.server)
        self._record(standin, b"")
        parts = self.path.split("/")[1:]  # "/gettradeids/three" is ["gettradeids", "three"]
        if parts[0] == "slow" and len(parts) == 2:
            standin.stopping.wait()
            return
        if parts[0] == "redirect":
            self.send_response(302)
            self.send_header("Location", "/gettradeids/three")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if parts[0] == "slow" and len(parts) == 3:
            # The issue's table after that many seconds, or nothing when the server stops first.
            if standin.stopping.wait(float(parts[1])):
                return
            status, answer = ANSWERS["three"]
        elif parts[0] == "status" and len(parts) == 3:
            status = int(parts[1])
            answer = b"the stand-in failed on purpose" if status >= 400 else ISSUE
        elif parts[0] == "gettradeids" and len(parts) == 2:
            status, answer = ANSWERS.get(parts[1], (404, b"no such filter"))
        else:
            status, answer = 404, b"no such path"
        self._send(status, answer)

    def do_POST(self) -> None:
        standin = cast(StandIn, self.server)
        length = int(self.headers.get("Content-Length") or 0)
        self._record(standin, self.rfile.read(length) if length else b"")
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _record(self, standin: StandIn, body: bytes) -> None:
        standin.record(
            {
                "method": self.command,
                "path": self.path,
                "accept": self.headers.get("Accept"),
                "user_agent": self.headers.get("User-Agent"),
                "content_type": self.headers.get("Content-Type"),
                "body": body.decode("utf-8", errors="replace"),
            }
        )

    def _send(self, status: int, answer: bytes) -> None:
        if status == 204:
            answer = b""  # no content, as the status says
        self.send_response(status)
        self.send_header("Content-Type", "application/json" if status < 300 else "text/plain")
        self.send_header("Content-Length", str(len(answer)))
        self.end_headers()
        self.wfile.write(answer)

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
