# Cursor Cloud Agents Setup Research & Recommendations

## Executive Summary

This document provides research findings and recommendations for configuring Cursor Cloud Agents (Background Agents) for the Job Search Project. Cloud Agents enable remote AI agents to clone your repository, run code in isolated environments, work on feature branches, and push PRs autonomously.

## Current Setup Analysis

### Existing Configuration

- **`.cursor/environment.json`**: Currently minimal - only has Dockerfile context:
  ```json
  {
    "build": {
      "context": "..",
      "dockerfile": "Dockerfile"
    },
    "terminals": []
  }
  ```

- **`.cursor/Dockerfile`**: Exists and defines base Python 3.11 environment with dependencies
- **Root `Dockerfile`**: Python 3.11-slim with PostgreSQL client, dbt, spaCy models
- **`docker-compose.yml`**: Multi-service setup (PostgreSQL, Airflow, Flask UI) - **NOT directly usable in Cloud Agents**

### Key Constraints for Cloud Agents

1. **Single Container Environment**: Cloud Agents run in a single container, not a docker-compose stack
2. **No External Services**: Can't automatically start PostgreSQL, Airflow, or other services via docker-compose
3. **Remote Database**: Agents will need to connect to an external database (or use a hosted test DB)
4. **Environment Variables**: Must be configured via Cursor Secrets (not `.env` files)

## Research Findings

### How Cloud Agents Work

1. **Clone Repository**: Agent clones your GitHub/GitLab repository
2. **Load Snapshot**: Uses a machine snapshot (OS + base dependencies) or builds from Dockerfile
3. **Run Install Command**: Executes `install` command from `environment.json` (e.g., `pip install -r requirements.txt`)
4. **Run Start Command** (optional): Executes `start` command for services that need to be running
5. **Run Terminal Commands** (optional): Background commands in tmux sessions (e.g., dev servers, watchers)
6. **Execute Tasks**: Agent performs code changes, runs tests, creates branches, pushes PRs

### Required Configuration

Cloud Agents require:

1. **Git Provider Connection**: GitHub/GitLab account connected in Cursor Settings
2. **Git-Tracked Workspace**: Repository must be initialized with Git
3. **`environment.json`**: Defines environment setup (snapshot, install, start, terminals)
4. **Secrets Configuration**: Environment variables configured in Cursor Settings → Cloud Agents → Secrets
5. **Dockerfile** (optional): Custom base image if default Ubuntu snapshot isn't sufficient

## Recommendations

### 1. Update `.cursor/environment.json`

**Current State**: Only has Dockerfile context, no install/start/terminals

**Recommended Configuration**:

```json
{
  "build": {
    "context": "..",
    "dockerfile": "Dockerfile"
  },
  "install": "pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir dbt-core==1.7.0 dbt-postgres==1.7.0 && python -m spacy download en_core_web_sm",
  "start": "",
  "terminals": []
}
```

**Explanation**:
- `install`: Installs Python dependencies, dbt, and spaCy model (idempotent)
- `start`: Leave empty (no services need to start automatically)
- `terminals`: Leave empty (no background processes needed for cloud agent tasks)

**Alternative (Lighter Install)**:

If install takes too long, split into Dockerfile (base deps) and install (changing deps):

```json
{
  "build": {
    "context": "..",
    "dockerfile": "Dockerfile"
  },
  "install": "pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt",
  "start": "",
  "terminals": []
}
```

(This assumes Dockerfile already installs dbt and spaCy model - which it currently does)

### 2. Verify Dockerfile is Cloud Agent Compatible

**Current `Dockerfile` Analysis**:

✅ **Good**:
- Uses `python:3.11-slim` base image
- Installs system dependencies (libpq-dev, postgresql-client, git)
- Installs Python packages
- Installs dbt-postgres
- Downloads spaCy model
- Sets PYTHONPATH correctly

✅ **Cloud Agent Ready**: The current Dockerfile is well-suited for Cloud Agents

**Potential Optimization**:

If you want faster agent startup, consider pre-building a snapshot with all dependencies installed. However, the current Dockerfile approach is fine for initial setup.

### 3. Configure Required Secrets

Cloud Agents can't access `.env` files. All environment variables must be configured in **Cursor Settings → Cloud Agents → Secrets**.

**Required Secrets** (from `env.template`):

**Critical (for basic functionality)**:
- `POSTGRES_HOST` - External database host (e.g., `your-db.example.com`)
- `POSTGRES_PORT` - Database port (e.g., `5432`)
- `POSTGRES_USER` - Database user (e.g., `postgres`)
- `POSTGRES_PASSWORD` - Database password
- `POSTGRES_DB` - Database name (e.g., `job_search_db`)

**API Keys** (for ETL/enrichment):
- `JSEARCH_API_KEY` - JSearch API key
- `GLASSDOOR_API_KEY` - Glassdoor API key (if used)
- `OPENAI_API_KEY` - OpenAI API key (for ChatGPT enrichment)

**Flask/Auth** (if testing UI features):
- `FLASK_SECRET_KEY` - Flask session secret key
- `JWT_SECRET_KEY` - JWT token secret key

**Airflow** (if testing DAGs):
- `AIRFLOW_FERNET_KEY` - Airflow encryption key
- `AIRFLOW_API_URL` - Airflow API endpoint (if external)
- `AIRFLOW_API_USERNAME` - Airflow API username
- `AIRFLOW_API_PASSWORD` - Airflow API password

**Optional**:
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` - For email notifications
- `JSEARCH_NUM_PAGES` - Default: `10`
- `CHATGPT_MODEL` - Default: `gpt-5-nano`
- Other ChatGPT config vars (use defaults unless needed)

**Secrets Setup Steps**:

1. Open Cursor Settings (Command/Ctrl + ,)
2. Navigate to **Cloud Agents** → **Secrets**
3. Add each secret as a key-value pair
4. Values are encrypted at rest and only available to running agents
5. Test by checking `os.environ` in agent environment

### 4. Database Access Strategy

**Challenge**: Cloud Agents run in isolated containers without access to your local docker-compose PostgreSQL instance.

**Recommended Approaches**:

#### Option A: External/Cloud Database (Recommended for Production-Like Testing)

- Use a hosted PostgreSQL instance (AWS RDS, Google Cloud SQL, Supabase, etc.)
- Configure connection details in Cursor Secrets
- Agents connect directly to this database
- **Pros**: Realistic environment, persistent data
- **Cons**: Requires hosting setup, potential costs

#### Option B: Test Database with Minimal Schema

- Create a lightweight test database with only essential tables
- Use environment variables to point to this test DB
- **Pros**: Fast setup, isolated test data
- **Cons**: Limited schema, may need custom migrations

#### Option C: SQLite for Agent Testing (If Applicable)

- If your code supports SQLite, use it for cloud agent tasks
- **Pros**: No external dependencies, fast
- **Cons**: Limited SQL features, not production-like

**Recommendation**: Start with Option A (external database) for full functionality, or Option B for faster iteration.

### 5. Update `.cursor/Dockerfile` (If Separate from Root)

**Check**: Does `.cursor/Dockerfile` exist and differ from root `Dockerfile`?

If `.cursor/Dockerfile` is different, ensure it:
- Matches the environment needed for cloud agents
- Installs all required dependencies
- Is compatible with the `install` command in `environment.json`

If `.cursor/Dockerfile` doesn't exist or is outdated, the root `Dockerfile` will be used (which is fine based on current setup).

### 6. Testing Strategy

**What Cloud Agents Can Do**:
- ✅ Run Python unit tests (`pytest tests/unit`)
- ✅ Run integration tests (if database is accessible)
- ✅ Run linting (`ruff`)
- ✅ Execute dbt compilation (`dbt compile`)
- ✅ Execute dbt tests (`dbt test`) if database accessible
- ✅ Run scripts that don't require docker-compose services

**What Cloud Agents Cannot Do (Without Additional Setup)**:
- ❌ Run full docker-compose stack (no Docker-in-Docker)
- ❌ Access localhost services (no network access to your machine)
- ❌ Use `.env` files (must use Secrets)

**Testing Recommendations**:

1. **Unit Tests**: Agents can run all unit tests without database
2. **Integration Tests**: Require external database access (configure in Secrets)
3. **dbt Tests**: Require database connection (use external DB)
4. **Service Tests**: May need mock services or external endpoints

## Implementation Checklist

### Phase 1: Basic Setup (Minimal Dependencies)

- [ ] **Update `.cursor/environment.json`** with `install` command
- [ ] **Verify Dockerfile** is compatible with cloud agents
- [ ] **Connect Git Provider** in Cursor Settings (if not already)
- [ ] **Test Environment Setup** using "Validate Setup" in Cursor

### Phase 2: Secrets Configuration

- [ ] **Add Database Secrets** (POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)
- [ ] **Add API Key Secrets** (JSEARCH_API_KEY, OPENAI_API_KEY, etc.)
- [ ] **Add Flask Secrets** (FLASK_SECRET_KEY, JWT_SECRET_KEY) if testing UI
- [ ] **Verify Secrets Access** (check `os.environ` in agent session)

### Phase 3: Database Access

- [ ] **Set Up External Database** (AWS RDS, Google Cloud SQL, Supabase, etc.)
- [ ] **Configure Connection** in Secrets
- [ ] **Run Schema Migrations** on external database (if needed)
- [ ] **Test Connection** from cloud agent environment

### Phase 4: Advanced Configuration (Optional)

- [ ] **Optimize Install Command** (split Dockerfile vs install if needed)
- [ ] **Configure Terminal Commands** (if background processes needed)
- [ ] **Set Up CI Integration** (if agents should trigger CI/CD)
- [ ] **Document Agent Capabilities** for team

## Common Issues & Troubleshooting

### Issue: "Validate Setup" Fails

**Causes**:
- Install command fails (check dependencies, network access)
- Dockerfile build fails (check base image, build context)
- Network errors (proxy, firewall blocking GitHub/Docker Hub)

**Solutions**:
- Test install command locally first
- Simplify install command (remove optional deps temporarily)
- Check network/firewall settings

### Issue: Secrets Not Accessible

**Causes**:
- Secrets not configured in Cursor Settings
- Secret names don't match code expectations (case-sensitive)
- Secrets not propagated to running agent

**Solutions**:
- Verify secrets in Cursor Settings → Cloud Agents → Secrets
- Check secret names match exactly (case-sensitive)
- Restart agent or re-validate setup

### Issue: Database Connection Fails

**Causes**:
- Database host not accessible from cloud agent network
- Credentials incorrect
- Database firewall blocking agent IPs

**Solutions**:
- Use publicly accessible database host
- Verify credentials in Secrets
- Configure database firewall to allow Cursor's IP ranges (if possible) or use 0.0.0.0/0 with strong authentication

### Issue: Install Takes Too Long

**Causes**:
- Installing large dependencies (spaCy models, dbt, etc.)
- Network latency downloading packages

**Solutions**:
- Pre-install heavy deps in Dockerfile (move from `install` to Dockerfile)
- Use cached snapshots (if available in Cursor plan)
- Optimize requirements.txt (remove unused deps)

## Best Practices

1. **Keep Install Idempotent**: Install command should be safe to run multiple times
2. **Minimize Install Time**: Move heavy deps to Dockerfile, keep `install` for changing deps
3. **Use Secrets for All Credentials**: Never hardcode or commit secrets
4. **Test Locally First**: Validate install/start commands locally before configuring agents
5. **Document Agent Capabilities**: Clarify what agents can/cannot do for your team
6. **Monitor Agent Performance**: Track install times, execution success rates

## Next Steps

1. **Immediate**: Update `.cursor/environment.json` with install command
2. **Short-term**: Configure essential secrets (database, API keys)
3. **Medium-term**: Set up external database for full testing
4. **Long-term**: Optimize setup based on agent usage patterns

## References

- [Cursor Background Agents Documentation](https://docs.cursor.com/en/background-agents)
- [Cursor Forum - Cloud Agents](https://forum.cursor.com/c/background-agents/16)
- Current project structure and configuration files

---

**Last Updated**: Based on research as of January 2025
**Status**: Recommendations ready for implementation
