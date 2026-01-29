#!/bin/bash
# Compare Airflow database state between staging-1 and staging-10

echo "=== Staging-1 Airflow Database State ==="
source ~/staging-1/.env.staging-1

PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" << 'SQL'
-- Check DAG runs
SELECT 
    dag_id,
    run_id,
    state,
    start_date,
    end_date,
    run_type
FROM dag_run
WHERE dag_id = 'jobs_etl_daily'
ORDER BY start_date DESC
LIMIT 5;
SQL

echo ""
echo "=== Staging-1 Task Instances (normalize_jobs) ==="
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" << 'SQL'
SELECT 
    ti.dag_id,
    ti.run_id,
    ti.task_id,
    ti.state,
    ti.try_number,
    ti.start_date,
    ti.end_date,
    ti.duration,
    ti.executor_state
FROM task_instance ti
JOIN dag_run dr ON ti.dag_id = dr.dag_id AND ti.run_id = dr.run_id
WHERE ti.dag_id = 'jobs_etl_daily'
    AND ti.task_id = 'normalize_jobs'
ORDER BY ti.start_date DESC
LIMIT 5;
SQL

echo ""
echo "=== Staging-10 Airflow Database State ==="
source ~/staging-10/.env.staging-10

PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" << 'SQL'
-- Check DAG runs
SELECT 
    dag_id,
    run_id,
    state,
    start_date,
    end_date,
    run_type
FROM dag_run
WHERE dag_id = 'jobs_etl_daily'
ORDER BY start_date DESC
LIMIT 5;
SQL

echo ""
echo "=== Staging-10 Task Instances (normalize_jobs) ==="
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" << 'SQL'
SELECT 
    ti.dag_id,
    ti.run_id,
    ti.task_id,
    ti.state,
    ti.try_number,
    ti.start_date,
    ti.end_date,
    ti.duration,
    ti.executor_state
FROM task_instance ti
JOIN dag_run dr ON ti.dag_id = dr.dag_id AND ti.run_id = dr.run_id
WHERE ti.dag_id = 'jobs_etl_daily'
    AND ti.task_id = 'normalize_jobs'
ORDER BY ti.start_date DESC
LIMIT 5;
SQL

echo ""
echo "=== Comparing executor_state vs state mismatch ==="
echo "Staging-10 tasks with executor_state=success but state!=success:"
PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" << 'SQL'
SELECT 
    ti.run_id,
    ti.task_id,
    ti.state,
    ti.executor_state,
    ti.try_number,
    ti.start_date
FROM task_instance ti
WHERE ti.dag_id = 'jobs_etl_daily'
    AND ti.task_id = 'normalize_jobs'
    AND ti.executor_state = 'success'
    AND ti.state != 'success'
ORDER BY ti.start_date DESC
LIMIT 10;
SQL
