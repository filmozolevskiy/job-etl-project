# Staging Slot Registry

This document defines the **static** staging slot layout (ports, subdomains, databases). **Current slot usage (claim/release) is stored in the database**, not in this file.

## Slot usage: database and API

- **Registry**: Table `marts.staging_slots` (e.g. in production DB backing justapply.net).
- **Staging Dashboard**: https://justapply.net/staging — view and manage slots (claim/release via UI).
- **API**: `GET/PUT /api/staging/slots`, `POST /api/staging/slots/<slot_id>/release` (admin JWT).
- **Release rule**: See `.cursorrules` § Staging slots (source of truth & release) for when and how to release a slot.

## Available Staging Slots (static reference)

| Slot | Identifier | Subdomain | Campaign UI Port | Airflow Port | Database |
|------|------------|-----------|------------------|--------------|----------|
| 1 | `staging-1` | `staging-1.justapply.net` | 5001 | 8081 | `job_search_staging_1` |
| 2 | `staging-2` | `staging-2.justapply.net` | 5002 | 8082 | `job_search_staging_2` |
| 3 | `staging-3` | `staging-3.justapply.net` | 5003 | 8083 | `job_search_staging_3` |
| 4 | `staging-4` | `staging-4.justapply.net` | 5004 | 8084 | `job_search_staging_4` |
| 5 | `staging-5` | `staging-5.justapply.net` | 5005 | 8085 | `job_search_staging_5` |
| 6 | `staging-6` | `staging-6.justapply.net` | 5006 | 8086 | `job_search_staging_6` |
| 7 | `staging-7` | `staging-7.justapply.net` | 5007 | 8087 | `job_search_staging_7` |
| 8 | `staging-8` | `staging-8.justapply.net` | 5008 | 8088 | `job_search_staging_8` |
| 9 | `staging-9` | `staging-9.justapply.net` | 5009 | 8089 | `job_search_staging_9` |
| 10 | `staging-10` | `staging-10.justapply.net` | 5010 | 8090 | `job_search_staging_10` |

**Production** runs on a dedicated droplet (`167.99.0.168`); slot 10 on the staging droplet is a normal staging slot.

## Ownership rules (summary)

- **One slot per task**: Each Linear issue gets one staging slot (slots 1–9 for QA; slot 10 available for staging).
- **Claim**: Via Staging API or by updating `marts.staging_slots` (or Staging Dashboard).
- **Release**: After PR merge (or when closing the task); use API or DB (see release rule).

## Deploy and verify

- **Deploy**: `./scripts/deploy-staging.sh <slot-id> [branch]`
- **Version**: `curl https://staging-N.justapply.net/api/version` or check Campaign UI footer.
