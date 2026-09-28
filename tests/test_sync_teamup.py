"""Unit tests for the JSON->Teamup sync logic: field mapping, rrule/
UNTIL computation, create/update/delete bucketing, and the
skip-and-flag policy for malformed entries. The Teamup HTTP layer is
mocked throughout -- nothing here touches the network."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from sync_teamup import (
    build_offset_datetime,
    build_payloads,
    build_rrule,
    compute_list_range,
    execute_sync,
    fetch_remote_index,
    map_event_to_payload,
    plan_sync,
    until_utc,
)

SUBCALENDAR_ID = 16069515

WEEKLY_EVENT = {
    "id": "weekly-event-1",
    "title": "Weekly Pickup",
    "location": "https://maps.example/x",
    "notes": "$20 drop in",
    "recurrenceType": "weekly",
    "dayOfWeek": "TU",
    "startDate": "2026-09-22",
    "endDate": "2026-11-10",
    "startTime": "20:00",
    "endTime": "21:00",
    "timezone": "America/New_York",
}

ONCE_EVENT = {
    "id": "once-event-1",
    "title": "One-off Tournament",
    "location": "https://maps.example/y",
    "notes": "bring cleats",
    "recurrenceType": "once",
    "date": "2026-10-03",
    "startTime": "13:00",
    "endTime": "18:00",
    "timezone": "America/New_York",
}


@pytest.mark.unit
def test_until_utc_converts_local_end_of_day_to_utc():
    """2026-11-10 23:59:59 America/New_York is EST (UTC-5) -> 04:59:59Z
    the next day, not a naive same-day UTC stamp."""
    assert until_utc("2026-11-10", "America/New_York") == "20261111T045959Z"


@pytest.mark.unit
def test_build_offset_datetime_carries_correct_dst_offset():
    """The same timezone name must yield different UTC offsets either
    side of a DST transition."""
    dt_edt = build_offset_datetime("2026-09-22", "20:00", "America/New_York")
    assert dt_edt == "2026-09-22T20:00:00-04:00"
    dt_est = build_offset_datetime("2026-11-10", "20:00", "America/New_York")
    assert dt_est == "2026-11-10T20:00:00-05:00"


@pytest.mark.unit
def test_build_rrule_shape():
    """rrule string matches the FREQ=WEEKLY;BYDAY=...;UNTIL=... shape
    the ticket's API research specifies."""
    rrule = build_rrule(WEEKLY_EVENT)
    assert rrule == "FREQ=WEEKLY;BYDAY=TU;UNTIL=20261111T045959Z"


@pytest.mark.unit
def test_map_event_to_payload_weekly():
    """A weekly JSON event maps to one Teamup payload carrying an
    rrule, not one payload per occurrence."""
    mapped = map_event_to_payload(WEEKLY_EVENT, SUBCALENDAR_ID)
    assert mapped.id == "weekly-event-1"
    assert mapped.is_recurring is True
    assert mapped.effective_end_date == "2026-11-10"
    payload = mapped.payload
    assert payload["subcalendar_ids"] == [SUBCALENDAR_ID]
    assert payload["remote_id"] == "weekly-event-1"
    assert payload["title"] == "Weekly Pickup"
    assert payload["location"] == "https://maps.example/x"
    assert payload["notes"] == "$20 drop in"
    assert payload["start_dt"] == "2026-09-22T20:00:00-04:00"
    assert payload["end_dt"] == "2026-09-22T21:00:00-04:00"
    assert payload["rrule"] == "FREQ=WEEKLY;BYDAY=TU;UNTIL=20261111T045959Z"


@pytest.mark.unit
def test_map_event_to_payload_once_has_no_rrule():
    """A one-off JSON event's payload must not carry an rrule field."""
    mapped = map_event_to_payload(ONCE_EVENT, SUBCALENDAR_ID)
    assert mapped.is_recurring is False
    assert mapped.effective_end_date == "2026-10-03"
    assert "rrule" not in mapped.payload
    assert mapped.payload["start_dt"] == "2026-10-03T13:00:00-04:00"


@pytest.mark.unit
def test_map_event_to_payload_unknown_recurrence_type_raises_value_error():
    """An unrecognized recurrenceType must fail loudly, not silently
    default to weekly or once."""
    bad = dict(ONCE_EVENT, recurrenceType="daily")
    with pytest.raises(ValueError):
        map_event_to_payload(bad, SUBCALENDAR_ID)


@pytest.mark.unit
def test_map_event_to_payload_missing_field_raises_key_error():
    """A missing required schedule field must fail loudly, not be
    silently guessed or defaulted."""
    incomplete = dict(WEEKLY_EVENT)
    del incomplete["endDate"]
    with pytest.raises(KeyError):
        map_event_to_payload(incomplete, SUBCALENDAR_ID)


@pytest.mark.unit
def test_build_payloads_skips_and_flags_malformed_entries():
    """One malformed entry is skipped and flagged; the rest of the
    batch still syncs -- mirrors the ICS generator's policy."""
    incomplete = dict(ONCE_EVENT, id="broken-event")
    del incomplete["date"]
    events = [WEEKLY_EVENT, incomplete]

    mapped, skipped = build_payloads(events, SUBCALENDAR_ID)

    assert set(mapped) == {"weekly-event-1"}
    assert len(skipped) == 1
    assert skipped[0][0] == "broken-event"
    assert isinstance(skipped[0][1], KeyError)


@pytest.mark.unit
def test_build_payloads_all_valid_has_no_skips():
    """A fully well-formed batch produces zero skips."""
    mapped, skipped = build_payloads(
        [WEEKLY_EVENT, ONCE_EVENT], SUBCALENDAR_ID
    )
    assert set(mapped) == {"weekly-event-1", "once-event-1"}
    assert not skipped


@pytest.mark.unit
def test_compute_list_range_uses_today_and_furthest_end_date():
    """The list range starts today and extends through the JSON's
    furthest effective end date."""
    mapped, _ = build_payloads([WEEKLY_EVENT, ONCE_EVENT], SUBCALENDAR_ID)

    start, end = compute_list_range(mapped)

    assert start == date.today().isoformat()
    assert end == "2026-11-10"  # WEEKLY_EVENT's endDate is the furthest


@pytest.mark.unit
def test_compute_list_range_empty_mapped_returns_today_twice():
    """No valid events still yields a well-formed (today, today) range
    rather than raising on an empty max()."""
    start, end = compute_list_range({})
    assert start == end == date.today().isoformat()


@pytest.mark.unit
def test_fetch_remote_index_dedupes_recurring_occurrences():
    """Multiple occurrences of one recurring series share a remote_id
    on Teamup's list endpoint; only one internal id should be kept per
    remote_id (any occurrence's id works for a redit=all operation)."""
    client = MagicMock()
    client.list_events.return_value = [
        {"id": "111-rid-1", "remote_id": "series-a", "series_id": 111},
        {"id": "111-rid-2", "remote_id": "series-a", "series_id": 111},
        {"id": "222", "remote_id": "one-off-b", "series_id": None},
        {"id": "no-remote-id-event", "remote_id": None, "series_id": None},
    ]

    index = fetch_remote_index(client, "2026-01-01", "2026-02-01")

    assert index == {
        "series-a": {"internal_id": "111-rid-1", "is_recurring": True},
        "one-off-b": {"internal_id": "222", "is_recurring": False},
    }
    client.list_events.assert_called_once_with("2026-01-01", "2026-02-01")


@pytest.mark.unit
def test_plan_sync_buckets_create_update_delete():
    """A JSON id absent from Teamup is a create, present in both is an
    update, and a Teamup remote_id absent from the JSON is a delete."""
    mapped, _ = build_payloads([WEEKLY_EVENT, ONCE_EVENT], SUBCALENDAR_ID)
    remote_index = {
        "once-event-1": {"internal_id": "1", "is_recurring": False},
        "stale-event": {"internal_id": "2", "is_recurring": False},
    }

    plan = plan_sync(mapped, remote_index)

    assert plan.creates == ["weekly-event-1"]
    assert plan.updates == ["once-event-1"]
    assert plan.deletes == ["stale-event"]


@pytest.mark.unit
def test_execute_sync_creates_new_events():
    """A create-bucket entry is POSTed and nothing else is touched."""
    mapped, _ = build_payloads([WEEKLY_EVENT], SUBCALENDAR_ID)
    remote_index: dict = {}
    plan = plan_sync(mapped, remote_index)
    client = MagicMock()

    execute_sync(client, mapped, remote_index, plan)

    client.create_event.assert_called_once_with(
        mapped["weekly-event-1"].payload
    )
    client.update_event.assert_not_called()
    client.delete_event.assert_not_called()


@pytest.mark.unit
def test_execute_sync_updates_once_event_with_plain_put():
    """A one-off update-bucket entry is PUT to its internal id, with
    the internal id also set on the payload's own `id` field (Teamup
    requires the body's id to match the URL's, confirmed live)."""
    mapped, _ = build_payloads([ONCE_EVENT], SUBCALENDAR_ID)
    remote_index = {
        "once-event-1": {"internal_id": "555", "is_recurring": False}
    }
    plan = plan_sync(mapped, remote_index)
    client = MagicMock()

    execute_sync(client, mapped, remote_index, plan)

    client.create_event.assert_not_called()
    client.delete_event.assert_not_called()
    client.update_event.assert_called_once()
    call_args = client.update_event.call_args
    assert call_args[0][0] == "555"
    assert call_args[0][1]["id"] == "555"
    assert call_args[0][1]["remote_id"] == "once-event-1"


@pytest.mark.unit
def test_execute_sync_updates_weekly_event_via_delete_and_recreate():
    """A recurring series is never PUT in place -- live testing showed
    that's unreliable. Update means delete (redit=all) then recreate."""
    mapped, _ = build_payloads([WEEKLY_EVENT], SUBCALENDAR_ID)
    remote_index = {
        "weekly-event-1": {"internal_id": "999", "is_recurring": True}
    }
    plan = plan_sync(mapped, remote_index)
    client = MagicMock()

    execute_sync(client, mapped, remote_index, plan)

    client.update_event.assert_not_called()
    client.delete_event.assert_called_once_with("999", redit_all=True)
    client.create_event.assert_called_once_with(
        mapped["weekly-event-1"].payload
    )


@pytest.mark.unit
def test_execute_sync_deletes_recurring_series_with_redit_all():
    """A delete-bucket entry passes redit_all according to whether the
    Teamup record it resolves to is part of a recurring series."""
    mapped: dict = {}
    remote_index = {
        "gone-weekly": {"internal_id": "10", "is_recurring": True},
        "gone-once": {"internal_id": "20", "is_recurring": False},
    }
    plan = plan_sync(mapped, remote_index)
    client = MagicMock()

    execute_sync(client, mapped, remote_index, plan)

    client.delete_event.assert_any_call("10", redit_all=True)
    client.delete_event.assert_any_call("20", redit_all=False)
    assert client.delete_event.call_count == 2
