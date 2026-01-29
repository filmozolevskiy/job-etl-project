#!/bin/bash
# Compare Airflow configurations between staging-1 and staging-10

echo "=== Staging-1 Environment Variables ==="
cd /home/deploy/staging-1/job-search-project
if docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 ps -q airflow-scheduler > /dev/null 2>&1; then
  docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 exec -T airflow-scheduler bash -c 'env | grep -E "AIRFLOW_|POSTGRES_|ENVIRONMENT" | sort'
else
  echo "Staging-1 containers not running"
fi

echo ""
echo "=== Staging-10 Environment Variables ==="
cd /home/deploy/staging-10/job-search-project
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c 'env | grep -E "AIRFLOW_|POSTGRES_|ENVIRONMENT" | sort'

echo ""
echo "=== Staging-1 Docker Compose Files ==="
cd /home/deploy/staging-1/job-search-project
if [ -f docker-compose.yml ] && [ -f docker-compose.staging.yml ]; then
  echo "Files exist"
  echo "docker-compose.yml size: $(wc -l < docker-compose.yml)"
  echo "docker-compose.staging.yml size: $(wc -l < docker-compose.staging.yml)"
else
  echo "Files not found"
fi

echo ""
echo "=== Staging-10 Docker Compose Files ==="
cd /home/deploy/staging-10/job-search-project
if [ -f docker-compose.yml ] && [ -f docker-compose.staging.yml ]; then
  echo "Files exist"
  echo "docker-compose.yml size: $(wc -l < docker-compose.yml)"
  echo "docker-compose.staging.yml size: $(wc -l < docker-compose.staging.yml)"
else
  echo "Files not found"
fi

echo ""
echo "=== Comparing docker-compose.staging.yml ==="
diff -u /home/deploy/staging-1/job-search-project/docker-compose.staging.yml /home/deploy/staging-10/job-search-project/docker-compose.staging.yml || echo "Files differ"

echo ""
echo "=== Staging-1 Airflow Config (if accessible) ==="
cd /home/deploy/staging-1/job-search-project
if docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 ps -q airflow-scheduler > /dev/null 2>&1; then
  docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-1 exec -T airflow-scheduler bash -c 'cat /opt/airflow/airflow.cfg 2>/dev/null | grep -E "^\[core\]|^\[scheduler\]|^executor|^task_runner|^retry" | head -20' || echo "Config not accessible"
else
  echo "Container not running"
fi

echo ""
echo "=== Staging-10 Airflow Config ==="
cd /home/deploy/staging-10/job-search-project
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p staging-10 exec -T airflow-scheduler bash -c 'cat /opt/airflow/airflow.cfg 2>/dev/null | grep -E "^\[core\]|^\[scheduler\]|^executor|^task_runner|^retry" | head -20' || echo "Config not accessible"
