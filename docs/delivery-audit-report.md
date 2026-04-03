# Delivery Acceptance & Project Architecture Audit

**Role:** Reviewer (Delivery Acceptance / Architecture)  
**Date:** 2026-04-03  
**Workspace:** `w2t77` (Warehouse Intelligence & Offline Crawling Operations Platform)

---

## 1. Verdict

**Partial Pass**

Static review shows a structured Django + React codebase aligned with most of the business prompt (crawling, inventory, notifications, audit, Celery, MySQL, Argon2, offline-oriented config). Runtime and automated tests were **not** executed here (Docker-only documented workflow; see §2). A **material route-level authorization inconsistency** was found between crawling tests and `CrawlSourceViewSet` permission logic (see Finding 1), which undermines security-critical RBAC until resolved or disproven by execution.

---

## 2. Scope and Verification Boundary

| Area | Reviewed |
|------|----------|
| Documentation | `repo/README.md`, `repo/run_test.sh`, `repo/CLAUDE.md` (context), `metadata.json` |
| Backend | `config/settings.py`, `config/urls.py`, `accounts/views.py`, `accounts/permissions.py`, `crawling/views.py`, `crawling/quota.py`, `crawling/routing.py`, `notifications/views.py`, `inventory/views.py` (sample), `config/logging_filters.py`, `config/security_middleware.py` |
| Tests (static) | `accounts/tests.py`, `crawling/tests.py` (RBAC section), `tests/test_e2e.py` header, `inventory/tests.py` header |
| Frontend (minimal) | `frontend/src/router/index.tsx` — dynamic `lazy()` routes only |

**Not executed**

- `docker compose`, `docker`, `podman`, or any container runtime (per audit rules).
- Backend `pytest` / `manage.py test` (documented path uses Docker: `repo/run_test.sh` → `docker compose exec backend …`).
- Health URL or manual API calls requiring a running stack.

**Docker-based verification**

- Required for the **documented** full-stack startup (`repo/README.md` lines 6–9) and for `repo/run_test.sh` test targets (e.g. `run_test.sh` lines 38–39, 282–308).
- Treated as a **verification boundary**, not automatic proof of defect.

**Unconfirmed**

- Whether the current tree passes the full pytest suite (including `CrawlingRBACTests`) on CI or locally inside containers.
- End-to-end runtime behavior (DB migrations, Celery workers, frontend build) without Docker.

---

## 3. Top Findings

### Finding 1 — **Severity: Blocker**

**Conclusion:** `POST /api/crawl/sources/{id}/rule-versions/` may be authorized for **any authenticated user**, while tests require **Procurement Analyst / Admin only**.

**Rationale:** `CrawlSourceViewSet.get_permissions` applies `IsProcurementAnalyst` only to `create`, `update`, and `partial_update`. The custom `@action` named `rule_versions` (GET/POST) is not included; DRF will use the default return branch `IsAuthenticated()` for that action.

**Evidence:**

```75:78:repo/backend/crawling/views.py
    def get_permissions(self):
        if self.action in ("create", "update", "partial_update"):
            return [IsProcurementAnalyst()]
        return [IsAuthenticated()]
```

```83:100:repo/backend/crawling/views.py
    @action(detail=True, methods=["get", "post"], url_path="rule-versions")
    def rule_versions(self, request, pk=None):
        source = self.get_object()

        if request.method == "POST":
            ser = CrawlRuleVersionCreateSerializer(data=request.data)
            ...
```

```706:714:repo/backend/crawling/tests.py
    def test_manager_cannot_create_rule_version(self):
        """INVENTORY_MANAGER must not create rule versions (403)."""
        self._auth(self.manager)
        resp = self.client.post(
            f"/api/crawl/sources/{self.source.pk}/rule-versions/",
            {"version_note": "blocked", "url_pattern": "http://x.local"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
```

**Impact:** Inventory (or any authenticated) role could create crawl rule versions, conflicting with the prompt’s procurement-analyst configuration center and with the project’s own RBAC tests—privilege escalation on a sensitive path.

**Minimum actionable fix:** In `get_permissions`, include `rule_versions` in the `IsProcurementAnalyst` branch (and keep GET list behavior as required by product policy), or set `@action(..., permission_classes=[IsProcurementAnalyst])` for POST while allowing broader GET if intended.

---

### Finding 2 — **Severity: High**

**Conclusion:** Default `DJANGO_SECRET_KEY` is committed when `DJANGO_SECRET_KEY` is unset, and `FIELD_ENCRYPTION_KEY` may be empty with only a runtime warning—both are production security risks.

**Evidence:**

```14:17:repo/backend/config/settings.py
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "insecure-dev-key-replace-before-any-real-use",
)
```

```247:260:repo/backend/config/settings.py
FIELD_ENCRYPTION_KEY = os.environ.get("FIELD_ENCRYPTION_KEY", "")
...
if not _TESTING and not FIELD_ENCRYPTION_KEY:
    import warnings
    warnings.warn(
        "FIELD_ENCRYPTION_KEY is not set. Encrypted model fields ...",
```

**Impact:** JWT signing and session security depend on `SECRET_KEY`; encrypted fields are ineffective without `FIELD_ENCRYPTION_KEY`.

**Minimum actionable fix:** Fail fast in production settings when `SECRET_KEY` / `FIELD_ENCRYPTION_KEY` are missing or placeholder; document required env vars prominently (README already warns on placeholder in `.env` for `run_test.sh` grep — extend to encryption key).

---

### Finding 3 — **Severity: Medium**

**Conclusion:** Documented run and test paths are **Docker-centric**; there is no parallel “bare metal” recipe in the reviewed README for MySQL + Redis + Celery locally.

**Evidence:** `repo/README.md` lines 6–9; `repo/run_test.sh` lines 38–73, 282–308.

**Impact:** Acceptable for teams using Docker; operators without containers must infer setup. Not a code defect by itself (per audit rules).

**Minimum actionable fix:** Optional short appendix: environment variables and commands for local `manage.py runserver` + MySQL/Redis (if product owners want non-Docker adoption).

---

### Finding 4 — **Severity: Medium**

**Conclusion:** Automated test **execution** was not verified in this audit; static evidence shows broad backend coverage (auth, inventory, crawling, notifications, e2e module) and explicit “no mock” intent.

**Evidence:** `repo/run_test.sh` lines 282–308; `repo/backend/tests/test_e2e.py` lines 1–13; `repo/backend/accounts/tests.py` lines 1–8.

**Impact:** If Finding 1 is real, CI should fail on `test_manager_cannot_create_rule_version` unless that test is skipped or never run—cannot confirm without execution.

**Minimum actionable fix:** Run `./run_test.sh test` (or equivalent) in Docker and fix any RBAC failures.

---

### Finding 5 — **Severity: Low**

**Conclusion:** Logging uses a dedicated secret-masking filter on the console handler, aligned with “mask tokens by default.”

**Evidence:**

```391:417:repo/backend/config/settings.py
LOGGING = {
    ...
    "filters": {
        "mask_secrets": {
            "()": "config.logging_filters.MaskSecretsFilter",
        },
    },
    ...
        "console": {
            ...
            "filters": ["mask_secrets"],
        },
```

**Impact:** Positive; reduces accidental secret leakage. Not exhaustive for all binary/log formats.

**Minimum actionable fix:** None mandatory.

---

*(Stopped at 5 findings: Blocker + security + verification boundary + logging + test execution note; additional low-severity items omitted per “highest impact” rule.)*

---

## 4. Security Summary

| Topic | Assessment | Evidence / boundary |
|-------|------------|---------------------|
| **Authentication** | **Partial Pass** (static) | JWT login (`accounts/views.py`), Argon2 primary hasher (`config/settings.py` lines 161–165), password validators. Runtime not verified. |
| **Route authorization** | **Fail** (static, pending test run) | Role classes exist (`accounts/permissions.py`). **Gap:** `CrawlSourceViewSet` vs `rule_versions` action (Finding 1). `CrawlTaskViewSet` correctly uses `IsProcurementAnalyst` (`crawling/views.py` line 227). |
| **Object-level authorization** | **Partial Pass** (static) | Notifications scoped to `request.user` (`notifications/views.py` lines 119–120). Admin user management uses `IsAdmin` + queryset (`accounts/views.py`). No multi-tenant model reviewed; single-tenant assumption. |
| **Tenant / user isolation** | **Cannot Confirm** | No separate tenant table found in sampled files; appears single-deployment / single org. |

---

## 5. Test Sufficiency Summary

**Test overview**

- **Unit / API tests:** Present under `repo/backend/` (`accounts/tests.py`, `inventory/tests.py`, `crawling/tests.py`, `notifications/tests.py`, `audit/tests.py`, `warehouse/tests.py`, `tests/test_e2e.py`).
- **Integration / E2E:** `tests/test_e2e.py` documents cross-module flows with real DB and HTTP.
- **Entry points:** `repo/run_test.sh` (`test`, `test-frontend`, `test-all`); test files also show `docker compose exec backend python manage.py test …` in docstrings.

**Core coverage (static)**

| Area | Assessment | Evidence |
|------|------------|----------|
| Happy path | **Partial** | E2E module (`test_e2e.py`), many API tests |
| Key failure paths (401/403/404/409) | **Partial** | Login 401 (`accounts/tests.py`), crawling RBAC matrix (`crawling/tests.py`), item create 403 (`inventory/tests.py` sample) |
| Security-critical | **Partial** | RBAC tests exist but **implementation mismatch suspected** for rule-versions POST (Finding 1) |

**Major gaps (up to 3)**

1. Cannot confirm green CI without running tests (Docker boundary).
2. If Finding 1 stands, tests and implementation are inconsistent until one side is fixed.

**Final test verdict:** **Partial Pass** (strong static signal; execution unconfirmed; one suspected RBAC defect).

---

## 6. Engineering Quality Summary

- **Positive:** Clear app split (`accounts`, `warehouse`, `inventory`, `crawling`, `notifications`, `audit`); Celery routing and beat schedule in `config/settings.py`; quota module documents transactions and `select_for_update` (`crawling/quota.py`); sharded crawl queues (`crawling/routing.py`); centralized exception handler referenced in DRF settings; security headers middleware.
- **Concern:** The RBAC gap on a nested `@action` (Finding 1) suggests permission logic should be centralized or reviewed for all custom actions on `ViewSet`s.

---

## 7. Next Actions

1. **Fix or verify** `CrawlSourceViewSet` permissions for `rule_versions` POST vs `CrawlingRBACTests` (Finding 1).
2. **Run** `./run_test.sh test` in Docker and resolve any failures (Finding 4).
3. **Harden** production config: require non-default `DJANGO_SECRET_KEY` and `FIELD_ENCRYPTION_KEY` when `DEBUG` is false (Finding 2).
4. **Optionally** document non-Docker local development if required by operators (Finding 3).
5. Re-run security spot-check on any other `@action` methods that perform writes without `IsProcurementAnalyst` / `IsInventoryManager` as appropriate.

---

## Final Verification (self-check)

1. Material conclusions cite file paths and line numbers where applicable.  
2. No claim that Docker fails to start—only that it was not run.  
3. Finding 1 is the strongest driver for **Partial Pass** vs **Pass**; removing it would still leave “unverified runtime/tests.”  
4. Uncertain points labeled **Cannot Confirm** where appropriate.  
5. Security and tests not graded “Pass” without execution evidence.  
6. Docker non-execution described as boundary, not as confirmed runtime failure.
