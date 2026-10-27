"""The filter request, import-cleared-futures.md: a POST carrying the filter's text as its body,
the answer read as trade IDs, and each way the request fails named with the address and the
cause; against the stand-in of tools/import_standin.py, which serves recorded answers on the
loopback interface, and against a port nobody listens on."""

import re
import socket
from collections.abc import Iterator

import pytest
from import_standin import StandIn, serve

from goosedove.importer.fetch import fetch_ids
from goosedove.instrumentation.work_counts import WorkCounter


@pytest.fixture(scope="module")
def standin() -> Iterator[StandIn]:
    server = serve()
    yield server
    server.shutdown()
    server.server_close()


def address(standin: StandIn, path: str) -> str:
    return f"http://127.0.0.1:{standin.server_address[1]}{path}"


def refused(message: str, endpoint: str, timeout: float = 5.0) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        fetch_ids(endpoint, "today", WorkCounter(), timeout)


def test_the_request_is_a_post_carrying_the_filter_as_its_body(standin: StandIn) -> None:
    counter = WorkCounter()
    ids = fetch_ids(address(standin, "/ids/three"), '{"product": "cleared futures"}', counter)
    assert ids == (103, 105, 104), "the IDs as the API gave them, in its order"
    assert standin.requests[-1] == {
        "method": "POST",
        "path": "/ids/three",
        "content_type": "application/json; charset=utf-8",
        "body": '{"product": "cleared futures"}',
    }
    assert counter.freeze().as_dict() == {"requests_made": 1, "bytes_received": 15}


def test_an_empty_answer_is_no_ids(standin: StandIn) -> None:
    assert fetch_ids(address(standin, "/ids/none"), "today", WorkCounter()) == ()


def test_a_status_other_than_200_is_refused_with_the_address(standin: StandIn) -> None:
    failing = address(standin, "/status/500")
    refused(
        f"the filter request to {failing} answered 500 Internal Server Error, expected 200", failing
    )
    nowhere = address(standin, "/nowhere")
    refused(f"the filter request to {nowhere} answered 404 Not Found, expected 200", nowhere)


def test_an_answer_that_is_no_list_of_whole_numbers_is_refused_in_the_readers_words(
    standin: StandIn,
) -> None:
    refused(
        "the filter's answer is an object, expected a list of trade IDs",
        address(standin, "/ids/object"),
    )
    refused(
        "the filter's item 1 is 105.5, expected a whole number, a trade ID",
        address(standin, "/ids/fraction"),
    )
    with pytest.raises(ValueError, match=r"^the filter's answer is not JSON: "):
        fetch_ids(address(standin, "/ids/text"), "today", WorkCounter())
    unreadable = address(standin, "/ids/bytes")
    refused(
        f"the filter request to {unreadable} answered 2 bytes that are not UTF-8 text", unreadable
    )


def test_nobody_listening_is_refused_with_the_address_and_the_cause() -> None:
    # A port the system handed out and gave back: nothing listens on it now.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    endpoint = f"http://127.0.0.1:{port}/ids"
    with pytest.raises(
        ValueError, match=rf"^the filter request to {re.escape(endpoint)} failed: ."
    ):
        fetch_ids(endpoint, "today", WorkCounter())


def test_an_answer_that_never_comes_is_refused_as_timed_out(standin: StandIn) -> None:
    slow = address(standin, "/slow")
    refused(f"the filter request to {slow} failed: timed out", slow, timeout=0.2)


def test_an_endpoint_that_is_no_http_address_is_refused_before_any_request() -> None:
    for endpoint in ("nowhere", "file:///C:/trades.json", "ftp://api/ids"):
        counter = WorkCounter()
        message = f"the filter request to {endpoint} failed: expected an http or https address"
        with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
            fetch_ids(endpoint, "today", counter)
        assert counter.freeze().as_dict() == {}


def test_a_redirect_is_refused_with_its_status_and_never_followed(standin: StandIn) -> None:
    # The review's probe: followed, a 302 turns the POST into a GET without the filter's text
    # and reports the other address's IDs as the answer, with a second request the counter
    # never saw. The one request is sent, refused by the status, and no other leaves.
    seen = len(standin.requests)
    counter = WorkCounter()
    redirect = address(standin, "/redirect")
    message = f"the filter request to {redirect} answered 302 Found, expected 200"
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        fetch_ids(redirect, "today", counter)
    assert len(standin.requests) == seen + 1
    assert standin.requests[-1]["path"] == "/redirect"
    assert counter.freeze().as_dict() == {"requests_made": 1}


def test_a_status_other_than_200_is_refused_even_with_ids_in_the_answer(
    standin: StandIn,
) -> None:
    # A 206 is a partial answer, and 201 and 202 are no answer at all; only 200 is read.
    for status, reason in ((201, "Created"), (202, "Accepted"), (206, "Partial Content")):
        endpoint = address(standin, f"/status/{status}")
        refused(
            f"the filter request to {endpoint} answered {status} {reason}, expected 200", endpoint
        )
