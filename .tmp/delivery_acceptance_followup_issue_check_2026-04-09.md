# Follow-up Audit: Previously Reported Issues Re-check (Static Only)

## Scope

- Purpose: Re-check the specific issues listed in the prior report, using static evidence only.
- Not executed: no runtime startup, no tests, no Docker execution.

## Re-check Results

| Previous Issue | Previous Severity | Current Status | Evidence | Notes |
|---|---|---|---|---|
| Predictable placeholder `DJANGO_SECRET_KEY` accepted | High | **Fixed** | Placeholder pattern block in secret loader: `repo/backend/config/settings.py:24`, `repo/backend/config/settings.py:40`, startup fail on placeholder: `repo/backend/config/settings.py:42` | Non-test startup now rejects placeholder-like values. |
| No explicit negative API test for external SMTP host rejection | Medium | **Fixed** | SMTP validator exists: `repo/backend/notifications/serializers.py:86`; explicit negative tests added: `repo/backend/notifications/tests.py:880`, `repo/backend/notifications/tests.py:891` | Coverage now includes hostname and public IP rejection for SMTP. |
| Start section lacked explicit `.env` prerequisite | Medium | **Fixed** | New prerequisites section: `repo/README.md:3`; explicit warning in start section: `repo/README.md:24` | Start workflow now clearly requires env setup before `docker compose up`. |
| `run_test.sh` only warned on placeholders (no fail-fast) | Low | **Fixed** | Script now aborts when `CHANGE_ME` remains: `repo/run_test.sh:89`, `repo/run_test.sh:93` | Behavior changed from warning-only to enforced failure. |

## Conclusion

- All four previously listed issues are **fixed** in the current static snapshot.
- No regressions were observed for these specific items in reviewed files.

## Verification Boundary

- This check confirms code/documentation/test presence only.
- **Manual Verification Required** for runtime behavior (startup path, endpoint behavior during live execution).
