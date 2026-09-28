# lax-pickup-calendar

## Repository Overview

Public, read-only calendar of adult lacrosse pickup games and leagues in MA/NH. Full spec: `docs/specs/public-lacrosse-calendar-site.md`.

The published site itself is a Hugo (Go) static site with FullCalendar loaded via CDN — no Node/npm build step, no backend. The only code with its own test/lint story is the Python `.ics` generator built in Phase 3 (structured event data -> `events.ics`), which this scaffolding targets.

## Technology Stack

- Site: Hugo static site generator, FullCalendar (CDN `<script>` tags, pinned version), served from any static host (GitHub Pages / Cloudflare Pages / Netlify).
- Generator: Python, producing RFC 5545 `.ics` output from structured event data.
- Python: 3.12.7 (pinned in `Makefile` and CI).

## Code Standards

- All dependency versions pinned to exact versions (`requirements.txt`, GitHub Actions SHAs).
- No prose-parsing of the existing free-text schedule notes — the structured schema is additive, not a replacement (see spec's Implementation Decisions).

## Static Analysis & Testing Standards

This project follows opinionated standards enforced by the `scaffold-project` skill:

1. **Pinned Dependencies**: all dependency versions are pinned to exact versions.
2. **Static Analysis**: run `make static` before committing.
3. **Pre-commit Hooks**: configured with gitleaks and `make static`.
4. **Dependabot**: configured for automated weekly updates (pip, github-actions).
5. **CI/CD**: GitHub Actions runs `make static-check` on PRs and main pushes.

### Available Make Targets

Run `make help` to see all available targets. Key targets:
- `make static` - run all static analysis checks (auto-formats)
- `make static-check` - run all static analysis checks (CI, no modification)
- `make unit` - run unit tests
- `make unit-update-golden` - update golden/fixture files for the `.ics` generator tests
- `make integration` - run integration tests (manual, requires credentials/fixtures)

## Testing Strategy

Per the spec's Testing Decisions:
- **Phases 1-2** (Hugo walking skeleton, hand-written `.ics` fixture): manual/visual verification only — no automated tests. These phases validate third-party library behavior (Hugo static serving, FullCalendar rendering/recurrence), not our own code.
- **Phase 3** (the `.ics` generator): the first and only automated-test surface in this repo. Fixture-based unit tests assert the generator's output structure directly — `VEVENT` count, `RRULE` string shape for recurring events, and that incomplete entries are excluded/flagged rather than silently emitted. Do not round-trip through a third-party ICS parser or FullCalendar itself.

## Workflows

- Git: default branch `main`.
- CI/CD: `.github/workflows/static-check.yml` runs `make static-check` on every PR and on push to `main`.
- Pre-commit: `pre-commit install` after `.venv` is created; runs gitleaks + `make static` before each commit.

## Guidelines for Claude Code

- Follow the phase ordering in the spec (walking skeleton -> manual `.ics` fixture -> generator automation) — don't jump ahead to automation before the earlier phases are manually verified.
- Keep the generated `.ics`'s recurring events as a single `VEVENT` + `RRULE`, never enumerated per-occurrence.
- Entries missing a required schedule field must be excluded and flagged by the generator, never defaulted or guessed.
