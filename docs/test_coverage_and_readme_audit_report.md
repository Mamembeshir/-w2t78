# Test Coverage Audit

## Scope
- Static inspection only; no code/tests/scripts/containers executed.
- Inspected only routing, views, tests, `README.md`, and `run_tests.sh`.
- README top does **not** explicitly declare one of: `backend|fullstack|web|android|ios|desktop`.
- Inferred project type (light inspection): **fullstack** (`backend/`, `frontend/`, `e2e/`).

## Backend Endpoint Inventory

Total endpoints (resolved `METHOD + PATH`): **72**

1. `GET /api/health/`
2. `POST /api/auth/login/`
3. `POST /api/auth/logout/`
4. `POST /api/auth/refresh/`
5. `GET /api/auth/me/`
6. `POST /api/auth/register/`
7. `GET /api/users/`
8. `POST /api/users/`
9. `GET /api/users/:id/`
10. `PUT /api/users/:id/`
11. `PATCH /api/users/:id/`
12. `POST /api/users/:id/reset-password/`
13. `GET /api/warehouses/`
14. `POST /api/warehouses/`
15. `GET /api/warehouses/:id/`
16. `PUT /api/warehouses/:id/`
17. `PATCH /api/warehouses/:id/`
18. `GET /api/warehouses/:warehouse_id/bins/`
19. `POST /api/warehouses/:warehouse_id/bins/`
20. `GET /api/warehouses/:warehouse_id/bins/:id/`
21. `PUT /api/warehouses/:warehouse_id/bins/:id/`
22. `PATCH /api/warehouses/:warehouse_id/bins/:id/`
23. `GET /api/items/`
24. `POST /api/items/`
25. `GET /api/items/:id/`
26. `PUT /api/items/:id/`
27. `PATCH /api/items/:id/`
28. `GET /api/items/:id/lots/`
29. `GET /api/items/:id/serials/`
30. `GET /api/items/:id/ledger/`
31. `GET /api/inventory/balances/`
32. `POST /api/inventory/receive/`
33. `POST /api/inventory/issue/`
34. `POST /api/inventory/transfer/`
35. `POST /api/inventory/cycle-count/start/`
36. `POST /api/inventory/cycle-count/:id/submit/`
37. `POST /api/inventory/cycle-count/:id/confirm/`
38. `GET /api/crawl/sources/`
39. `POST /api/crawl/sources/`
40. `GET /api/crawl/sources/:id/`
41. `PUT /api/crawl/sources/:id/`
42. `PATCH /api/crawl/sources/:id/`
43. `GET /api/crawl/sources/:id/rule-versions/`
44. `POST /api/crawl/sources/:id/rule-versions/`
45. `GET /api/crawl/sources/:id/debug-log/`
46. `GET /api/crawl/sources/:id/quota/`
47. `GET /api/crawl/rule-versions/:id/`
48. `POST /api/crawl/rule-versions/:id/activate/`
49. `POST /api/crawl/rule-versions/:id/canary/`
50. `POST /api/crawl/rule-versions/:id/rollback/`
51. `POST /api/crawl/rule-versions/:id/test/`
52. `GET /api/crawl/tasks/`
53. `POST /api/crawl/tasks/`
54. `GET /api/crawl/tasks/:id/`
55. `POST /api/crawl/tasks/:id/retry/`
56. `GET /api/notifications/subscriptions/`
57. `POST /api/notifications/subscriptions/`
58. `DELETE /api/notifications/subscriptions/:id/`
59. `GET /api/notifications/inbox/`
60. `GET /api/notifications/inbox/:id/`
61. `GET /api/notifications/inbox/unread-count/`
62. `POST /api/notifications/inbox/:id/read/`
63. `POST /api/notifications/inbox/read-all/`
64. `GET /api/notifications/outbound/queued/`
65. `GET /api/notifications/outbound/queued/:id/`
66. `GET /api/notifications/digest/`
67. `PATCH /api/notifications/digest/`
68. `GET /api/settings/`
69. `PATCH /api/settings/`
70. `POST /api/settings/test-smtp/`
71. `POST /api/settings/test-sms/`
72. `GET /api/audit/`

## API Test Mapping Table

| Endpoint | Covered | Test type | Test files | Evidence |
|---|---|---|---|---|
| `GET /api/health/` | yes | true no-mock HTTP | `backend/tests/api/audit/test_middleware.py` | `AuditMiddlewareTests.test_health_endpoint_skipped` |
| `POST /api/auth/login/` | yes | true no-mock HTTP | `backend/tests/api/accounts/test_auth_api.py` | `LoginTests.test_login_valid_credentials_returns_tokens` |
| `POST /api/auth/logout/` | yes | true no-mock HTTP | `backend/tests/api/accounts/test_auth_api.py` | `LogoutTests.test_logout_returns_204` |
| `POST /api/auth/refresh/` | yes | true no-mock HTTP | `backend/tests/api/accounts/test_auth_api.py` | `RefreshTokenTests.test_refresh_returns_new_access_token` |
| `GET /api/auth/me/` | yes | true no-mock HTTP | `backend/tests/api/accounts/test_auth_api.py` | `MeViewTests.test_me_returns_current_user` |
| `POST /api/auth/register/` | yes | true no-mock HTTP | `backend/tests/api/accounts/test_registration_api.py` | `RegistrationTests.test_register_returns_201` |
| `GET /api/users/` | yes | true no-mock HTTP | `backend/tests/api/accounts/test_permissions.py` | `PermissionTests.test_admin_can_access_users` |
| `POST /api/users/` | yes | true no-mock HTTP | `backend/tests/api/accounts/test_user_management_api.py` | `UserManagementTests.test_create_user_returns_201` |
| `GET /api/users/:id/` | yes | true no-mock HTTP | `backend/tests/api/accounts/test_user_management_api.py` | `UserManagementTests.test_retrieve_user` |
| `PUT /api/users/:id/` | yes | true no-mock HTTP | `backend/tests/api/accounts/test_user_management_api.py` | `UserManagementTests.test_put_ignores_password_field` |
| `PATCH /api/users/:id/` | yes | true no-mock HTTP | `backend/tests/api/accounts/test_user_management_api.py` | `UserManagementTests.test_patch_user_role` |
| `POST /api/users/:id/reset-password/` | yes | true no-mock HTTP | `backend/tests/api/accounts/test_user_management_api.py` | `UserManagementTests.test_reset_password_changes_password` |
| `GET /api/warehouses/` | yes | true no-mock HTTP | `backend/tests/api/warehouse/test_api.py` | `WarehouseAPITests.test_list_warehouses_authenticated` |
| `POST /api/warehouses/` | yes | true no-mock HTTP | `backend/tests/api/warehouse/test_api.py` | `WarehouseAPITests.test_create_warehouse_admin` |
| `GET /api/warehouses/:id/` | yes | true no-mock HTTP | `backend/tests/api/warehouse/test_api.py` | `WarehouseAPITests.test_retrieve_warehouse` |
| `PUT /api/warehouses/:id/` | yes | true no-mock HTTP | `backend/tests/api/warehouse/test_api.py` | `WarehouseAPITests.test_full_update_warehouse` |
| `PATCH /api/warehouses/:id/` | yes | true no-mock HTTP | `backend/tests/api/warehouse/test_api.py` | `WarehouseAPITests.test_update_warehouse_admin` |
| `GET /api/warehouses/:warehouse_id/bins/` | yes | true no-mock HTTP | `backend/tests/api/warehouse/test_api.py` | `BinAPITests.test_list_bins_authenticated` |
| `POST /api/warehouses/:warehouse_id/bins/` | yes | true no-mock HTTP | `backend/tests/api/warehouse/test_api.py` | `BinAPITests.test_create_bin_admin` |
| `GET /api/warehouses/:warehouse_id/bins/:id/` | yes | true no-mock HTTP | `backend/tests/api/warehouse/test_api.py` | `BinAPITests.test_retrieve_bin` |
| `PUT /api/warehouses/:warehouse_id/bins/:id/` | yes | true no-mock HTTP | `backend/tests/api/warehouse/test_api.py` | `BinAPITests.test_full_update_bin` |
| `PATCH /api/warehouses/:warehouse_id/bins/:id/` | yes | true no-mock HTTP | `backend/tests/api/warehouse/test_api.py` | `BinAPITests.test_partial_update_bin` |
| `GET /api/items/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_item_api.py` | `ItemAPITests.test_list_items` |
| `POST /api/items/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_item_api.py` | `ItemAPITests.test_create_item_inventory_manager` |
| `GET /api/items/:id/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_item_api.py` | `ItemAPITests.test_item_detail_includes_totals` |
| `PUT /api/items/:id/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_item_api.py` | `ItemAPITests.test_full_update_item` |
| `PATCH /api/items/:id/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_item_api.py` | `ItemAPITests.test_partial_update_item` |
| `GET /api/items/:id/lots/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_item_api.py` | `ItemAPITests.test_item_lots_endpoint` |
| `GET /api/items/:id/serials/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_item_api.py` | `ItemAPITests.test_serials_endpoint_with_data` |
| `GET /api/items/:id/ledger/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_item_api.py` | `ItemAPITests.test_ledger_endpoint_with_entries` |
| `GET /api/inventory/balances/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_stock_balance_api.py` | `StockBalanceAPITests.test_balances_list` |
| `POST /api/inventory/receive/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_receive_stock.py` | `ReceiveStockTests.test_receive_creates_ledger_entry` |
| `POST /api/inventory/issue/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_issue_stock.py` | `IssueStockTests.test_issue_moving_avg_posts_at_avg_cost` |
| `POST /api/inventory/transfer/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_transfer_stock.py` | `TransferStockTests.test_transfer_moves_stock_between_warehouses` |
| `POST /api/inventory/cycle-count/start/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_cycle_count.py` | `CycleCountTests.test_start_creates_session_with_expected_qty` |
| `POST /api/inventory/cycle-count/:id/submit/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_cycle_count.py` | `CycleCountTests.test_submit_small_variance_auto_confirms` |
| `POST /api/inventory/cycle-count/:id/confirm/` | yes | true no-mock HTTP | `backend/tests/api/inventory/test_cycle_count.py` | `CycleCountTests.test_confirm_posts_ledger_and_adjusts_balance` |
| `GET /api/crawl/sources/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_source_api.py` | `SourceAPITests.test_list_sources_authenticated` |
| `POST /api/crawl/sources/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_source_api.py` | `SourceAPITests.test_create_source_analyst` |
| `GET /api/crawl/sources/:id/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_source_api.py` | `SourceAPITests.test_source_detail_shows_active_rule_version` |
| `PUT /api/crawl/sources/:id/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_source_api.py` | `SourceAPITests.test_full_update_source` |
| `PATCH /api/crawl/sources/:id/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_source_api.py` | `SourceAPITests.test_update_source` |
| `GET /api/crawl/sources/:id/rule-versions/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_rule_version_api.py` | `RuleVersionAPITests.test_list_rule_versions_for_source` |
| `POST /api/crawl/sources/:id/rule-versions/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_rule_version_api.py` | `RuleVersionAPITests.test_create_rule_version_auto_increments` |
| `GET /api/crawl/sources/:id/debug-log/` | yes | true no-mock HTTP | `backend/tests/api/cross_module/test_cross_module_api.py` | `CrawlEnqueueExecuteDebugE2ETest.test_enqueue_execute_log_debug` |
| `GET /api/crawl/sources/:id/quota/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_source_api.py` | `SourceAPITests.test_quota_returns_zero_when_no_acquisitions` |
| `GET /api/crawl/rule-versions/:id/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_rule_version_api.py` | `RuleVersionAPITests.test_request_headers_masked_in_response` |
| `POST /api/crawl/rule-versions/:id/activate/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_rule_version_api.py` | `RuleVersionAPITests.test_activate_version` |
| `POST /api/crawl/rule-versions/:id/canary/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_rule_version_api.py` | `RuleVersionAPITests.test_start_canary` |
| `POST /api/crawl/rule-versions/:id/rollback/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_rule_version_api.py` | `RuleVersionAPITests.test_rollback_canary` |
| `POST /api/crawl/rule-versions/:id/test/` | yes | true no-mock HTTP + HTTP with mocking | `backend/tests/unit/crawling/test_worker.py`, `backend/tests/api/crawling/test_rule_version_api.py` | `NewFeatureTests.test_rule_test_endpoint_returns_response_data`; `RuleVersionAPITests.test_rule_test_returns_probe_result_on_success` |
| `GET /api/crawl/tasks/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_task_api.py` | `CrawlTaskListTests.test_list_tasks_authenticated` |
| `POST /api/crawl/tasks/` | yes | true no-mock HTTP | `backend/tests/unit/crawling/test_task_scheduler.py` | `TaskSchedulerTests.test_enqueue_task_creates_pending_task` |
| `GET /api/crawl/tasks/:id/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_task_api.py` | `CrawlTaskDetailTests.test_retrieve_task_detail` |
| `POST /api/crawl/tasks/:id/retry/` | yes | true no-mock HTTP | `backend/tests/api/crawling/test_task_api.py` | `CrawlTaskDetailTests.test_retry_failed_task` |
| `GET /api/notifications/subscriptions/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_subscription_api.py` | `SubscriptionAPITests.test_list_subscriptions_empty` |
| `POST /api/notifications/subscriptions/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_subscription_api.py` | `SubscriptionAPITests.test_subscribe_creates_subscription` |
| `DELETE /api/notifications/subscriptions/:id/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_subscription_api.py` | `SubscriptionAPITests.test_unsubscribe` |
| `GET /api/notifications/inbox/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_inbox_api.py` | `InboxAPITests.test_inbox_lists_own_notifications` |
| `GET /api/notifications/inbox/:id/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_inbox_api.py` | `InboxAPITests.test_retrieve_notification_detail` |
| `GET /api/notifications/inbox/unread-count/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_inbox_api.py` | `InboxAPITests.test_unread_count` |
| `POST /api/notifications/inbox/:id/read/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_inbox_api.py` | `InboxAPITests.test_mark_notification_read` |
| `POST /api/notifications/inbox/read-all/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_inbox_api.py` | `InboxAPITests.test_mark_all_read` |
| `GET /api/notifications/outbound/queued/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_outbound.py` | `OutboundQueuedTests.test_admin_can_list_queued_messages` |
| `GET /api/notifications/outbound/queued/:id/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_outbound.py` | `OutboundQueuedTests.test_retrieve_queued_message_detail` |
| `GET /api/notifications/digest/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_digest_schedule_api.py` | `DigestScheduleAPITests.test_get_creates_default_schedule` |
| `PATCH /api/notifications/digest/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_digest_schedule_api.py` | `DigestScheduleAPITests.test_patch_updates_send_time` |
| `GET /api/settings/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_settings_api.py` | `SystemSettingsAPITests.test_get_settings_admin_returns_200_with_expected_fields` |
| `PATCH /api/settings/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_settings_api.py` | `SystemSettingsAPITests.test_patch_smtp_host_admin_returns_200_and_persists` |
| `POST /api/settings/test-smtp/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_settings_api.py` | `SystemSettingsAPITests.test_test_smtp_returns_400_on_connection_failure` |
| `POST /api/settings/test-sms/` | yes | true no-mock HTTP | `backend/tests/api/notifications/test_settings_api.py` | `SystemSettingsAPITests.test_test_sms_returns_400_on_connection_failure` |
| `GET /api/audit/` | yes | true no-mock HTTP | `backend/tests/api/audit/test_audit_log_api.py` | `AuditLogAPITests.test_admin_can_list_audit_entries` |

## API Test Classification

1. True No-Mock HTTP
- Broadly present across `backend/tests/api/**` and selected `backend/tests/unit/**` HTTP tests.

2. HTTP with Mocking
- `backend/tests/api/crawling/test_rule_version_api.py`: `patch("requests.get", ...)` in rule-version probe endpoint tests.
- `backend/tests/api/inventory/test_rbac.py`: `force_authenticate` in helper/auth transitions.
- `backend/tests/api/inventory/test_cycle_count.py`: `force_authenticate` in `test_analyst_cannot_start_cycle_count`.

3. Non-HTTP (unit/integration without HTTP)
- Examples: `backend/tests/unit/notifications/test_dispatcher.py`, `backend/tests/unit/audit/test_immutability.py`, `backend/tests/unit/inventory/test_safety_stock.py`.

## Mock Detection

- Mocked transport/provider in API tests:
  - WHAT: outbound HTTP probe (`requests.get`) mocked
  - WHERE: `backend/tests/api/crawling/test_rule_version_api.py` (tests under `RuleVersionAPITests` with `patch("requests.get", ...)`)
- HTTP-layer auth bypass in some tests:
  - WHAT: DRF auth shortcut `force_authenticate`
  - WHERE: `backend/tests/api/inventory/test_rbac.py`, `backend/tests/api/inventory/test_cycle_count.py`
- Frontend mocks (unit scope):
  - WHAT: hook/service/component mocks via `vi.mock`
  - WHERE: multiple files under `frontend/src/**/__tests__/*` (e.g., `frontend/src/pages/auth/__tests__/LoginPage.test.tsx`)

## Coverage Summary

- Total endpoints: **72**
- Endpoints with HTTP tests: **72**
- Endpoints with TRUE no-mock tests: **72** (each endpoint has at least one non-mocked HTTP test path)
- HTTP coverage: **100.00%**
- True API coverage: **100.00%**

## Unit Test Summary

### Backend Unit Tests

Test files (representative):
- `backend/tests/unit/crawling/test_worker.py`
- `backend/tests/unit/crawling/test_task_scheduler.py`
- `backend/tests/unit/crawling/test_canary.py`
- `backend/tests/unit/crawling/test_quota_engine.py`
- `backend/tests/unit/notifications/test_dispatcher.py`
- `backend/tests/unit/inventory/test_safety_stock.py`
- `backend/tests/unit/audit/test_immutability.py`
- `backend/tests/unit/config/test_exceptions.py`

Modules covered:
- controllers: mainly via API-level tests
- services/tasks: crawling worker/scheduler/canary/quota; notifications dispatcher/tasks; inventory safety stock task
- repositories/models: audit immutability/retention, quota state, task state transitions
- auth/guards/middleware: auth/RBAC matrixes, exception middleware shape tests

Important backend modules not directly unit-focused:
- `backend/accounts/permissions.py` (mostly API-covered)
- `backend/warehouse` serializer/business-rule internals (mostly API-covered)

### Frontend Unit Tests (STRICT)

Frontend test files detected (examples):
- `frontend/src/components/ui/__tests__/Button.test.tsx`
- `frontend/src/components/ui/__tests__/Input.test.tsx`
- `frontend/src/pages/auth/__tests__/LoginPage.test.tsx`
- `frontend/src/pages/auth/__tests__/RegisterPage.test.tsx`
- `frontend/src/router/__tests__/ProtectedRoute.test.tsx`
- `frontend/src/pages/inventory/__tests__/InventoryWorkflowPages.test.tsx`
- `frontend/src/pages/crawling/__tests__/CrawlingPages.test.tsx`
- `frontend/src/pages/notifications/__tests__/NotificationsPages.test.tsx`

Frameworks/tools detected:
- Vitest (`frontend/package.json`, `frontend/vitest.config.ts`)
- React Testing Library + user-event (`frontend/package.json`, test imports)
- jsdom (`frontend/vitest.config.ts`)

Components/modules covered:
- UI components, auth pages, route guard, inventory/crawling/notifications/admin pages, utility hooks/libs

Important frontend components/modules not directly tested:
- `frontend/src/contexts/AuthContext.tsx`
- `frontend/src/contexts/ThemeContext.tsx`
- `frontend/src/contexts/ToastContext.tsx`
- `frontend/src/components/layout/AppShell.tsx`

**Frontend unit tests: PRESENT**

Cross-layer observation:
- Backend coverage is deep and endpoint-complete.
- Frontend has broad unit presence, but many tests are mock-heavy; realism shifts to e2e/integration quality.

## Tests Check

- Success/failure/edge/validation/auth paths: strong coverage across backend API suites.
- Assertions: generally meaningful in backend; frontend includes many smoke-style assertions.
- Integration boundaries: present (cross-module API and worker/live-server tests).
- `run_tests.sh` check: mixed
  - Docker-based backend/frontend paths: OK
  - Local dependency behavior for e2e: FLAG (`npm install`, Playwright browser install in `run_tests.sh:449`, `run_tests.sh:451`)

## API Observability Check

- Backend API tests: mostly clear endpoint + request + response assertions.
- Weak pockets: some e2e tests rely on route/error-absence checks rather than explicit API payload/response contract evidence.

## End-to-End Expectations

- For fullstack, FE↔BE e2e exists (`e2e/tests/*.spec.ts`) and validates auth/routing role flows.
- Depth of data-contract and stateful business assertions in e2e remains moderate.

## Test Coverage Score (0–100)

**94/100**

## Score Rationale

- Endpoint coverage and true no-mock endpoint coverage are complete (72/72).
- Strong RBAC, validation, negative-path coverage.
- Deduction for remaining mock-heavy zones (frontend unit and some API-path mocking) and moderate e2e depth.

## Key Gaps

- Reduce remaining `force_authenticate` usage in inventory API tests where full JWT flow is feasible.
- Increase FE↔BE e2e depth (assert persisted business effects, not only navigation/visibility).

## Confidence & Assumptions

- Confidence: high on endpoint inventory and coverage mapping.
- Confidence: medium on quality scoring (static-only review).
- Assumption: endpoint routing resolution based on declared Django URL/router/viewset contracts.

---

# README Audit

## README Location

- Found at `repo/README.md` (`README.md`).

## Hard Gates

- Formatting: PASS (clean markdown and readable structure).
- Startup instructions (fullstack/backend): PASS (contains `docker-compose up --build -d` at `README.md:54`, satisfies required `docker-compose up`).
- Access method: PASS (URLs/ports at `README.md:59`, `README.md:60`, `README.md:61`).
- Verification method: PASS (health endpoint + login verification flow at `README.md:61`, `README.md:83`).
- Environment rules: PASS in README text (no `npm install`/`pip install`/`apt-get`/manual DB setup instructions).
- Demo credentials (auth exists): PASS (role + username + password table at `README.md:85`).

## High Priority Issues

- Project type token is not explicitly declared at top using required exact values (`backend|fullstack|web|android|ios|desktop`).
  - Evidence: README uses prose "full-stack" (`README.md:3`) rather than explicit token `fullstack`.

## Medium Priority Issues

- Testing section states containerized test orchestration, but repository test runner still performs local e2e dependency/bootstrap on first run.
  - Evidence: `run_tests.sh:449` (`npm install`), `run_tests.sh:451` (`npx playwright install`).

## Low Priority Issues

- Verification guidance is valid but could include a concrete API command example (`curl`/Postman request sample) for stricter reproducibility.

## Hard Gate Failures

- None.

## README Verdict

**PARTIAL PASS**

Reason: all hard gates pass, but strict project-type declaration format at top is not exact.

---

## Final Verdicts

- Test Coverage Audit Verdict: **PASS (strong)**
- README Audit Verdict: **PARTIAL PASS**
