# Testing dbt Setup in Docker

## Quick Test Guide

### 1. Rebuild Docker Images (First Time)

Since we've added a custom Dockerfile, rebuild the Airflow images:

```powershell
docker-compose build
```

This will install dbt-core and dbt-postgres in the Airflow containers.

### 2. Start Services

```powershell
docker-compose up -d
```

Wait for services to start (especially PostgreSQL initialization).

### 3. Verify dbt is Installed

Check if dbt is available in the Airflow container:

```powershell
docker exec -it job_search_airflow_scheduler dbt --version
```

Expected output:
```
installed version: 1.7.0
```

### 4. Test dbt Connection

Test dbt can connect to PostgreSQL:

```powershell
docker exec -it job_search_airflow_scheduler dbt debug --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt
```

Expected output should show:
- Connection test: PASS
- Profile configuration: VALID

### 5. Verify Tables Were Created

Check that PostgreSQL initialization scripts ran:

```powershell
docker exec -it job_search_postgres psql -U postgres -d job_search_db -c "\dt raw.*"
docker exec -it job_search_postgres psql -U postgres -d job_search_db -c "\dt staging.*"
docker exec -it job_search_postgres psql -U postgres -d job_search_db -c "\dt marts.*"
```

You should see:
- `raw.jsearch_job_postings`
- `raw.glassdoor_companies`
- `staging.company_enrichment_queue`
- `marts.profile_preferences`

### 6. Test dbt Compilation

Compile a staging model to verify ephemeral model references work:

```powershell
docker exec -it job_search_airflow_scheduler dbt compile --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt
```

This should compile successfully and create SQL in `dbt/target/compiled/`.

### 7. Test dbt Run (with Empty Tables)

Even with empty raw tables, staging models should create empty staging tables:

```powershell
docker exec -it job_search_airflow_scheduler dbt run --select staging.jsearch_job_postings --profiles-dir /opt/airflow/dbt --project-dir /opt/airflow/dbt
```

Expected: Success message, staging table created (even if empty).

### 8. Verify in Airflow UI

1. Open http://localhost:8080
2. Login with credentials from `.env` (default: admin/admin)
3. Find the `jobs_etl_daily` DAG
4. Check that dbt tasks are visible and can be triggered

## Troubleshooting

### Issue: dbt command not found
**Solution**: Rebuild images: `docker-compose build`

### Issue: Connection test fails
**Check**:
- PostgreSQL container is running: `docker-compose ps`
- Environment variables are set correctly in docker-compose.yml
- Database name matches in `dbt/profiles.yml`

### Issue: Tables don't exist
**Check**:
- PostgreSQL logs: `docker-compose logs postgres`
- Init scripts ran: Look for "CREATE TABLE" messages in logs
- Manually run init scripts if needed

### Issue: Ephemeral model compilation error
**Check**:
- Raw tables exist: `\dt raw.*` in psql
- Model file syntax is correct
- dbt version compatibility

## Success Criteria

✅ dbt --version shows 1.7.0  
✅ dbt debug shows connection PASS  
✅ All tables exist in PostgreSQL  
✅ dbt compile succeeds  
✅ dbt run creates staging tables  
✅ Airflow DAG shows dbt tasks  

Once all checks pass, the setup is ready for implementing Python services!

