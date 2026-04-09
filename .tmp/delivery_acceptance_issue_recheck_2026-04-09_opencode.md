# Delivery Acceptance Issue Re-check (Static)

Date: 2026-04-09
Scope: static code inspection only (no runtime/test execution)

## Overall result

- Prior issues re-checked: **4**
- Fixed: **4/4**
- Remaining blocker from prior report: **cleared in code**

---

## 1) Blocker — Offline-only bypass on crawl execution URLs

**Previous status:** Open (Blocker)

**Current status:** **Fixed**

### Evidence of fix

- Shared local/private URL validator added:
  - `repo/backend/crawling/serializers.py:11`
- `base_url` now uses shared validator:
  - `repo/backend/crawling/serializers.py:91`
- `url_pattern` now validated for rule version creation:
  - `repo/backend/crawling/serializers.py:178`
- Enqueue task URL now validated:
  - `repo/backend/crawling/serializers.py:231`
- Defense-in-depth guard in rule test endpoint before HTTP call:
  - `repo/backend/crawling/views.py:240`
  - `repo/backend/crawling/views.py:242`

### Coverage evidence added

- Rule-test endpoint rejects public URL even if inserted directly in DB:
  - `repo/backend/crawling/tests.py:1222`

---

## 2) Medium — Ambiguous scan matches (barcode/RFID not unique)

**Previous status:** Open (Medium)

**Current status:** **Fixed (application-layer)**

### Evidence of fix

- Create/update validation now enforces non-empty barcode uniqueness:
  - `repo/backend/inventory/serializers.py:66`
  - `repo/backend/inventory/serializers.py:72`
- Create/update validation now enforces non-empty RFID uniqueness:
  - `repo/backend/inventory/serializers.py:76`
  - `repo/backend/inventory/serializers.py:82`
- Scan endpoint now returns deterministic conflict when multiple matches exist:
  - `repo/backend/inventory/views.py:73`
  - `repo/backend/inventory/views.py:80`
  - `repo/backend/inventory/views.py:90`

### Note

- Model fields remain `db_index=True` and are not DB-unique (`repo/backend/inventory/models.py:56`, `repo/backend/inventory/models.py:57`), but the prior acceptance recommendation allowed deterministic conflict handling as an alternative; that path is now implemented.

---

## 3) Medium — New critical paths under-tested

**Previous status:** Open (Medium)

**Current status:** **Fixed**

### Evidence of new tests

- New integration test section explicitly added:
  - `repo/backend/crawling/tests.py:1143`
- Crawled payload persistence write test:
  - `repo/backend/crawling/tests.py:1180`
- Crawled payload dedupe test:
  - `repo/backend/crawling/tests.py:1187`
- Rule `/test/` endpoint contract test:
  - `repo/backend/crawling/tests.py:1210`
- `quota_pre_acquired=True` worker path test:
  - `repo/backend/crawling/tests.py:1238`
- `promote_waiting_tasks` promotion path test:
  - `repo/backend/crawling/tests.py:1252`

---

## 4) Low — DigestSchedule signal regression test missing

**Previous status:** Open (Low)

**Current status:** **Fixed**

### Evidence of fix

- Signal implementation present and registered:
  - `repo/backend/notifications/signals.py:13`
  - `repo/backend/notifications/apps.py:8`
- Dedicated regression tests added:
  - test schedule created once on user creation: `repo/backend/notifications/tests.py:966`, `repo/backend/notifications/tests.py:976`
  - test default send time remains 18:00: `repo/backend/notifications/tests.py:982`
  - test user update does not create duplicate schedule: `repo/backend/notifications/tests.py:987`

---

## Additional observation from re-check

- External SMTP rejection tests were also added (previously missing in earlier re-review snapshot):
  - `repo/backend/notifications/tests.py:888`
  - `repo/backend/notifications/tests.py:899`

## Final re-check judgment

- The specific issues listed in the prior report are now addressed in code and (for most items) covered by new tests.
- Runtime confirmation still requires executing the suite, but statically the prior blocker/medium/low items are resolved.
