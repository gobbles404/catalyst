"""The filter request, import-cleared-futures.md: one request to the endpoint the workbook names,
the filter's text as its body, through the standard library with a timeout, and the answer read
whole and handed to the reader of trade IDs. A connection refused, a timeout, a status other than
200, an answer that is not text or an endpoint that is no address is a refusal naming the address
and the cause, in the words of the seam. No credentials, decision 4: the endpoint stands alone, and
the request carries nothing the workbook does not hold. The system's proxy settings apply as
urllib reads them, the environment's and then Windows' own, so the request takes the road the
desk's browser takes."""

import http.client
import urllib.error
import urllib.request
from typing import Final

from goosedove.importer.walk import ids_from_json
from goosedove.instrumentation.work_counts import WorkCounter

TIMEOUT_SECONDS: Final = 30.0  # the longest one request may wait, to connect and for each read

REQUESTS_MADE: Final = "requests_made"  # the requests sent, answered or not
BYTES_RECEIVED: Final = "bytes_received"  # the bytes of every answer read whole

_HEADERS: Final = {
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json",
}


def fetch_ids(
    endpoint: str, filter: str, counter: WorkCounter, timeout: float = TIMEOUT_SECONDS
) -> tuple[int, ...]:
    """The filter's answer as trade IDs: a POST to the endpoint carrying the filter's text as its
    body, as the API's own filter document, the answer's bytes read whole, decoded as UTF-8 and
    read by ids_from_json. The one request of the first slice, decision 10. Work: the request
    made and the bytes received."""
    counter.hit(REQUESTS_MADE)
    try:
        request = urllib.request.Request(
            endpoint, data=filter.encode("utf-8"), headers=_HEADERS, method="POST"
        )
        with urllib.request.urlopen(request, timeout=timeout) as answer:
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
        # A read that timed out or was cut short, an answer that is no HTTP, or an endpoint that
        # is no address at all, which urllib refuses before any connection.
        raise ValueError(f"the filter request to {endpoint} failed: {refusal}") from None
    counter.hit(BYTES_RECEIVED, len(body))
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(
            f"the filter request to {endpoint} answered {len(body)} bytes that are not UTF-8 text"
        ) from None
    return ids_from_json(text)
