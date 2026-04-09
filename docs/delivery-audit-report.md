# Delivery Acceptance & Project Architecture Audit

**Review date:** 2026-04-03  
**Workspace:** `w2t77` (`repo/` contains the application)  
**Reviewer role:** Delivery acceptance and architecture audit (static review + documented verification boundaries; **no Docker or container-related commands executed** per audit rules).

---

## 1. Verdict

**Partial Pass**

The repository is a **credible, structured 0-to-1 deliverable** aligned with the Warehouse Intelligence & Offline Crawling Operations Platform prompt: Django + DRF + MySQL + Celery/Redis + React, with domain modules for accounts, warehouse, inventory, crawling, notifications, and audit; crawling includes canary monitoring, quota with `select_for_update`, encrypted rule headers, and integration/E2E-style tests. **End-to-end runtime behavior was not executed** (documented path is Docker-centric; audit constraint). **Documentation vs. actual runtime consistency cannot be confirmed** from this review. Static evidence does not support a **Fail** verdict (no evidence the implementation is a fragment or unrelated to the prompt). Frontend aesthetics were **not assessed** (non-frontend audit scope).

---

## 2. Scope and Verification Boundary

**Reviewed**

- Documentation: `repo/README.md`, `repo/run_test.sh`, `repo/backend/pytest.ini`, `repo/backend/conftest.py`
- Backend configuration and security: `repo/backend/config/settings.py`, `repo/backend/config/urls.py`, `repo/backend/config/logging_filters.py` (referenced from `LOGGING`)
- Auth and users: `repo/backend/accounts/views.py`, `repo/backend/accounts/permissions.py`, `repo/backend/accounts/tests.py` (sampled)
- Crawling: `repo/backend/crawling/quota.py`, `repo/backend/crawling/tasks.py`, `repo/backend/crawling/models.py` (encryption import), `repo/backend/crawling/tests.py` (sampled)
- Inventory RBAC samples: `repo/backend/inventory/views.py`, `repo/backend/inventory/tests.py` (grep + samples)
- Notifications scoping: `repo/backend/notifications/views.py`
- Cross-app E2E: `repo/backend/tests/test_e2e.py`

**Not executed**

| Action | Reason |
|--------|--------|
| `docker compose`, `podman`, `run_test.sh` | Audit rule: no Docker-related commands |
| Host `pytest` / `manage.py test` | Documented path runs tests inside the backend container; `DB_HOST` defaults to `db` and `REDIS_URL` to `redis://redis:6379/0` in `settings.py`, which assumes Docker service hostnames unless overridden |
| `npm` / Vitest on host | Frontend tests are invoked via `run_test.sh` → Docker |

**Docker-based verification:** Required by project docs for the primary run and test path; **not performed** here (verification boundary, not treated as proof of a broken stack).

**Unconfirmed:** Live `/api/health/` JSON, migration/seed execution, Celery workers/beat, real SMTP/SMS gateways, and full frontend behavior.

---

## 3. Top Findings

*(Up to 10; highest-impact only. Stopping after material conclusions.)*

### Finding 1 — **High** — Default `DJANGO_SECRET_KEY` and JWT signing

- **Conclusion:** If `DJANGO_SECRET_KEY` is not set in the environment, the app uses a fixed insecure development default; SimpleJWT uses the same material as `SIGNING_KEY` for HS256 tokens.
- **Rationale:** Anyone with the default key could forge JWTs; README still encourages `.env` but the fallback is embedded in code.
- **Evidence:** `repo/backend/config/settings.py` lines 14–17 (`SECRET_KEY` default `insecure-dev-key-replace-before-any-real-use`); lines 216–224 (`SIMPLE_JWT` → `SIGNING_KEY`: `SECRET_KEY`).
- **Impact:** **Deployment security:** production deployments that omit a real secret are critically exposed.
- **Minimum fix:** Refuse to start when `DEBUG` is false and `SECRET_KEY` is the placeholder; or require `DJANGO_SECRET_KEY` in non-debug environments with no default.

### Finding 2 — **Medium** — Fernet fallback for field encryption

- **Conclusion:** A dev Fernet key is embedded and used when `FIELD_ENCRYPTION_KEY` is missing or invalid; a runtime warning is emitted outside test runs.
- **Rationale:** Misconfiguration could silently use a known key shipped in the repository.
- **Evidence:** `repo/backend/config/settings.py` lines 247–276 (`_DEV_FERNET_KEY`, `_resolve_encryption_key`, warning when not `_TESTING`).
- **Impact:** At-rest encryption for sensitive crawl fields may be weaker than operators assume.
- **Minimum fix:** Fail fast in non-debug production when encryption key is unset or invalid; restrict dev fallback to explicit dev mode.

### Finding 3 — **Medium** — Primary run and test path is Docker-only

- **Conclusion:** README and `run_test.sh` document `docker compose` as the way to start services and run tests; there is no first-class documented host-only workflow.
- **Rationale:** Reproducibility for reviewers without Docker relies on inferring env vars and local MySQL/Redis; this audit did not run the stack.
- **Evidence:** `repo/README.md` lines 3–9 (`docker compose up --build`); `repo/run_test.sh` lines 38–39, 62–74, 282–308 (`docker compose` prerequisites and `exec` for pytest).
- **Impact:** Narrows who can verify the deliverable without extra undocumented setup.
- **Minimum fix:** Optional “local without Docker” section (env vars for `DB_HOST`, `REDIS_URL`, `manage.py runserver`, Celery, Vite) **or** explicit statement that Docker is the only supported path.

### Finding 4 — **Medium** — “6:00 PM” digest vs default `TIME_ZONE`

- **Conclusion:** Digest scheduling compares local wall-clock components; default `TIME_ZONE` is `UTC` unless set via environment, so “6:00 PM” in the prompt is **6:00 PM UTC** by default.
- **Rationale:** Operators may expect site-local 6:00 PM without reading env docs.
- **Evidence:** `repo/backend/config/settings.py` lines 367–372 (`TIME_ZONE`); comments at 286–291 tie digest to local wall-clock via `TIME_ZONE`.
- **Impact:** Digests may fire at an unexpected wall time for non-UTC sites.
- **Minimum fix:** Document default UTC and require `TIME_ZONE` for local 6:00 PM; consider a single “business timezone” setting in README.

### Finding 5 — **Low** — Seeded credentials in README

- **Conclusion:** Default seeded usernames and passwords are listed in `README.md` for smoke testing.
- **Rationale:** Acceptable for local dev documentation; unacceptable if the same credentials ever reach a shared or production-like environment without rotation.
- **Evidence:** `repo/README.md` lines 33–39.
- **Impact:** Operational hygiene risk if operators reuse defaults outside isolated dev.
- **Minimum fix:** Emphasize “change after first login” or use one-time bootstrap tokens for non-local environments.

### Finding 6 — **Low** — Runtime prompt alignment for crawling/inventory

- **Conclusion:** Static code references SPEC-style constants (e.g. canary 30m/2%, quota `FOR UPDATE`, backoff/checkpoint comments in worker); **not** validated by execution here.
- **Evidence:** `repo/backend/crawling/quota.py` lines 33–34, 54–58 (`select_for_update`); `repo/backend/crawling/tasks.py` lines 19–31 (canary window and error threshold); `repo/backend/tests/test_e2e.py` (receive/issue, crawl execute, canary rollback).
- **Impact:** Increases confidence in prompt fit; runtime remains unconfirmed under this audit.

---

## 4. Security Summary

| Area | Rating | Evidence / verification boundary |
|------|--------|----------------------------------|
| **Authentication** | **Partial Pass** | JWT (SimpleJWT), login throttling (`repo/backend/accounts/views.py` 51–53), Argon2 primary (`repo/backend/config/settings.py` 161–165), tests for login/401 and Argon2 prefix (`repo/backend/accounts/tests.py` 39–71). **High risk** if default `SECRET_KEY` is used in deployment (Finding 1). |
| **Route authorization** | **Pass** | Default `IsAuthenticated` (`settings.py` 186–188); `UserViewSet` uses `IsAdmin` (`accounts/views.py` 189); inventory/crawling tests assert 403 for wrong roles (e.g. `inventory/tests.py` 92–95, 625+). |
| **Object-level authorization** | **Partial Pass** | Notifications: `get_queryset` scopes subscriptions and inbox to `request.user` (`notifications/views.py` 60–63, 119–120). Inventory/warehouse operations use shared catalog data (typical single-tenant internal app); **not** exhaustively proven for every `retrieve` by ID across all viewsets. |
| **Tenant / user isolation** | **Cannot Confirm** | Prompt describes roles within one platform, not multi-tenant SaaS. No multi-tenant partition was reviewed; not treated as a defect without that requirement. |

---

## 5. Test Sufficiency Summary

**Test overview**

- **Unit / integration tests:** Present per Django app (`accounts/tests.py`, `inventory/tests.py`, `crawling/tests.py`, `notifications/tests.py`, `audit/tests.py`, `warehouse/tests.py`) plus `repo/backend/tests/test_e2e.py`.
- **API tests:** HTTP-level tests with DRF `APIClient`; `conftest.py` states real DB, no mocking of HTTP/views.
- **Entry points:** `repo/run_test.sh` `test` / `test-all` (Docker `exec` into backend); `repo/backend/pytest.ini` sets `DJANGO_SETTINGS_MODULE`.

**Core coverage**

| Area | Assessment | Evidence |
|------|------------|----------|
| Happy path | **covered** (static) | Login, inventory receive/issue, crawling sources/tasks, canary rollback E2E (`test_e2e.py`). |
| Key failure paths | **partial** | 401 login, 403 role denial, 400 over-issue (`test_e2e.py` 155–172); registration disabled 403 (`accounts/tests.py`). Full 404/409/429 matrix not mapped. |
| Security-critical | **partial** | Argon2 check, registration off, analyst forbidden on inventory; JWT forgery risk is **operational** (Finding 1), not unit-tested as “missing secret key” scenario. |

**Major gaps (up to 3)**

1. **Execution:** Test suite not run in this audit (Docker boundary)—**cannot confirm** green CI.  
2. **Object-level:** Spot-check; minimum addition: prove user A cannot `GET` user B’s notification by primary key if URLs allow ID access.  
3. **Host-only CI:** No evidence reviewed of a compose-free test job; optional gap if required by policy.

**Final test verdict:** **Partial Pass** (broad static coverage; execution unconfirmed).

---

## 6. Engineering Quality Summary

- **Structure:** Clear Django app boundaries (`accounts`, `warehouse`, `inventory`, `crawling`, `notifications`, `audit`); crawling quota logic isolated in `crawling/quota.py` with transactional locking.
- **Maintainability:** Central `REST_FRAMEWORK` config, custom exception handler, Celery beat schedule in `settings.py`, logging with `MaskSecretsFilter` (`settings.py` 411–438).
- **Material concerns:** Default secrets (Finding 1–2) and timezone semantics for digests (Finding 4) affect production confidence; otherwise the codebase does not read as a throwaway single-file demo.

---

## 7. Next Actions

1. **Production / staging:** Set `DJANGO_SECRET_KEY` and `FIELD_ENCRYPTION_KEY` to unique values; fail startup if placeholders remain when not in debug.  
2. **Operators:** Run `./run_test.sh test-all` (or documented compose equivalent) where Docker is available to confirm green tests and `/api/health/`.  
3. **Docs:** State whether Docker is the only supported dev path; document `TIME_ZONE` for 6:00 PM digest behavior.  
4. **Optional tests:** Notification ID access across users; startup test that rejects default `SECRET_KEY` in production-like settings.  
5. **Credential hygiene:** Reinforce rotating or overriding seeded accounts outside local dev.

---

## Final Verification (self-check)

1. Material conclusions tied to paths/lines where stated.  
2. No claim that Docker failed—only that Docker was **not run** (boundary).  
3. Verdict does not assume tests pass without execution.  
4. Uncertain items labeled **Cannot Confirm** or verification boundary.  
5. Security and tests not graded as full **Pass** where default signing key risk exists or tests were not executed.  
6. Docker non-execution **not** described as a confirmed runtime failure.
