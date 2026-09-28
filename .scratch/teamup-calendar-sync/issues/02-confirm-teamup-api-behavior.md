# Confirm Teamup's real API behavior

Type: research
Status: resolved
Blocked by: 05 (resolved)

## Question

`hugo-natenite.net/HOSTED.md` names Teamup as the strongest hosted-calendar candidate for this project's upsert-by-own-id model, but flags its core API schema as **unconfirmed**: apidocs.teamup.com is a JS-rendered Stoplight site that two direct-fetch attempts in that prior research could not get past the page shell, so the `remote_id` upsert field and the `rrule` field are known only from search-indexed snippets, never a directly-read page.

This project now has a real Teamup calendar and a real API key (see [Set up local Teamup credentials file](01-teamup-credentials-file.md)). Resolve the open questions **empirically**, by making real API calls against that real calendar, rather than relying on docs that couldn't be directly read:

1. **Create**: create one one-off event and one recurring (weekly) event via the API. What request body shape actually works -- field names for title/location/description/start/end/timezone, and does a `remote_id`-equivalent field exist and accept an arbitrary caller-supplied string?
2. **Recurrence**: what field and format does Teamup actually want for a recurring event's rule -- is it a raw RFC5545 `RRULE` string, or something else? Confirm by creating the recurring event and then reading it back / viewing it in the Teamup UI to see if it expanded correctly.
3. **Upsert behavior**: call create a second time with the same `remote_id` (or whatever the actual field turns out to be) and the same event content. Does it error, silently create a duplicate, or update in place? If it doesn't self-dedupe, what's the correct pattern -- list/query by that id first, then branch between create and update?
4. **List/query**: does Teamup's list-events endpoint return the caller-supplied id field, so a sync run can diff "what's in Teamup" against "what's in the JSON" to know what to delete?
5. **Delete**: confirm the delete-event endpoint and what it needs (Teamup's own event id? the caller-supplied id?).
6. **Field mapping**: confirm how the JSON schema's `location`, `notes`, `timezone` map onto Teamup's actual event fields.

Clean up any test events created against the real calendar once each behavior is confirmed, unless the user prefers to leave them for manual inspection first.

## Answer

**Resolved on the third attempt.** A "Modify"-permission Access Key (obtained via ticket 05) has full read+write access to the calendar's one sub-calendar (`id: 16069515`, confirmed `readonly: false`). All six original questions were live-tested against the real Teamup calendar with real API calls. Every test event created (including a full 7-occurrence recurring series) was deleted afterward; a final sweep confirmed zero test events remain.

1. **Create**: `POST /{calendarKeyOrId}/events` works exactly as spec-described. `subcalendar_ids` (array) is required. Field names: `title`, `location`, `notes`, `start_dt`/`end_dt` (ISO 8601 with offset), `remote_id` (arbitrary caller-supplied string, accepted and echoed back verbatim).

2. **Recurrence**: the `rrule` field (raw RFC5545 string, e.g. `FREQ=WEEKLY;BYDAY=TU;UNTIL=20261110T235959Z`) on create works. A single POST creates one **series** (`series_id`); Teamup normalizes the `UNTIL` clause into the calendar's local offset on echo-back. Reading it back via `GET /events` over a date range **expands the series into one event object per occurrence** — each occurrence has a unique `id` (`{series_id}-rid-{epoch}`) but shares the same `series_id`, `remote_id`, and `rrule` string. `GET /events/{occurrenceId}` returns a single occurrence, not the whole series. The expansion is read/display-time only — writing remains one POST per series, matching the map's "one event + rrule" design.

3. **Upsert behavior — settled, and it does NOT self-dedupe.** Re-POSTing with a `remote_id` that already exists returns `HTTP 400 {"error":{"id":"event_not_unique","title":"Remote ID conflict", ...}}`. No duplicate is created and the existing event is left untouched (confirmed via follow-up GET showing only the original). **Correct pattern**: `GET /events` first to build a `remote_id → internal id` map of what currently exists, then branch per JSON entry between `POST` (create, if `remote_id` absent) and `PUT /events/{id}` (update, using the internal id, if present). This same map also identifies what to delete (an internal id in Teamup with no matching JSON `remote_id`).

4. **List/query with `remote_id`**: confirmed — every event and every expanded recurring occurrence returned by `GET /events` includes its `remote_id` field, exactly as set on create. Sufficient to diff Teamup's state against the JSON by `remote_id` alone.

5. **Delete**: `DELETE /events/{internalId}` works (smoke-tested previously, reconfirmed here for a recurring series with `?redit=all`, `200 OK`, all 7 occurrences removed in one call). `DELETE /events/0?remoteId=<remote_id>` (query-param addressing) also works, confirmed `200 OK` for **one-off** events. It did **not** work for deleting a whole recurring series by `remote_id` + `startTime` (`404 event_not_found` with both UTC and local start-time values tried) — recommend resolving `remote_id` to internal id first (via the same list call used for upsert detection above) and deleting by internal id with `redit=all` for series; that path is proven. The spec's alternative body-based `remote_id` delete mechanism (`eventId=0` + `{"remote_id": ...}` JSON body) also did **not** work as documented — it returned `400 event_missing_start_end_datetime`; not investigated further since the two working mechanisms above fully cover the sync engine's needs.

6. **Field mapping**: `location` → `location`, plain string, round-trips exactly. `notes` → `notes`, but comes back **HTML-wrapped** (`<p>...</p>`) even when plain text is sent — Teamup treats `notes` as rich text, not plain text. **Timezone (bonus finding, more rigorously confirmed)**: the prior smoke test's hypothesis ("`tz` derived from the offset in `start_dt`/`end_dt`") is **wrong**. Three events created with three different offsets (`-04:00`, `-07:00`, `+09:00`) all came back with the identical `"tz": "America/New_York"` — Teamup uses the offset only to compute the correct absolute instant (converting `start_dt`/`end_dt` accordingly), but the **displayed zone name is a fixed, calendar-level property**, not a per-event or per-offset one. No writable `tz`/`timezone` field exists on create/update (reconfirmed against spec). Practical implication: the sync engine can send any correct offset for `start_dt`/`end_dt` — there is no "right" timezone to choose beyond a correct absolute time, since the display zone is fixed regardless.

Full findings, evidence (redacted), request/response examples, and the delete-mechanism comparison table: [../../../docs/research/teamup-live-api-behavior.md](../../../docs/research/teamup-live-api-behavior.md)
