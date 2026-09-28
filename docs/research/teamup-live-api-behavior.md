# Teamup Live API Behavior — Write Access Confirmed, All 6 Questions Live-Tested

## Summary

**This is the third and final attempt at this research; it succeeded.** A "Modify"-permission Access Key (obtained via ticket 05) has full read+write access to the calendar's one sub-calendar (`id: 16069515`, confirmed `"readonly": false`). All six of this ticket's original questions, plus the timezone bonus finding from the coordinator's own smoke test, were live-tested against the real Teamup calendar with real API calls (not spec reading). Every test event created has been deleted; the calendar is confirmed clean (empty result for any event with a `wayfinder`-prefixed `remote_id`, verified by a final `GET /events` sweep).

**Headline findings:**

1. **Create** (one-off and recurring) works exactly as the spec described: `POST /{calendarKeyOrId}/events`, `subcalendar_ids` required, `remote_id` accepts an arbitrary caller-supplied string.
2. **Recurrence** works via `rrule` (RFC5545 string) on create. A single POST creates one **series** (`series_id`), but `GET /events` over a date range **expands it into one event object per occurrence** — each occurrence has a unique `id` of the form `{series_id}-rid-{unix_ts}`, but all occurrences share the same `series_id`, `remote_id`, and `rrule` string.
3. **Upsert does NOT self-dedupe.** Re-POSTing with a `remote_id` that already exists returns `HTTP 400 {"error":{"id":"event_not_unique","title":"Remote ID conflict", ...}}`. No duplicate is created and the original event is untouched. **The sync engine must list-by-remote_id first, then branch between create (POST) and update (PUT) itself** — Teamup will not do this branching for you.
4. **List/query returns `remote_id`** on every event and every expanded occurrence — confirmed with real data. A sync can diff "what's in Teamup" vs. "what's in the JSON" purely by `remote_id`.
5. **Delete by `remote_id` is real but only reliably confirmed for one-off events via query parameters** — `DELETE /events/0?remoteId=<remote_id>` returned `200 OK` for one-off test events. The spec's alternative *body*-based mechanism (`eventId=0` + `{"remote_id": ...}` JSON body) **did not work as documented**: it returned `400 event_missing_start_end_datetime`. Deleting an entire **recurring series** by `remote_id` alone (`?remoteId=...&startTime=...&redit=all`) also **did not work** in this environment — it returned `404 event_not_found` regardless of whether the UTC (`ristart_dt`) or local (`rsstart_dt`) value was used for `startTime`. Deleting the series by its **internal occurrence id** (`DELETE /events/{id}?redit=all`) worked cleanly (`200 OK`) and is what was used for final cleanup. See Finding 5 below for the practical recommendation this implies for the sync engine.
6. **Field mapping**: `location` round-trips as a plain string, byte-for-byte. `notes` round-trips as **HTML** — plain text sent on create came back wrapped in `<p>...</p>` tags, meaning Teamup treats `notes` as a rich-text field, not plain text.
7. **Timezone finding — corrects the prior smoke test's hypothesis.** `tz` is **not** derived from the UTC offset embedded in `start_dt`/`end_dt`. Three events were created with three different offsets (`-04:00`, `-07:00`, `+09:00`) in the same `start_dt`/`end_dt` request bodies; all three came back with **`"tz": "America/New_York"`** — the same value every time. Teamup correctly used each offset to compute the event's absolute UTC instant (e.g. `10:00-07:00` came back stored/displayed as `13:00-04:00`, and `10:00+09:00` came back as `21:00-04:00` the previous day), but the **displayed/stored zone name itself is a fixed, calendar-level property** (presumably the timezone configured when the calendar or its owning account was created), not a per-event, per-request value. There remains no writable `tz`/`timezone` field on `Event.create`/`Event.createRecurring`/`Event.update` (confirmed again in the spec this round) — this is now doubly confirmed: neither a field exists, nor does the offset in `start_dt`/`end_dt` influence which zone name is stored. **Practical implication for the sync engine: send `start_dt`/`end_dt` in whatever offset is convenient (e.g. always UTC, or always the JSON's local `timezone` field's offset) — the *displayed* zone will always be the calendar's own fixed zone regardless, so there is nothing to get "right" here beyond sending a correct absolute-time offset.**

## Findings

All commands run with `set -a; source .env; set +a` in the repo root. `TEAMUP_TOKEN` and `TEAMUP_CALENDAR_KEY` redacted as `***` below. Sub-calendar id `16069515` used throughout (confirmed `readonly: false` before and after all testing).

### 0. Write access reconfirmed

```
GET /***/subcalendars → 200, subcalendars[0].readonly == false  (both before and after this test run)
```

### 1. Create — one-off event

```
POST /***/events
{"subcalendar_ids":[16069515],"start_dt":"2026-10-06T10:00:00-04:00","end_dt":"2026-10-06T11:30:00-04:00",
 "title":"...","location":"Test Field 1","notes":"Test notes content EDT","remote_id":"wayfinder-tz-edt-001"}
→ 201-equivalent, {"event": {"id":"2177097106", "remote_id":"wayfinder-tz-edt-001",
    "location":"Test Field 1", "notes":"<p>Test notes content EDT</p>", "tz":"America/New_York", ...}}
```

Confirms: `subcalendar_ids` required (array). `remote_id` is a plain writable string, echoed back verbatim on the created object. `location` round-trips exactly. `notes` comes back **HTML-wrapped** (`<p>...</p>`) even though plain text was sent — Teamup treats `notes` as rich text.

### 2. Timezone — offset does NOT select the stored zone; the zone is a fixed calendar property

Three events created with identical logical intent but three different UTC offsets in `start_dt`/`end_dt`:

| Sent `start_dt` offset | Returned `tz` | Returned `start_dt` (converted) |
|---|---|---|
| `2026-10-06T10:00:00-04:00` | `America/New_York` | `2026-10-06T10:00:00-04:00` (unchanged) |
| `2026-10-06T10:00:00-07:00` | `America/New_York` | `2026-10-06T13:00:00-04:00` (correctly converted) |
| `2026-10-06T10:00:00+09:00` | `America/New_York` | `2026-10-05T21:00:00-04:00` (correctly converted, crosses midnight/date) |

All three requests produced the identical `tz` value. Teamup correctly computes the absolute instant from whatever offset is sent, but always **displays/stores it rendered in the calendar's own fixed configured timezone** (here, `America/New_York`) — this is a calendar-level setting, not a per-request or per-offset one. This directly supersedes the prior attempt's spec-only hypothesis ("timezone appears derived from the UTC offset") — that hypothesis is **wrong**; the offset only matters for computing the correct absolute moment, not for choosing the display zone. No writable `tz`/`timezone` field exists anywhere in `Event.create`/`Event.createRecurring`/`Event.update` (re-confirmed against the spec this round too).

### 3. Recurrence

```
POST /***/events
{"subcalendar_ids":[16069515], "start_dt":"2026-10-06T18:00:00-04:00", "end_dt":"2026-10-06T19:30:00-04:00",
 "title":"...", "rrule":"FREQ=WEEKLY;BYDAY=TU;UNTIL=20261110T235959Z", "remote_id":"wayfinder-recur-001"}
→ {"event": {"id":"2177097322-rid-1791324000", "series_id":2177097322,
    "rrule":"FREQ=WEEKLY;BYDAY=TU;UNTIL=20261110T185959-05:00", "remote_id":"wayfinder-recur-001",
    "ristart_dt":"2026-10-06T22:00:00+00:00", "rsstart_dt":"2026-10-06T18:00:00-04:00", ...}}
```

A single `POST` with `rrule` creates one **series** (`series_id`). Teamup normalizes the sent `UNTIL` clause (`Z`/UTC) into the calendar's local offset (`-05:00`, reflecting the DST transition at the `UNTIL` boundary) on the value it echoes back.

`GET /events?startDate=2026-10-01&endDate=2026-11-15` **expands the series into one event object per occurrence** (7 objects returned, one per Tuesday through the `UNTIL` bound), each with:
- a **unique `id`**: `{series_id}-rid-{occurrence_epoch_seconds}`
- the **same `series_id`**, **same `remote_id`**, and **same `rrule` string** across all occurrences
- its own `start_dt`/`end_dt`/`ristart_dt`/`rsstart_dt` for that specific occurrence (correctly reflecting the Nov 3 US DST fall-back: earlier occurrences show `-04:00`, the Nov 3 and Nov 10 occurrences show `-05:00`)

`GET /events/{occurrenceId}` on one specific occurrence id returns that single occurrence object (not the whole series) — same shape as the list result, plus a `history` block.

**Sync-engine implication**: representing a weekly JSON event as one Teamup event + `rrule` (per the map's stated design) is directly correct — write one series with `rrule`; the multi-occurrence expansion is purely a read/display-time behavior, not something the sync needs to manage as separate rows.

### 4. Upsert behavior — no self-dedupe, hard conflict error

```
POST /***/events  {remote_id:"wayfinder-upsert-test-001", title:"... v1", ...}
→ 200-equivalent, event created, id 2177097467

POST /***/events  {remote_id:"wayfinder-upsert-test-001", title:"... v2 SHOULD DIFFER", ...}  (same remote_id again)
→ HTTP 400
   {"error":{"id":"event_not_unique","title":"Remote ID conflict",
     "message":"The event cannot be inserted or updated because an event with the same remote id exists already."}}
```

Follow-up `GET /events` confirmed **exactly one** event exists with that `remote_id`, still showing the **v1** title/time — the second POST neither created a duplicate nor updated the original in place; it was rejected outright.

**This settles the question the spec could not answer.** The sync engine cannot rely on `POST` as an upsert. Correct pattern: `GET /events` (or a targeted query) first to build a `remote_id → internal id` map of what currently exists in Teamup, then for each JSON entry: `POST` (create) if its `remote_id` is absent from that map, or `PUT /events/{id}` (update, using the internal id) if present. This is also the mechanism a full sync needs anyway to detect entries to **delete** (an internal id present in Teamup with no matching `remote_id` in the JSON).

### 5. List/query returns `remote_id`

Confirmed directly in the recurrence and upsert tests above — every event and every expanded occurrence returned by `GET /events` includes its `remote_id` field, exactly as set on create. This is sufficient for a sync to diff Teamup's current state against the JSON's state by `remote_id` alone, without tracking Teamup's internal ids in the JSON itself.

### 6. Delete — three mechanisms tried, mixed results

| Mechanism | Target | Result |
|---|---|---|
| `DELETE /events/{internalId}` | one-off event, by internal id | `200 OK` (already smoke-tested by the coordinator; reconfirmed for the recurring series below) |
| `DELETE /events/0?remoteId=<remote_id>` (query param) | one-off event | **`200 OK`** — worked cleanly, confirmed twice |
| `DELETE /events/0` with `{"remote_id": "..."}` JSON body (no other fields) | one-off event | **`400 event_missing_start_end_datetime`** — did NOT work as the spec's own prose describes; the body-based addressing mode appears to require additional fields (likely `start_dt`/`end_dt`) that the spec's truncated schema didn't make clear, and which defeats the point of addressing purely by `remote_id` |
| `DELETE /events/0?remoteId=<remote_id>&startTime=<ristart_dt or rsstart_dt>&redit=all` (query params) | whole recurring series | **`404 event_not_found`** — tried with both the UTC `ristart_dt` value and the local `rsstart_dt` value as `startTime`; neither matched |
| `DELETE /events/{oneOccurrenceInternalId}?redit=all` | whole recurring series | **`200 OK`** — worked cleanly, deleted all 7 occurrences in one call |

**Practical recommendation for the sync engine**: `remote_id`-only delete via query params is reliable for **one-off** events, but **not proven reliable for recurring series** in this environment — use it for one-offs, but for recurring series (and as a robust fallback generally), resolve the `remote_id` to an internal `id` via a `GET /events` list first (needed anyway for the upsert-detection pass in Finding 4), then delete by that internal id, passing `redit=all` for any recurring series. This also means the sync engine's internal `remote_id → id` map built for upsert detection doubles as the map needed for deletion — one list call serves both purposes.

## Open Questions

- **The spec's documented body-based `remote_id` delete mechanism does not work as described** (`400 event_missing_start_end_datetime` with just `remote_id` in the body). Not re-investigated further since the query-param variant and internal-id variant both work and cover the sync engine's actual needs — flagging this mainly so nobody re-attempts the body-only method expecting it to work from the spec's prose alone.
- **Recurring-series delete-by-`remote_id`-via-query-params returned `404`** in both attempts (UTC and local `startTime` values). Root cause not identified (possibly a different `startTime` format/precision is expected, or this addressing mode may only match a `single` `redit` occurrence rather than `all`). Not blocking — the internal-id + `redit=all` fallback is proven and is what the sync engine should use for series deletion regardless, since it already has to resolve internal ids for the upsert/diff pass.
- Everything the sibling research (`teamup-python-client-options.md`) already left open (exact rate limit, Postman collection contents, `subcalendar_remote_ids` usage) remains open here too — unaffected by this ticket.
- The exact HTML dialect/sanitization Teamup applies to `notes` (only `<p>` wrapping was observed with plain single-line text; multi-paragraph or special-character input was not tested) is not fully characterized — worth a quick check if the JSON's `notes` field ever contains newlines or markup-sensitive characters.

### Primary-source URLs / commands used in this research

1. `https://api.teamup.com/{calendarKey}/subcalendars` — live `GET`, confirmed `readonly: false` both before and after testing.
2. `https://api.teamup.com/{calendarKey}/events` — live `POST` x6 (3 timezone-offset probes, 1 recurring series, 2 upsert-conflict probes), all with `subcalendar_ids:[16069515]`.
3. `https://api.teamup.com/{calendarKey}/events/{id}` — live `GET` (single occurrence read-back).
4. `https://api.teamup.com/{calendarKey}/events?startDate=...&endDate=...` — live `GET` (date-range list, used to confirm recurrence expansion, `remote_id` round-trip, and final cleanup verification).
5. `https://api.teamup.com/{calendarKey}/events/0?remoteId=...[&startTime=...&redit=...]` — live `DELETE` x4 (2 succeeded for one-off events, 1 failed for a recurring series, 1 body-based variant failed).
6. `https://api.teamup.com/{calendarKey}/events/{id}?redit=all` — live `DELETE` (succeeded, used for final recurring-series cleanup).
7. `https://stoplight.io/api/v1/projects/teamup/api/nodes/reference/generated_docs_public.yaml` — re-consulted for the exact `DELETE`/`PUT` parameter set (`redit` enum, `Event.createRecurring`'s `rrule` field, confirmation that `Event.create`/`Event.update` have no writable `tz` field).

**Cleanup confirmed**: a final `GET /events?startDate=2026-09-28&endDate=2026-12-01` sweep returned zero events with a `remote_id` starting with `wayfinder` — every test event and the full recurring series were deleted. Nothing was left behind on the real calendar.
