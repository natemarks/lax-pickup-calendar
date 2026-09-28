# Design and build the JSON -> Teamup sync engine

Type: task
Status: resolved
Blocked by: 02 (resolved)

## Question

All the API-contract unknowns are now resolved (see [Confirm Teamup's real API behavior](02-confirm-teamup-api-behavior.md) and `docs/research/teamup-live-api-behavior.md`). This ticket is execution, not investigation -- per this map's Notes, execution is explicitly in scope. Build the actual one-way sync engine and run it for real, since this map's "done" is a populated calendar, not just passing tests.

Design decisions to settle while building (not open API questions anymore, just implementation choices):

1. **`remote_id` value**: use the JSON's own stable `id` field directly (unprefixed, or with a short project prefix like `lax-` if collision with anything else ever seems plausible -- probably unnecessary for a single-purpose calendar).
2. **List-then-diff algorithm**: one `GET /events` call over the JSON's full date span, building a `remote_id -> Teamup internal id` map from the results, then bucket the JSON's events into create (JSON id absent from the map) / update (present) / delete (map ids absent from the JSON).
3. **Change detection for the update bucket**: decide whether to diff fields before calling `PUT`, or always `PUT` unconditionally (Teamup's `PUT` looked idempotent-by-internal-id in testing, but this ticket's live testing did not actually exercise `PUT` -- do at least one live smoke call early here to confirm before committing to "always PUT").
4. **Recurring-series handling on update and delete**: wire `?redit=all` for both, mirroring the delete finding (plain `remote_id`-based delete returned `404` for a recurring series in testing; internal id + `redit=all` worked).
5. **Field mapping**: `title`/`location`/`date`+`startTime`+`endTime`/`recurrenceType`->`rrule` map directly; send `notes` as plain text (Teamup wraps it in `<p>...</p>` on return -- don't assume byte-identical round-trip if diffing raw strings for change detection); the JSON's `timezone` field has no Teamup write-time counterpart (Teamup's `tz` is a fixed calendar-level setting) but is still needed to construct the correct UTC offset in `start_dt`/`end_dt`.
6. **Incomplete-entry handling**: reuse the original spec's policy (skip and flag entries missing required schedule fields, never silently guess/default) -- same convention as `hugo-natenite.net/scripts/sync_calendar.py`.
7. **Testing split**: `make unit` mocks the Teamup API client against the request/response shapes captured in `docs/research/teamup-live-api-behavior.md` (create success, `event_not_unique` conflict, recurrence expansion, delete success/404); `make integration` runs the same list-diff-create/update/delete flow live against the real calendar using `.env` credentials, following the cleanup-and-verify pattern this research established (tag test events distinctly if any test fixtures are used beyond the real data, verify a final sweep).
8. **Makefile target**: add whatever's needed to invoke the sync (e.g. `make sync-teamup`), consistent with this project's existing `static`/`unit`/`integration` target conventions.

**This map's actual finish line**: once the engine is built and tested, run it for real against `data/events.json` so the live Teamup calendar is populated and matches the JSON -- that's what closes out this ticket and the map's destination, not just green tests.

## Answer

Built and run for real. `scripts/teamup_client.py` (pure HTTP layer) +
`scripts/sync_teamup.py` (JSON->Teamup mapping, list-then-diff, and
create/update/delete execution), with `tests/test_teamup_client.py`,
`tests/test_sync_teamup.py` (25 unit tests, mocked HTTP) and
`tests/test_integration.py` (2 tests against the real API: a list
smoke test and a full create->update->delete round trip using a
distinctly-tagged `wayfinder-integration-test-*` fixture, cleaned up
in a `finally` block). `tests/test_placeholder.py` deleted.
`requirements.txt` gained `requests==2.34.2`, `python-dotenv==1.2.3`,
and `types-requests==2.33.0.20260906` (needed for a clean `mypy` run).
`pytest.ini` gained `pythonpath = scripts` so tests can import the two
script modules directly. `Makefile` gained a `sync-teamup` target.

Design decisions, against the ticket's 8 points:

1. **`remote_id` value**: the JSON's own `id`, unprefixed -- no
   collision risk on this single-purpose calendar.
2. **List-then-diff**: one `GET /events` per run, ranged from today
   through the JSON's furthest `endDate`/`date` (`compute_list_range`
   in `sync_teamup.py`), building a `remote_id -> {internal_id,
   is_recurring}` map (`fetch_remote_index`). A recurring series is
   expanded into multiple occurrences sharing one `remote_id` by
   Teamup's list endpoint; the first occurrence's internal id is kept
   (any one works for a `redit=all` operation). `plan_sync` then does
   plain set arithmetic for create/update/delete.
3. **Change detection for updates**: always act on every entry in the
   update bucket unconditionally -- no field-level diffing. A live
   smoke `PUT` early in this ticket's work confirmed `PUT` **is**
   idempotent-by-internal-id for a one-off event (and revealed Teamup
   requires the body's own `id` field to match the URL's -- omitting
   it returns `invalid_json: "id" missing`, undocumented in the prior
   research). Running the sync twice against the real calendar in a
   row (documented below) confirms this converges: second run reports
   `0 created, 8 updated, 0 deleted` with the same 8 `remote_id`s
   present afterward, unchanged.
4. **Recurring-series handling on update/delete -- deviates from the
   ticket's `?redit=all`-for-both assumption.** Delete via internal id
   + `redit=all` is exactly as proven in the prior research: reliable,
   used unconditionally for a to-be-deleted recurring series. **Update
   is not** done via `PUT .../{occurrence_id}?redit=all` -- live
   smoke-testing that path this ticket (not the prior research) showed
   it is unsafe: one attempt against a real 6-occurrence test series
   silently dropped one occurrence (5 remained, none with the intended
   title change) and returned an empty response body; a follow-up
   attempt hit an outright `500 Maintenance In Progress` from Teamup's
   own infrastructure mid-test. Given that, a changed weekly event is
   instead **deleted (internal id, `redit=all`) and recreated fresh
   via `POST`** with the same `remote_id` -- both proven-reliable
   operations, sidestepping the fragile in-place series edit entirely.
   A changed one-off event still uses a normal `PUT`.
5. **Field mapping**: `title`/`location`/`notes` map directly;
   `notes` sent as plain text (Teamup wraps it in `<p>...</p>` on
   return, not diffed since there's no field-level diffing at all
   here). `start_dt`/`end_dt` built via `zoneinfo` from the JSON's
   `date`/`startTime`/`endTime`/`timezone` fields, correct across DST
   (unit-tested for both an EDT and an EST date). `rrule` built as
   `FREQ=WEEKLY;BYDAY={dayOfWeek};UNTIL={until_utc(endDate, timezone)}`,
   reusing the ICS generator's `until_utc` local-end-of-day-to-UTC
   logic verbatim (adapted for Teamup's rrule string).
6. **Incomplete-entry handling**: `map_event_to_payload` raises
   `KeyError`/`ValueError` per event; `build_payloads` catches both,
   skips the entry, and collects `(id, error)` pairs -- same
   skip-and-flag policy as `hugo-natenite.net/scripts/sync_calendar.py`,
   unit-tested directly (missing field, unknown `recurrenceType`, and
   a full-batch case with one bad entry among good ones).
7. **Testing split**: `make unit` (25 tests, all mocked, `<0.2s`)
   covers field mapping, `rrule`/`UNTIL` computation, bucketing, and
   skip-and-flag. `make integration` (2 tests) hits the real calendar
   with a fixture tagged `wayfinder-integration-test-*`, exercising
   the actual create/update(delete+recreate for weekly, PUT for
   one-off)/delete path end to end, cleaned up in a `finally` even on
   failure. Both passed clean on the real calendar before the real
   sync was run.
8. **Makefile target**: `make sync-teamup` added, mirroring the
   existing `.venv`-dependent target style.

**`make static` result**: clean -- `black` (auto-formats, no diffs on
final run), `mypy` (0 errors across all 5 new/changed source files),
`shellcheck` (n/a, no `.sh` files), `pylint` (10.00/10), `pytest -m
unit` (25 passed). `make integration` (2 passed) run separately against
the live calendar before the real sync.

**Real sync result**: `make sync-teamup` run against the real calendar
and the real `data/events.json` (8 events, a mix of `weekly` and
`once`). Output: `Sync complete: 8 created, 0 updated, 0 deleted, 0
skipped.` Verified via a follow-up `GET /events` over the full date
range (2026-09-28 through 2027-07-01): all 8 distinct `remote_id`s
present and exactly matching the JSON's 8 `id`s (104 total occurrence
objects returned once weekly series are expanded read-time by Teamup,
as expected -- still only 8 underlying series/events written). Ran the
sync a second time to confirm idempotency: `0 created, 8 updated, 0
deleted, 0 skipped`, with the same 8 `remote_id`s intact afterward.
The 8 real events are left in place on the real calendar (not cleaned
up -- they are the actual intended output of this ticket).

**Not yet done, flagged for the map**: per map.md's standing note, the
first Modify-permission key's rotation was deliberately deferred until
this ticket closed. It is closed now -- that rotation is the one
remaining follow-up outside this ticket's own scope. (Since resolved --
see the incident note below and map.md.)

**Post-resolution incident**: running `make integration` against the
real, populated calendar deleted all 8 real events. Root cause:
`tests/test_integration.py`'s `_create_fixtures`/`_update_fixtures`/
`_delete_fixtures` each called `plan_sync(mapped, remote_index)` where
`mapped` only ever contained the test's own 2 throwaway fixtures, but
`remote_index` (from `fetch_remote_index` over the test's date range)
reflected the *entire* real calendar -- all 8 real events have
occurrences in that range. `plan_sync`'s `deletes` bucket is
"in Teamup but not in mapped", so all 8 real events were bucketed as
deletes and silently removed by `execute_sync`, with only
`plan.creates`/`plan.updates` ever asserted on -- nothing checked
`plan.deletes`. The test reported "passed" throughout.

Fixed two ways: (1) `tests/test_integration.py` now filters
`remote_index` down to only the test's own fixture remote_ids via a
new `_fetch_fixture_index` helper *before* it ever reaches
`plan_sync`/`execute_sync`, making it structurally impossible for the
test to see (let alone delete) anything else, regardless of what's on
the calendar -- verified by restoring the 8 real events and re-running
`make integration` against a populated calendar; all 8 survived. (2)
`scripts/sync_teamup.py` gained a `mass_deletion_guard_error` check in
`main()`: refuses to run if a plan would delete existing events while
the JSON produced zero valid mapped events (the broken/empty-JSON
failure mode this incident's root cause resembles), unit-tested in
`tests/test_sync_teamup.py`. `make static` clean after both fixes (28
unit tests, up from 25).
