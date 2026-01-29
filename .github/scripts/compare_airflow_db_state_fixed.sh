#!/bin/bash
# Compare Airflow database state between staging-1 and staging-10

echo "=== Staging-1 Task Instances (normalize_jobs) - Last 5 ==="
source ~/staging-1/.env.staging-1

PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" << 'SQL'
SELECT 
    ti.dag_id,
    ti.run_id,
    ti.task_id,
    ti.state,
    ti.try_number,
    ti.start_date,
    ti.end_date,
    ti.duration
FROM task_instance ti
JOIN dag_run dr ON ti.dag_id = dr.dag_id AND ti.run_id = dr.run_id
WHERE ti.dag_id = 'jobs_etl_daily'
    AND ti.task_id = 'normalize_jobs'
ORDER BY ti.start_date DESC
LIMIT 5;
SQL

echo ""
echo "=== Staging-10 Task Instances (normalize_jobs) - Last 5 ==="
source ~/staging-10/.env.staging-10

PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" << 'SQL'
SELECT 
    ti.dag_id,
    ti.run_id,
    ti.task_id,
    ti.state,
    ti.try_number,
    ti.start_date,
    ti.end_date,
    ti.duration
FROM task_instance ti
JOIN dag_run dr ON ti.dag_id = dr.dag_id AND ti.run_id = dr.run_id
WHERE ti.dag_id = 'jobs_etl_daily'
    AND ti.task_id = 'normalize_jobs'
ORDER BY ti.start_date DESC
LIMIT 5;
SQL

echo ""
echo "=== Staging-1 Successful normalize_jobs task details ==="
source ~/staging-1/.env.staging-1

PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" << 'SQL'
SELECT 
    ti.run_id,
    ti.state,
    ti.try_number,
    ti.start_date,
    ti.end_date,
    ti.duration,
    dr.state as dag_run_state
FROM task_instance ti
JOIN dag_run dr ON ti.dag_id = dr.dag_id AND ti.run_id = dr.run_id
WHERE ti.dag_id = 'jobs_etl_daily'
    AND ti.task_id = 'normalize_jobs'
    AND ti.state = 'success'
ORDER BY ti.start_date DESC
LIMIT 3;
SQL

echo ""
echo "=== Staging-10 Failed normalize_jobs task details ==="
source ~/staging-10/.env.staging-10

PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" << 'SQL'
SELECT 
    ti.run_id,
    ti.state,
    ti.try_number,
    ti.start_date,
    ti.end_date,
    ti.duration,
    dr.state as dag_run_state
FROM task_instance ti
JOIN dag_run dr ON ti.dag_id = dr.dag_id AND ti.run_id = dr.run_id
WHERE ti.dag_id = 'jobs_etl_daily'
    AND ti.task_id = 'normalize_jobs'
    AND ti.state != 'success'
ORDER BY ti.start_date DESC
LIMIT 3;
SQL
