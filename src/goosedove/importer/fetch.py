"""The filter request, import-cleared-futures.md: one GET to the address the workbook names with
the filter's name as the last part of its path, the form a named filter takes on the desk's API,
through the standard library with a timeout, and the answer read whole and handed to the reader
of trade IDs. The request is sent once and answered by the address it was sent to: a redirect is
refused with its status and never followed, so that no second request leaves that the counter
never saw; and only 200 is an answer, so a 201, 202, 204 or 206 with IDs in it is refused too. A
connection refused, a timeout, an answer that is not text, an endpoint that cannot take the
filter's name as the last part of its path or a filter that is no name is a refusal naming the
address and the cause, in the words of the seam. No credentials and no header of the add-in's
own beyond what it accepts, decision 4: the endpoint stands alone, the request carries nothing
the workbook does not hold, and urllib's own User-Agent goes as it does for any Python program.
The system's proxy settings apply as urllib reads them, the environment's and then Windows' own,
so the request takes the road the desk's browser takes."""

import http.client
import re
import urllib.error
import urllib.request
from http.client import HTTPMessage
from typing import IO, Final
from urllib.parse import quote, urlsplit

from goosedove.importer.walk import ids_from_json
from goosedove.instrumentation.work_counts import WorkCounter

TIMEOUT_SECONDS: Final = 30.0  # the longest one request may wait, to connect and for each read

REQUESTS_MADE: Final = "requests_made"  # the requests sent, answered or not
BYTES_RECEIVED: Final = "bytes_received"  # the bytes of every answer read whole

_HEADERS: Final = {"Accept": "application/json"}  # and nothing of the add-in's own besides

_WHITESPACE: Final = re.compile(r"\s")
_CONTROL: Final = re.compile(r"[\x00-\x1f\x7f]")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect refused with its status, so the one request is never followed by another."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


# urllib's default handlers, the proxies' among them, with the refusal in the redirect handler's
# place, built once.
_OPENER: Final = urllib.request.build_opener(_NoRedirect)


def address(endpoint: str, filter: str) -> str:
    """The filter request's address: the endpoint, an absolute http or https address with a host
    and nothing after its path, then the filter's name encoded once as the path's last part, so
    that a space or a slash in the name is a character of it and never the address's syntax. An
    endpoint or a filter that cannot make such an address is refused here, before any request:
    an endpoint with whitespace, with credentials in it, or with a query or a fragment, which the
    name would land inside; a filter with whitespace around it, with a control character, or
    equal to `.` or `..`, which a server reads as a step in the path and not a name."""
    if _WHITESPACE.search(endpoint):
        raise _refusal(endpoint, "expected an address without whitespace")
    if "?" in endpoint or "#" in endpoint:
        raise _refusal(endpoint, "expected an address ending in its path, with no ? or #")
    try:
        parts = urlsplit(endpoint)
    except ValueError as refusal:
        raise _refusal(endpoint, str(refusal)) from None
    if parts.scheme not in ("http", "https"):
        raise _refusal(endpoint, "expected an http or https address")
    if "@" in parts.netloc:
        raise _refusal(endpoint, "expected an address without credentials in it")
    if not parts.hostname:
        raise _refusal(endpoint, "expected an address with a host")
    if filter != filter.strip():
        raise ValueError(
            f"the filter {filter!r} has whitespace around it, expected a filter's name"
        )
    if _CONTROL.search(filter):
        raise ValueError(
            f"the filter {filter!r} holds a control character, expected a filter's name"
        )
    if filter in (".", ".."):
        raise ValueError(f"the filter {filter!r} is a step in a path, expected a filter's name")
    return endpoint.rstrip("/") + "/" + quote(filter, safe="")


def _refusal(endpoint: str, cause: str) -> ValueError:
    return ValueError(f"the filter request to {endpoint} failed: {cause}")


def fetch_ids(
    endpoint: str, filter: str, counter: WorkCounter, timeout: float = TIMEOUT_SECONDS
) -> tuple[int, ...]:
    """The filter's answer as trade IDs: one GET to the filter's address, no body, the answer's
    bytes read whole, decoded as UTF-8 and read by ids_from_json. The one request of the first
    slice, decision 10 as settled against the desk's API. Work: the request made and the bytes
    received."""
    url = address(endpoint, filter)
    counter.hit(REQUESTS_MADE)
    try:
        request = urllib.request.Request(url, headers=_HEADERS, method="GET")
        with _OPENER.open(request, timeout=timeout) as answer:
            status, reason = int(answer.status), str(answer.reason)
            body: bytes = answer.read()
    except urllib.error.HTTPError as refusal:
        raise ValueError(
            f"the filter request to {url} answered {refusal.code} {refusal.reason}, expected 200"
        ) from None
    except urllib.error.URLError as refusal:
        # The transport's own failure, a connection refused or a connect that timed out, wrapped
        # by urllib around the operating system's words.
        raise ValueError(f"the filter request to {url} failed: {refusal.reason}") from None
    except (OSError, http.client.HTTPException, ValueError) as refusal:
        # A read that timed out or was cut short, or an answer that is no HTTP.
        raise ValueError(f"the filter request to {url} failed: {refusal}") from None
    if status != 200:
        raise ValueError(f"the filter request to {url} answered {status} {reason}, expected 200")
    counter.hit(BYTES_RECEIVED, len(body))
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(
            f"the filter request to {url} answered {len(body)} bytes that are not UTF-8 text"
        ) from None
    return ids_from_json(text)
