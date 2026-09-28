#!/usr/bin/env python3
"""One-way, idempotent, full sync of data/events.json into a real Teamup
calendar.

data/events.json is the sole source of truth (see
hugo-natenite.net/scripts/sync_calendar.py for the sibling ICS-generator
version of this same JSON schema/policy). Each JSON event's own stable
`id` is used directly as Teamup's `remote_id`, so re-running this script
recognizes "this is the same event" across runs without tracking
Teamup's internal ids anywhere outside Teamup itself.

Teamup's `POST /events` does not upsert -- re-posting an existing
`remote_id` returns `400 event_not_unique` rather than updating in
place (confirmed live; see docs/research/teamup-live-api-behavior.md).
So every run first lists Teamup's current events over a date range
covering everything in the JSON, builds a `remote_id -> internal id`
map from that, and only then decides create vs. update vs. delete per
JSON event -- Teamup will not branch this for you.

Recurring (weekly) events are written as a single Teamup event with an
`rrule`, matching the JSON's own recurrence model -- never one row per
occurrence (Teamup's `GET /events` expands a series into one object per
occurrence at read time, but that is purely a display-time behavior).

Updating a recurring series is NOT done via `PUT .../{id}?redit=all`.
Live smoke-testing that approach (see this ticket's Answer section)
showed it is unreliable -- one attempt silently dropped an occurrence
from the series, another returned an empty response body. Instead, a
changed weekly event is deleted (by internal id, `redit=all` -- proven
reliable) and recreated fresh via POST with the same `remote_id`. A
changed one-off event uses a normal `PUT` (proven reliable, and
required by Teamup to also carry the internal `id` in the body).

Usage: python3 scripts/sync_teamup.py
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from teamup_client import TeamupApiError, TeamupClient

REPO_ROOT = Path(__file__).resolve().parent.parent
EVENTS_PATH = REPO_ROOT / "data" / "events.json"

# This project uses a single flat Teamup calendar with one sub-calendar
# (see map.md's "Standing decisions" -- no sub-calendar routing needed).
# Overridable via env var only because that's free and harmless; there
# is no multi-sub-calendar use case in scope for this project.
DEFAULT_SUBCALENDAR_ID = 16069515


@dataclass
class MappedEvent:
    """One JSON event, translated into a Teamup write payload.

    `effective_end_date` is the latest date this event could still
    appear on the calendar (an `endDate` for weekly events, the `date`
    itself for one-off events) -- used to size the `GET /events` range
    that has to cover every currently-relevant Teamup event.
    """

    id: str
    payload: dict[str, Any]
    is_recurring: bool
    effective_end_date: str


@dataclass
class SyncPlan:
    """The create/update/delete buckets for one sync run, keyed by
    remote_id (JSON `id` for creates/updates, Teamup's own record of
    `remote_id` for deletes since the JSON entry is gone by then)."""

    creates: list[str]
    updates: list[str]
    deletes: list[str]


def until_utc(end_date_str: str, tzid: str) -> str:
    """RRULE's UNTIL must be a real UTC instant -- convert local
    end-of-day in the event's own timezone, rather than treating the
    local date as if it were already UTC (which would shift it by the
    zone's offset). Mirrors hugo-natenite.net/scripts/sync_calendar.py's
    helper of the same name, adapted for Teamup's rrule instead of ICS."""
    local_end_of_day = datetime.strptime(end_date_str, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=ZoneInfo(tzid)
    )
    return local_end_of_day.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_offset_datetime(date_str: str, time_str: str, tzid: str) -> str:
    """Combine a YYYY-MM-DD date and HH:MM time into an ISO 8601
    datetime carrying that timezone's correct UTC offset for that
    specific date (so DST transitions land on the right side). Teamup's
    *displayed* zone is a fixed calendar-level property regardless of
    which correct offset is sent (confirmed live), so any correct
    offset works -- this uses the JSON's own `timezone` field."""
    naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return naive.replace(tzinfo=ZoneInfo(tzid)).isoformat()


def build_rrule(event: dict[str, Any]) -> str:
    """Build an RFC 5545 rrule string for a weekly JSON event."""
    until = until_utc(event["endDate"], event["timezone"])
    return f"FREQ=WEEKLY;BYDAY={event['dayOfWeek']};UNTIL={until}"


def map_event_to_payload(
    event: dict[str, Any], subcalendar_id: int
) -> MappedEvent:
    """Translate one JSON event into a Teamup write payload.

    Raises KeyError for a missing required field or ValueError for an
    unrecognized `recurrenceType` -- callers must catch both and skip
    the event rather than guessing/defaulting a value (this project's
    standing policy, same as the ICS generator)."""
    recurrence_type = event["recurrenceType"]
    tzid = event["timezone"]

    if recurrence_type == "weekly":
        schedule_date = event["startDate"]
        effective_end_date = event["endDate"]
        is_recurring = True
    elif recurrence_type == "once":
        schedule_date = event["date"]
        effective_end_date = event["date"]
        is_recurring = False
    else:
        raise ValueError(f"Unknown recurrenceType {recurrence_type!r}")

    payload: dict[str, Any] = {
        "subcalendar_ids": [subcalendar_id],
        "start_dt": build_offset_datetime(
            schedule_date, event["startTime"], tzid
        ),
        "end_dt": build_offset_datetime(schedule_date, event["endTime"], tzid),
        "title": event["title"],
        "location": event["location"],
        "notes": event["notes"],
        "remote_id": event["id"],
    }
    if is_recurring:
        payload["rrule"] = build_rrule(event)

    return MappedEvent(
        id=event["id"],
        payload=payload,
        is_recurring=is_recurring,
        effective_end_date=effective_end_date,
    )


def build_payloads(
    events: list[dict[str, Any]], subcalendar_id: int
) -> tuple[dict[str, MappedEvent], list[tuple[str, Exception]]]:
    """Map every JSON event to a Teamup payload, skipping and flagging
    (never silently defaulting) any entry missing a required field."""
    mapped: dict[str, MappedEvent] = {}
    skipped: list[tuple[str, Exception]] = []
    for event in events:
        try:
            entry = map_event_to_payload(event, subcalendar_id)
        except (KeyError, ValueError) as err:
            skipped.append((event.get("id", "<no id>"), err))
            continue
        mapped[entry.id] = entry
    return mapped, skipped


def compute_list_range(mapped: dict[str, MappedEvent]) -> tuple[str, str]:
    """The `GET /events` range must cover every event currently on
    Teamup that this sync might need to touch: from today (past events
    don't need diffing) through the JSON's furthest `endDate`/`date`."""
    today = date.today().isoformat()
    if not mapped:
        return today, today
    furthest = max(entry.effective_end_date for entry in mapped.values())
    return today, max(furthest, today)


def fetch_remote_index(
    client: TeamupClient, start_date: str, end_date: str
) -> dict[str, dict[str, Any]]:
    """Build a `remote_id -> {internal_id, is_recurring}` map of
    everything currently on Teamup in range. A recurring series is
    expanded into multiple occurrences sharing one `remote_id` by
    Teamup's list endpoint (read-time-only behavior) -- the first
    occurrence encountered is kept, since any one occurrence's internal
    id works for a `redit=all` update/delete of the whole series."""
    index: dict[str, dict[str, Any]] = {}
    for remote_event in client.list_events(start_date, end_date):
        remote_id = remote_event.get("remote_id")
        if not remote_id or remote_id in index:
            continue
        index[remote_id] = {
            "internal_id": remote_event["id"],
            "is_recurring": remote_event.get("series_id") is not None,
        }
    return index


def plan_sync(
    mapped: dict[str, MappedEvent], remote_index: dict[str, dict[str, Any]]
) -> SyncPlan:
    """Bucket JSON events against Teamup's current state: create
    (JSON id absent from Teamup), update (present in both), delete
    (present on Teamup, absent from the JSON). Pure function, no I/O --
    kept separate so the bucketing logic is directly unit-testable."""
    json_ids = set(mapped)
    remote_ids = set(remote_index)
    return SyncPlan(
        creates=sorted(json_ids - remote_ids),
        updates=sorted(json_ids & remote_ids),
        deletes=sorted(remote_ids - json_ids),
    )


def execute_sync(
    client: TeamupClient,
    mapped: dict[str, MappedEvent],
    remote_index: dict[str, dict[str, Any]],
    plan: SyncPlan,
) -> None:
    """Perform the actual Teamup writes for one sync plan.

    Update handling differs by recurrence: a one-off event gets a
    normal `PUT` (idempotent by internal id, confirmed live -- Teamup
    requires the body's own `id` to match the URL's). A weekly event
    is deleted (`redit=all`) and recreated instead of edited in place --
    see this module's docstring for why in-place series edits were
    rejected after live testing."""
    for event_id in plan.creates:
        client.create_event(mapped[event_id].payload)

    for event_id in plan.updates:
        entry = mapped[event_id]
        info = remote_index[event_id]
        if entry.is_recurring:
            client.delete_event(info["internal_id"], redit_all=True)
            client.create_event(entry.payload)
        else:
            payload = dict(entry.payload)
            payload["id"] = info["internal_id"]
            client.update_event(info["internal_id"], payload)

    for remote_id in plan.deletes:
        info = remote_index[remote_id]
        client.delete_event(
            info["internal_id"], redit_all=info["is_recurring"]
        )


def load_events() -> list[dict[str, Any]]:
    """Load the events array out of data/events.json."""
    data = json.loads(EVENTS_PATH.read_text())
    return list(data["events"])


def mass_deletion_guard_error(
    plan: SyncPlan, mapped: dict[str, MappedEvent]
) -> str | None:
    """Refuse to run a plan that would delete every currently-synced
    event while the JSON produced zero valid ones -- almost certainly
    a broken/empty/misread data/events.json, not a deliberate "wipe my
    whole calendar" intent (this happened for real: an unrelated bug
    elsewhere once called the sync primitives this same way and
    silently deleted a fully-populated real calendar). Returns an
    error message to abort with, or None if the plan looks safe."""
    if plan.deletes and not mapped:
        return (
            f"Refusing to run: {len(plan.deletes)} event(s) would be "
            "deleted, but data/events.json produced zero valid mapped "
            "events. This looks like a broken or empty JSON file, not "
            "an intentional full wipe -- check the file before "
            "re-running."
        )
    return None


def main() -> int:
    """Run one full sync. Exit codes: 0 = every JSON event synced
    cleanly, 1 = at least one entry was skipped (schema problem) but
    the rest synced, 2 = missing credentials or a Teamup API failure
    aborted the run partway through."""
    load_dotenv()
    token = os.environ.get("TEAMUP_TOKEN")
    calendar_key = os.environ.get("TEAMUP_CALENDAR_KEY")
    if not token or not calendar_key:
        print(
            "Missing TEAMUP_TOKEN or TEAMUP_CALENDAR_KEY -- check .env",
            file=sys.stderr,
        )
        return 2

    subcalendar_id = int(
        os.environ.get("TEAMUP_SUBCALENDAR_ID", DEFAULT_SUBCALENDAR_ID)
    )

    events = load_events()
    mapped, skipped = build_payloads(events, subcalendar_id)
    for event_id, err in skipped:
        print(f"Skipped event {event_id!r}: {err}", file=sys.stderr)

    client = TeamupClient(calendar_key, token)
    start_date, end_date = compute_list_range(mapped)

    try:
        remote_index = fetch_remote_index(client, start_date, end_date)
        plan = plan_sync(mapped, remote_index)
        guard_error = mass_deletion_guard_error(plan, mapped)
        if guard_error:
            print(guard_error, file=sys.stderr)
            return 2
        execute_sync(client, mapped, remote_index, plan)
    except TeamupApiError as err:
        print(f"Teamup API call failed, aborting sync: {err}", file=sys.stderr)
        return 2

    print(
        f"Sync complete: {len(plan.creates)} created, "
        f"{len(plan.updates)} updated, {len(plan.deletes)} deleted, "
        f"{len(skipped)} skipped."
    )
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
