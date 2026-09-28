"""Unit tests for the Teamup HTTP client -- mocks requests.request so
these never touch the network. Request/response shapes asserted here
mirror what docs/research/teamup-live-api-behavior.md and this
ticket's own live smoke testing actually observed, not guesses."""

from unittest.mock import MagicMock, patch

import pytest

from teamup_client import TeamupApiError, TeamupClient


def make_client() -> TeamupClient:
    """Build a client with fake credentials -- no request in these
    tests ever leaves the process, so the values are inert."""
    return TeamupClient(calendar_key="testcal", token="testtoken")


def make_response(status_code=200, json_body=None, text=""):
    """Build a MagicMock standing in for a requests.Response."""
    response = MagicMock()
    response.ok = 200 <= status_code < 300
    response.status_code = status_code
    if json_body is not None:
        response.json.return_value = json_body
        response.text = "non-empty"
    else:
        response.json.side_effect = ValueError("no json")
        response.text = text
    return response


@pytest.mark.unit
def test_list_events_returns_events_list():
    """list_events issues a GET with startDate/endDate query params
    and unwraps the `events` array from the response body."""
    client = make_client()
    response = make_response(
        json_body={"events": [{"id": "1", "remote_id": "abc"}]}
    )
    with patch("teamup_client.requests.request", return_value=response) as req:
        events = client.list_events("2026-01-01", "2026-02-01")

    assert events == [{"id": "1", "remote_id": "abc"}]
    args, kwargs = req.call_args
    assert args[0] == "GET"
    assert args[1].endswith("/testcal/events")
    assert kwargs["params"] == {
        "startDate": "2026-01-01",
        "endDate": "2026-02-01",
    }
    assert kwargs["headers"]["Teamup-Token"] == "testtoken"


@pytest.mark.unit
def test_create_event_posts_payload_and_returns_event():
    """create_event POSTs the given payload verbatim and unwraps the
    `event` object from the response body."""
    client = make_client()
    response = make_response(json_body={"event": {"id": "42", "title": "x"}})
    with patch("teamup_client.requests.request", return_value=response) as req:
        result = client.create_event({"title": "x", "remote_id": "abc"})

    assert result == {"id": "42", "title": "x"}
    args, kwargs = req.call_args
    assert args[0] == "POST"
    assert args[1].endswith("/testcal/events")
    assert kwargs["json"] == {"title": "x", "remote_id": "abc"}


@pytest.mark.unit
def test_create_event_duplicate_remote_id_raises_teamup_api_error():
    """A 400 event_not_unique response (Teamup's real reaction to a
    re-posted remote_id) must surface as a TeamupApiError, not a
    silently-ignored failure."""
    client = make_client()
    response = make_response(
        status_code=400,
        json_body={
            "error": {
                "id": "event_not_unique",
                "title": "Remote ID conflict",
            }
        },
    )
    with patch("teamup_client.requests.request", return_value=response):
        with pytest.raises(TeamupApiError) as excinfo:
            client.create_event({"remote_id": "dup"})

    assert excinfo.value.status_code == 400
    assert excinfo.value.error_body["error"]["id"] == "event_not_unique"


@pytest.mark.unit
def test_update_event_puts_to_internal_id_path():
    """update_event PUTs to /events/{internal_id} with the given
    payload verbatim (callers are responsible for setting the body's
    own `id` field -- Teamup requires it to match the URL's)."""
    client = make_client()
    response = make_response(json_body={"event": {"id": "42"}})
    with patch("teamup_client.requests.request", return_value=response) as req:
        client.update_event("42", {"id": "42", "title": "updated"})

    args, kwargs = req.call_args
    assert args[0] == "PUT"
    assert args[1].endswith("/testcal/events/42")
    assert kwargs["json"] == {"id": "42", "title": "updated"}


@pytest.mark.unit
def test_delete_event_without_redit_all_sends_no_params():
    """A plain delete (one-off event, or a single occurrence) sends
    no `redit` query param."""
    client = make_client()
    response = make_response(json_body={})
    with patch("teamup_client.requests.request", return_value=response) as req:
        client.delete_event("42")

    args, kwargs = req.call_args
    assert args[0] == "DELETE"
    assert args[1].endswith("/testcal/events/42")
    assert kwargs["params"] is None


@pytest.mark.unit
def test_delete_event_with_redit_all_sends_redit_param():
    """redit_all=True sends `?redit=all`, the proven-working way to
    delete a whole recurring series by any one occurrence's id."""
    client = make_client()
    response = make_response(json_body={})
    with patch("teamup_client.requests.request", return_value=response) as req:
        client.delete_event("42", redit_all=True)

    _, kwargs = req.call_args
    assert kwargs["params"] == {"redit": "all"}


@pytest.mark.unit
def test_empty_response_body_raises_teamup_api_error():
    """Observed live during a Teamup maintenance-window glitch: an
    ostensibly-ok response with an empty body. Must not raise a raw
    JSONDecodeError from inside the client."""
    client = make_client()
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.text = ""
    with patch("teamup_client.requests.request", return_value=response):
        with pytest.raises(TeamupApiError):
            client.list_events("2026-01-01", "2026-02-01")


@pytest.mark.unit
def test_error_response_with_non_json_body_uses_text():
    """A non-JSON error body (e.g. Teamup's HTML maintenance page)
    still surfaces as a TeamupApiError, carrying the raw text."""
    client = make_client()
    response = make_response(status_code=500, text="<html>Maintenance</html>")
    with patch("teamup_client.requests.request", return_value=response):
        with pytest.raises(TeamupApiError) as excinfo:
            client.list_events("2026-01-01", "2026-02-01")

    assert excinfo.value.status_code == 500
    assert "Maintenance" in excinfo.value.error_body
