# Complete Verification Checklist

## ✅ Already Verified

- [x] **dbt Installation**: dbt-core 1.7.0 and dbt-postgres 1.7.0 installed in Airflow containers
- [x] **Database Schemas**: raw, staging, marts schemas exist
- [x] **Database Tables**: All 4 tables created:
  - `raw.jsearch_job_postings`
  - `raw.glassdoor_companies`
  - `staging.company_enrichment_queue`
  - `marts.profile_preferences`
- [x] **Model Naming**: No conflicts, all models recognized by dbt
- [x] **dbt Compilation**: Staging models compile successfully

## 🔍 Next Verification Steps

### Step 1: Verify dbt Connection to Database

**Command:**
```powershell
docker exec job_search_airflow_scheduler sh -c "cd /opt/airflow/dbt && dbt debug --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt"
```

**Expected Output:**
- Connection test: ✅ PASS
- Profile configuration: ✅ VALID
- All checks should pass

**If it fails:**
- Check PostgreSQL is running: `docker-compose ps postgres`
- Verify environment variables in docker-compose.yml match dbt/profiles.yml
- Check database credentials

---

### Step 2: Test dbt Compilation for All Models

**Command:**
```powershell
docker exec job_search_airflow_scheduler sh -c "cd /opt/airflow/dbt && dbt compile --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt 2>&1"
```

**Expected Output:**
- No compilation errors
- All models compile successfully
- SQL files generated in `dbt/target/compiled/`

**What to check:**
- Verify ephemeral models resolve correctly (raw models inline to table references)
- Check that staging models compile to valid SQL
- Ensure no syntax errors

---

### Step 3: Test dbt Run (Create Staging Tables)

**Command:**
```powershell
docker exec job_search_airflow_scheduler sh -c "cd /opt/airflow/dbt && dbt run --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt 2>&1"
```

**Expected Output:**
- Model runs successfully
- Table `staging.jsearch_job_postings` is created (even if empty)
- Success message: "Completed successfully"

**Verify in database:**
```powershell
docker exec -it job_search_postgres psql -U postgres -d job_search_db -c "\d staging.jsearch_job_postings"
```

**Expected:**
- Table exists with all expected columns
- Column types match the model definition

---

### Step 4: Test dbt Run for All Staging Models

**Command:**
```powershell
docker exec job_search_airflow_scheduler sh -c "cd /opt/airflow/dbt && dbt run --select staging.* --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt 2>&1"
```

**Expected Output:**
- All staging models run successfully:
  - `staging.jsearch_job_postings`
  - `staging.glassdoor_companies`
  - `staging.company_enrichment_queue` (ephemeral, won't create table)

**Verify tables:**
```powershell
docker exec -it job_search_postgres psql -U postgres -d job_search_db -c "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = 'staging' ORDER BY table_name;"
```

---

### Step 5: Test Ephemeral Model Resolution

**Purpose**: Verify that ephemeral raw models correctly resolve to table references in compiled SQL.

**Command:**
```powershell
docker exec job_search_airflow_scheduler sh -c "cd /opt/airflow/dbt && dbt compile --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt && cat target/compiled/job_search_platform/models/staging/jsearch_job_postings.sql | head -30"
```

**Expected Output:**
- Compiled SQL should show direct table reference: `from raw.jsearch_job_postings`
- NOT: `from (select * from raw.jsearch_job_postings) as ...`
- The ephemeral model should be inlined

---

### Step 6: Test with Sample Data (Optional but Recommended)

**Purpose**: Verify the full pipeline works with actual data.

**Step 6a: Insert test data into raw table**
```powershell
docker exec -it job_search_postgres psql -U postgres -d job_search_db -c @"
INSERT INTO raw.jsearch_job_postings (
    raw_job_posting_id,
    raw_payload,
    dwh_load_date,
    dwh_load_timestamp,
    dwh_source_system,
    profile_id
) VALUES (
    1,
    '{\"job_id\": \"test123\", \"job_title\": \"Data Engineer\", \"employer_name\": \"Test Company\", \"job_description\": \"Test description\"}'::jsonb,
    CURRENT_DATE,
    CURRENT_TIMESTAMP,
    'jsearch',
    1
);
"@
```

**Step 6b: Run staging model**
```powershell
docker exec job_search_airflow_scheduler sh -c "cd /opt/airflow/dbt && dbt run --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt 2>&1"
```

**Step 6c: Verify data transformed correctly**
```powershell
docker exec -it job_search_postgres psql -U postgres -d job_search_db -c "SELECT job_id, job_title, employer_name FROM staging.jsearch_job_postings;"
```

**Expected Output:**
- Row appears in staging table
- JSON fields extracted correctly
- job_id = 'test123', job_title = 'Data Engineer', etc.

---

### Step 7: Verify Airflow DAG Can Execute dbt Tasks

**Step 7a: Check Airflow UI**
1. Open http://localhost:8080
2. Login (default: admin/admin)
3. Find `jobs_etl_daily` DAG
4. Verify it's visible and not paused

**Step 7b: Test dbt task manually in Airflow**
1. In Airflow UI, click on `jobs_etl_daily` DAG
2. Click "normalize_jobs" task
3. Click "Run" → "Run Task"
4. Monitor logs

**Expected:**
- Task completes successfully
- Logs show dbt execution
- No errors

**Alternative: Test via command line**
```powershell
docker exec job_search_airflow_scheduler sh -c "cd /opt/airflow/dbt && dbt run --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt"
```

---

### Step 8: Verify All Airflow Services Are Running

**Command:**
```powershell
docker-compose ps
```

**Expected:**
- `job_search_postgres`: Up (healthy)
- `job_search_airflow_webserver`: Up (healthy)
- `job_search_airflow_scheduler`: Up (healthy)
- `job_search_airflow_init`: Exited (0) - This is normal, init only runs once

---

### Step 9: Verify Environment Variables

**Check that all required env vars are set:**
```powershell
docker exec job_search_airflow_scheduler env | Select-String -Pattern "POSTGRES|JSEARCH|GLASSDOOR|SMTP"
```

**Expected:**
- POSTGRES_HOST=postgres
- POSTGRES_PORT=5432
- POSTGRES_USER=postgres (or your value)
- POSTGRES_DB=job_search_db
- JSEARCH_API_KEY (if set)
- GLASSDOOR_API_KEY (if set)
- SMTP_* variables (if set)

---

### Step 10: Test Full DAG Execution (Dry Run)

**Purpose**: Verify all tasks can execute (even if they're placeholders)

**In Airflow UI:**
1. Go to `jobs_etl_daily` DAG
2. Click "Trigger DAG"
3. Monitor execution

**Expected:**
- All tasks show up
- Tasks that are placeholders (extract_job_postings, etc.) will echo messages
- dbt tasks (normalize_jobs, normalize_companies, dbt_modelling, dbt_tests) should execute
- DAG completes (may have some skipped tasks if dependencies fail)

---

## 🎯 Success Criteria

All verification steps pass when:

✅ **dbt Connection**: `dbt debug` shows all checks passing  
✅ **dbt Compilation**: All models compile without errors  
✅ **dbt Execution**: Staging models can run and create tables  
✅ **Data Transformation**: Sample data flows correctly from raw → staging  
✅ **Airflow Integration**: DAG tasks can execute dbt commands  
✅ **Ephemeral Models**: Raw models correctly inline to table references  
✅ **All Services**: Docker containers are healthy and running  

---

## 🐛 Troubleshooting

### Issue: dbt debug fails
- **Check**: PostgreSQL container is running and healthy
- **Check**: Database credentials in docker-compose.yml match dbt/profiles.yml
- **Fix**: Restart PostgreSQL: `docker-compose restart postgres`

### Issue: Models don't compile
- **Check**: Model file syntax (SQL is valid PostgreSQL)
- **Check**: All referenced models exist
- **Check**: Schema names match between models and database

### Issue: Tables don't exist after dbt run
- **Check**: dbt has permissions to create tables
- **Check**: Schema exists in database
- **Check**: dbt run logs for errors

### Issue: Airflow tasks fail
- **Check**: dbt is installed in container (we verified this ✅)
- **Check**: Paths in DAG are correct (`/opt/airflow/dbt`)
- **Check**: Airflow logs for specific error messages

---

## 📝 Next Steps After Verification

Once all verification steps pass:

1. ✅ **Setup Complete** - Infrastructure is ready
2. ⏭️ **Implement Python Services**:
   - JSearch API client
   - Source Extractor service
   - Glassdoor API client
   - Company Extraction service
   - Ranker service
   - Email Notification service
3. ⏭️ **Create Marts Models**:
   - `marts.dim_companies`
   - `marts.fact_jobs`
   - `marts.dim_ranking`
4. ⏭️ **Implement Profile Management UI**
5. ⏭️ **End-to-End Testing**

