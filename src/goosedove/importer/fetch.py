"""The filter request, import-cleared-futures.md: one request to the endpoint the workbook names,
the filter's text as its body, through the standard library with a timeout, and the answer read
whole and handed to the reader of trade IDs. The request is sent once and answered by the address
it was sent to: a redirect is refused with its status and never followed, since following one
would turn the POST into a GET without the filter's text and a second request the counter never
saw; and only 200 is an answer, so a 201, 202 or 206 with IDs in it is refused too. A connection
refused, a timeout, an answer that is not text or an endpoint that is no http address is a
refusal naming the address and the cause, in the words of the seam. No credentials, decision 4:
the endpoint stands alone, and the request carries nothing the workbook does not hold. The
system's proxy settings apply as urllib reads them, the environment's and then Windows' own, so
the request takes the road the desk's browser takes."""

import http.client
import urllib.error
import urllib.request
from http.client import HTTPMessage
from typing import IO, Final
from urllib.parse import urlsplit

from goosedove.importer.walk import ids_from_json
from goosedove.instrumentation.work_counts import WorkCounter

TIMEOUT_SECONDS: Final = 30.0  # the longest one request may wait, to connect and for each read

REQUESTS_MADE: Final = "requests_made"  # the requests sent, answered or not
BYTES_RECEIVED: Final = "bytes_received"  # the bytes of every answer read whole

_HEADERS: Final = {
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json",
}


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


def fetch_ids(
    endpoint: str, filter: str, counter: WorkCounter, timeout: float = TIMEOUT_SECONDS
) -> tuple[int, ...]:
    """The filter's answer as trade IDs: a POST to the endpoint carrying the filter's text as its
    body, as the API's own filter document, the answer's bytes read whole, decoded as UTF-8 and
    read by ids_from_json. The one request of the first slice, decision 10. Work: the request
    made and the bytes received."""
    try:
        scheme = urlsplit(endpoint).scheme
    except ValueError as refusal:
        raise ValueError(f"the filter request to {endpoint} failed: {refusal}") from None
    if scheme not in ("http", "https"):
        raise ValueError(
            f"the filter request to {endpoint} failed: expected an http or https address"
        )
    counter.hit(REQUESTS_MADE)
    try:
        request = urllib.request.Request(
            endpoint, data=filter.encode("utf-8"), headers=_HEADERS, method="POST"
        )
        with _OPENER.open(request, timeout=timeout) as answer:
            status, reason = int(answer.status), str(answer.reason)
            body: bytes = answer.read()
    except urllib.error.HTTPError as refusal:
        raise ValueError(
            f"the filter request to {endpoint} answered {refusal.code} {refusal.reason}, "
            "expected 200"
        ) from None
    except urllib.error.URLError as refusal:
        # The transport's own failure, a connection refused or a connect that timed out, wrapped
        # by urllib around the operating system's words.
        raise ValueError(f"the filter request to {endpoint} failed: {refusal.reason}") from None
    except (OSError, http.client.HTTPException, ValueError) as refusal:
        # A read that timed out or was cut short, or an answer that is no HTTP.
        raise ValueError(f"the filter request to {endpoint} failed: {refusal}") from None
    if status != 200:
        raise ValueError(
            f"the filter request to {endpoint} answered {status} {reason}, expected 200"
        )
    counter.hit(BYTES_RECEIVED, len(body))
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(
            f"the filter request to {endpoint} answered {len(body)} bytes that are not UTF-8 text"
        ) from None
    return ids_from_json(text)
