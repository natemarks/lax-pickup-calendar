"""Integration tests that hit the real Teamup API using `.env`
credentials. Regression checks for future runs of the sync engine,
following the cleanup-and-verify pattern established in
docs/research/teamup-live-api-behavior.md: every fixture event created
here uses a distinctly-tagged `remote_id` (`wayfinder-integration-test-
...`) and is deleted again before the test finishes, whether it passes
or fails. These never touch the real synced events from data/events.json
-- only their own throwaway fixtures.

Skipped automatically if TEAMUP_TOKEN/TEAMUP_CALENDAR_KEY aren't set,
so `make unit` (and CI, which has no credentials) never depends on
these."""

import os

import pytest
from dotenv import load_dotenv

from sync_teamup import (
    build_payloads,
    compute_list_range,
    execute_sync,
    fetch_remote_index,
    plan_sync,
)
from teamup_client import TeamupClient

SUBCALENDAR_ID = 16069515
WEEKLY_REMOTE_ID = "wayfinder-integration-test-weekly"
ONCE_REMOTE_ID = "wayfinder-integration-test-once"


def _weekly_event(title="Integration Test Weekly"):
    """Fixture weekly event, distinctly tagged so it never collides
    with a real synced event from data/events.json."""
    return {
        "id": WEEKLY_REMOTE_ID,
        "title": title,
        "location": "Test Field",
        "notes": "created by tests/test_integration.py",
        "recurrenceType": "weekly",
        "dayOfWeek": "TU",
        "startDate": "2026-10-06",
        "endDate": "2026-10-27",
        "startTime": "10:00",
        "endTime": "11:00",
        "timezone": "America/New_York",
    }


def _once_event(title="Integration Test Once"):
    """Fixture one-off event, distinctly tagged so it never collides
    with a real synced event from data/events.json."""
    return {
        "id": ONCE_REMOTE_ID,
        "title": title,
        "location": "Test Field",
        "notes": "created by tests/test_integration.py",
        "recurrenceType": "once",
        "date": "2026-10-10",
        "startTime": "10:00",
        "endTime": "11:00",
        "timezone": "America/New_York",
    }


@pytest.fixture(name="client")
def client_fixture():
    """A real TeamupClient built from .env, or a skip if credentials
    aren't configured -- keeps `make unit`/CI independent of these."""
    load_dotenv()
    token = os.environ.get("TEAMUP_TOKEN")
    calendar_key = os.environ.get("TEAMUP_CALENDAR_KEY")
    if not token or not calendar_key:
        pytest.skip("TEAMUP_TOKEN/TEAMUP_CALENDAR_KEY not set in .env")
    return TeamupClient(calendar_key, token)


def _cleanup(client, start, end):
    """Delete any leftover fixture events by remote_id, e.g. from a
    previous failed run, so each test starts and ends from a clean
    slate without touching real synced events."""
    remote_index = fetch_remote_index(client, start, end)
    for remote_id in (WEEKLY_REMOTE_ID, ONCE_REMOTE_ID):
        info = remote_index.get(remote_id)
        if info is not None:
            client.delete_event(
                info["internal_id"], redit_all=info["is_recurring"]
            )


def _create_fixtures(client, start, end):
    """Create both fixture events fresh and assert the sync engine
    correctly classified them as creates."""
    mapped, skipped = build_payloads(
        [_weekly_event(), _once_event()], SUBCALENDAR_ID
    )
    assert not skipped
    remote_index = fetch_remote_index(client, start, end)
    plan = plan_sync(mapped, remote_index)
    assert set(plan.creates) == {WEEKLY_REMOTE_ID, ONCE_REMOTE_ID}
    execute_sync(client, mapped, remote_index, plan)


def _update_fixtures(client, start, end):
    """Re-sync both fixture events with new titles and assert the
    sync engine correctly classified them as updates."""
    mapped, skipped = build_payloads(
        [
            _weekly_event("Integration Test Weekly UPDATED"),
            _once_event("Integration Test Once UPDATED"),
        ],
        SUBCALENDAR_ID,
    )
    assert not skipped
    remote_index = fetch_remote_index(client, start, end)
    plan = plan_sync(mapped, remote_index)
    assert sorted(plan.updates) == sorted([WEEKLY_REMOTE_ID, ONCE_REMOTE_ID])
    execute_sync(client, mapped, remote_index, plan)


def _assert_titles_updated(client, start, end):
    """Confirm the update actually landed on Teamup's own data, not
    just that the local bucketing logic ran without error."""
    remote_events = client.list_events(start, end)
    titles = {
        remote_event["remote_id"]: remote_event["title"]
        for remote_event in remote_events
        if remote_event.get("remote_id") in (WEEKLY_REMOTE_ID, ONCE_REMOTE_ID)
    }
    assert titles[WEEKLY_REMOTE_ID] == "Integration Test Weekly UPDATED"
    assert titles[ONCE_REMOTE_ID] == "Integration Test Once UPDATED"


def _delete_fixtures(client, start, end):
    """Sync against an empty JSON set and assert both fixtures are
    correctly classified as deletes, then confirm they're gone."""
    remote_index = fetch_remote_index(client, start, end)
    plan = plan_sync({}, remote_index)
    assert sorted(plan.deletes) == sorted([WEEKLY_REMOTE_ID, ONCE_REMOTE_ID])
    execute_sync(client, {}, remote_index, plan)

    remote_index_after = fetch_remote_index(client, start, end)
    assert WEEKLY_REMOTE_ID not in remote_index_after
    assert ONCE_REMOTE_ID not in remote_index_after


@pytest.mark.integration
def test_list_events_smoke(client):
    """Basic regression check: the list endpoint responds and returns
    a list shape, over a short real date range."""
    events = client.list_events("2026-09-28", "2026-10-05")
    assert isinstance(events, list)


@pytest.mark.integration
def test_full_sync_round_trip_create_update_delete(client):
    """Exercises the real create -> update (delete+recreate for the
    weekly event, plain PUT for the one-off) -> delete path the sync
    engine actually uses, against the live calendar, with a distinctly
    tagged fixture remote_id that is always cleaned up afterward."""
    mapped, skipped = build_payloads([_weekly_event()], SUBCALENDAR_ID)
    assert not skipped
    start, end = compute_list_range(mapped)

    _cleanup(client, start, end)
    try:
        _create_fixtures(client, start, end)
        _update_fixtures(client, start, end)
        _assert_titles_updated(client, start, end)
        _delete_fixtures(client, start, end)
    finally:
        _cleanup(client, start, end)
