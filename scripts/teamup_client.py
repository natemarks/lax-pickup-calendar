"""Thin HTTP wrapper around the Teamup REST API.

This module knows nothing about the JSON event schema or recurrence
rules -- it only knows how to list/create/update/delete raw Teamup
event dicts over HTTP. Field mapping and sync logic live in
scripts/sync_teamup.py. Keeping this layer dumb makes it mockable in
unit tests without needing to fake the JSON->Teamup translation too.

Every fact this module relies on (required fields, error shapes,
which recurring-series operations are safe) was empirically verified
against the real API -- see docs/research/teamup-live-api-behavior.md
and this ticket's own live smoke testing, not just the API's own
(sometimes wrong) documentation.
"""

from typing import Any

import requests

TEAMUP_BASE_URL = "https://api.teamup.com"
REQUEST_TIMEOUT_SECONDS = 30


class TeamupApiError(Exception):
    """Raised when Teamup returns a non-2xx response.

    Carries the parsed error body (when Teamup returned JSON) so
    callers can distinguish e.g. `event_not_unique` from other
    failures without re-parsing the response themselves.
    """

    def __init__(self, status_code: int, error_body: Any):
        self.status_code = status_code
        self.error_body = error_body
        super().__init__(f"Teamup API error {status_code}: {error_body!r}")


class TeamupClient:
    """Pure HTTP layer over one Teamup calendar.

    `calendar_key` is the Calendar Link key (used as the base-URL path
    segment); `token` is the value sent as the `Teamup-Token` header.
    Both are read from `.env` by the caller and never logged here.
    """

    def __init__(
        self,
        calendar_key: str,
        token: str,
        base_url: str = TEAMUP_BASE_URL,
    ):
        self._calendar_key = calendar_key
        self._headers = {
            "Teamup-Token": token,
            "Content-Type": "application/json",
        }
        self._base_url = f"{base_url}/{calendar_key}"

    def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Issue one request and raise TeamupApiError on failure.

        A response with an empty body (observed during a real Teamup
        maintenance-window glitch while live-testing this client) is
        treated as an error too -- callers should never have to guard
        against `response.json()` raising on an empty 200-shaped body.
        """
        response = requests.request(
            method,
            f"{self._base_url}{path}",
            headers=self._headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
            **kwargs,
        )
        if not response.ok:
            try:
                error_body = response.json()
            except ValueError:
                error_body = response.text
            raise TeamupApiError(response.status_code, error_body)
        if not response.text:
            raise TeamupApiError(response.status_code, "empty response body")
        return response.json()

    def list_events(
        self, start_date: str, end_date: str
    ) -> list[dict[str, Any]]:
        """List events (occurrences of recurring series included) in
        [start_date, end_date], both YYYY-MM-DD."""
        body = self._request(
            "GET",
            "/events",
            params={"startDate": start_date, "endDate": end_date},
        )
        return list(body["events"])

    def create_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a new event (or recurring series, if `payload` has an
        `rrule`). Raises TeamupApiError(status_code=400, error_body
        containing id `event_not_unique`) if `payload["remote_id"]`
        already exists -- Teamup's create does not upsert."""
        body = self._request("POST", "/events", json=payload)
        return dict(body["event"])

    def update_event(
        self, internal_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT a full replacement of the event addressed by
        `internal_id`. Teamup requires the body's own `id` field to
        match the URL's id (confirmed by live testing -- omitting it
        returns `invalid_json: "id" missing`), so callers must set
        `payload["id"] = internal_id` themselves.

        Only safe for one-off events. Do NOT call this for a
        recurring-series occurrence id with `redit=all`: live testing
        showed that in-place series edits via PUT are unreliable --
        one attempt silently dropped an occurrence from the series
        and another returned an empty response body. Recurring-series
        updates should delete the series and recreate it instead (see
        sync_teamup.py), both of which are proven-reliable operations.
        """
        body = self._request("PUT", f"/events/{internal_id}", json=payload)
        return dict(body["event"])

    def delete_event(self, internal_id: str, redit_all: bool = False) -> None:
        """DELETE the event addressed by `internal_id`. Pass
        `redit_all=True` to delete an entire recurring series (any one
        occurrence's internal id works; Teamup deletes every
        occurrence in the series) -- confirmed working by live
        testing. Without it, deletes just the single addressed
        event/occurrence."""
        params = {"redit": "all"} if redit_all else None
        self._request("DELETE", f"/events/{internal_id}", params=params)
