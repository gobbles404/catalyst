"""The filter request, import-cleared-futures.md: one GET to the filter's address, the filter's
name the last part of the path and no body, the answer read as trade IDs, and each way the
request fails named with the address and the cause; against the stand-in of
tools/import_standin.py, which serves recorded answers on the loopback interface, and against a
port nobody listens on."""

import re
import socket
from collections.abc import Iterator

import pytest
from import_standin import StandIn, serve

from goosedove.importer.fetch import address, fetch_ids
from goosedove.instrumentation.work_counts import WorkCounter


@pytest.fixture(scope="module")
def standin() -> Iterator[StandIn]:
    server = serve()
    yield server
    server.shutdown()
    server.server_close()


def endpoint(standin: StandIn, path: str = "/gettradeids") -> str:
    return f"http://127.0.0.1:{standin.server_address[1]}{path}"


def refused(message: str, endpoint: str, filter: str = "three", timeout: float = 5.0) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        fetch_ids(endpoint, filter, WorkCounter(), timeout)


def test_the_request_is_a_get_with_the_filters_name_last_in_its_path_and_no_body(
    standin: StandIn,
) -> None:
    counter = WorkCounter()
    ids = fetch_ids(endpoint(standin), "three", counter)
    assert ids == (103, 105, 104), "the IDs as the API gave them, in its order"
    seen = standin.requests[-1]
    assert seen == {
        "method": "GET",
        "path": "/gettradeids/three",
        "accept": "application/json",
        "user_agent": seen["user_agent"],
        "content_type": None,
        "body": "",
    }
    # No header of the add-in's own: urllib's User-Agent goes, as for any Python program.
    assert str(seen["user_agent"]).startswith("Python-urllib/")
    assert counter.freeze().as_dict() == {"requests_made": 1, "bytes_received": 29}


def test_the_filters_name_is_encoded_once_as_a_part_of_the_path(standin: StandIn) -> None:
    # A space, a slash, a question mark or a percent sign in the name is a character of it and
    # never the address's syntax; a trailing slash on the endpoint is not doubled.
    with pytest.raises(ValueError, match=r" answered 404 Not Found, expected 200$"):
        fetch_ids(endpoint(standin) + "/", "Giles CMDTY/Today?50%", WorkCounter())
    assert standin.requests[-1]["path"] == "/gettradeids/Giles%20CMDTY%2FToday%3F50%25"
    assert (
        address("https://api.desk/calypso/gettradeids", "Giles_CMDTY_Today")
        == "https://api.desk/calypso/gettradeids/Giles_CMDTY_Today"
    )
    assert address("https://api.desk/calypso/gettradeids/", "x") == (
        "https://api.desk/calypso/gettradeids/x"
    )
    assert address("https://api.desk", "x") == "https://api.desk/x"


def test_an_endpoint_that_cannot_take_the_name_is_refused_before_any_request() -> None:
    for endpoint, cause in (
        ("nowhere", "expected an http or https address"),
        ("file:///C:/trades.json", "expected an http or https address"),
        ("ftp://api/gettradeids", "expected an http or https address"),
        ("https:///gettradeids", "expected an address with a host"),
        ("https://:8080/gettradeids", "expected an address with a host"),
        (
            "https://user:secret@api.desk/gettradeids",
            "expected an address without credentials in it",
        ),
        (
            "https://api.desk/gettradeids?x=1",
            "expected an address ending in its path, with no ? or #",
        ),
        (
            "https://api.desk/gettradeids#top",
            "expected an address ending in its path, with no ? or #",
        ),
        ("https://api.desk/get tradeids", "expected an address without whitespace"),
        ("https://api.desk/gettradeids\t", "expected an address without whitespace"),
    ):
        counter = WorkCounter()
        message = f"the filter request to {endpoint} failed: {cause}"
        with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
            fetch_ids(endpoint, "three", counter)
        assert counter.freeze().as_dict() == {}


def test_a_filter_that_is_no_name_is_refused_before_any_request() -> None:
    for filter, message in (
        (" three", "the filter ' three' has whitespace around it, expected a filter's name"),
        ("three ", "the filter 'three ' has whitespace around it, expected a filter's name"),
        ("th\tree", "the filter 'th\\tree' holds a control character, expected a filter's name"),
        (
            "three\x00",
            "the filter 'three\\x00' holds a control character, expected a filter's name",
        ),
        (".", "the filter '.' is a step in a path, expected a filter's name"),
        ("..", "the filter '..' is a step in a path, expected a filter's name"),
    ):
        counter = WorkCounter()
        with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
            fetch_ids("https://api.desk/gettradeids", filter, counter)
        assert counter.freeze().as_dict() == {}


def test_an_empty_answer_is_no_ids(standin: StandIn) -> None:
    assert fetch_ids(endpoint(standin), "none", WorkCounter()) == ()


def test_a_status_other_than_200_is_refused_with_the_whole_address(standin: StandIn) -> None:
    failing = endpoint(standin, "/status/500")
    refused(
        f"the filter request to {failing}/three answered 500 Internal Server Error, expected 200",
        failing,
    )
    nowhere = endpoint(standin, "/nowhere")
    refused(f"the filter request to {nowhere}/three answered 404 Not Found, expected 200", nowhere)


def test_a_status_other_than_200_is_refused_even_with_ids_in_the_answer(
    standin: StandIn,
) -> None:
    # A 206 is a partial answer, a 204 none, and 201 and 202 no answer at all; only 200 is read.
    for status, reason in (
        (201, "Created"),
        (202, "Accepted"),
        (204, "No Content"),
        (206, "Partial Content"),
    ):
        failing = endpoint(standin, f"/status/{status}")
        refused(
            f"the filter request to {failing}/three answered {status} {reason}, expected 200",
            failing,
        )


def test_a_sign_in_demanded_is_refused_with_its_status_and_asked_of_no_one(
    standin: StandIn,
) -> None:
    # The first version sends no credentials, decision 4: a 401 or a 403 is the line, and no
    # second request with anything more leaves.
    for status, reason in ((401, "Unauthorized"), (403, "Forbidden")):
        failing = endpoint(standin, f"/status/{status}")
        seen = len(standin.requests)
        refused(
            f"the filter request to {failing}/three answered {status} {reason}, expected 200",
            failing,
        )
        assert len(standin.requests) == seen + 1


def test_an_answer_that_is_no_object_of_whole_numbers_is_refused_in_the_readers_words(
    standin: StandIn,
) -> None:
    for filter, message in (
        ("list", "the filter's answer is a list, expected an object holding tradeIds"),
        ("alias", "the filter's answer has no tradeIds, expected an object holding tradeIds"),
        ("null", "the filter's tradeIds is nothing, expected a list of trade IDs"),
        ("fraction", "the filter's item 1 is 105.5, expected a whole number, a trade ID"),
        ("string", "the filter's item 1 is text '104', expected a whole number, a trade ID"),
        (
            "long",
            "the filter's item 1 is 1000000000000000, expected a whole number of at most 15 digits",
        ),
    ):
        refused(message, endpoint(standin), filter)
    with pytest.raises(ValueError, match=r"^the filter's answer is not JSON: "):
        fetch_ids(endpoint(standin), "text", WorkCounter())
    unreadable = endpoint(standin)
    refused(
        f"the filter request to {unreadable}/bytes answered 2 bytes that are not UTF-8 text",
        unreadable,
        "bytes",
    )


def test_nobody_listening_is_refused_with_the_whole_address_and_the_cause() -> None:
    # A port the system handed out and gave back: nothing listens on it now.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    nowhere = f"http://127.0.0.1:{port}/gettradeids"
    with pytest.raises(
        ValueError, match=rf"^the filter request to {re.escape(nowhere)}/three failed: ."
    ):
        fetch_ids(nowhere, "three", WorkCounter())


def test_an_answer_that_never_comes_is_refused_as_timed_out(standin: StandIn) -> None:
    slow = endpoint(standin, "/slow")
    refused(f"the filter request to {slow}/three failed: timed out", slow, timeout=0.2)


def test_a_redirect_is_refused_with_its_status_and_never_followed(standin: StandIn) -> None:
    # Followed, a 302 would report the other address's IDs as the answer, with a second request
    # the counter never saw. The one request is sent, refused by the status, and no other leaves.
    seen = len(standin.requests)
    counter = WorkCounter()
    redirect = endpoint(standin, "/redirect")
    message = f"the filter request to {redirect}/three answered 302 Found, expected 200"
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        fetch_ids(redirect, "three", counter)
    assert len(standin.requests) == seen + 1
    assert standin.requests[-1]["path"] == "/redirect/three"
    assert counter.freeze().as_dict() == {"requests_made": 1}
