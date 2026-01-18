# CI Status Checking Scripts

Scripts for checking CI status and extracting error information from GitHub Actions workflow runs.

## Prerequisites

- Python 3.11+
- Install dependencies: `pip install PyGithub requests`
- GitHub Personal Access Token with `repo` and `actions:read` permissions

## Setting Up GitHub Token

### For Cursor Cloud Agents (Recommended)

Cloud Agents cannot access local environment variables. Configure `GITHUB_TOKEN` in Cursor Settings:

1. Open **Cursor Settings** (`Ctrl/Cmd + ,`)
2. Navigate to **Cloud Agents** → **Secrets**
3. Click **Add Secret**
4. Key: `GITHUB_TOKEN`
5. Value: Your GitHub Personal Access Token
6. Click **Save**

The token will be automatically available as `GITHUB_TOKEN` environment variable in Cloud Agents.

**Creating a GitHub Token:**
1. Go to https://github.com/settings/tokens
2. Click **Generate new token** → **Generate new token (classic)**
3. Name: `Cursor Cloud Agents` (or any descriptive name)
4. Select scopes:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `actions:read` (Read workflow runs and logs)
5. Click **Generate token**
6. Copy the token (you won't see it again)
7. Add it to Cursor Cloud Agents Secrets as described above

### For Local Cursor Development

**Option 1: Environment Variable (Recommended for Local Cursor)**

Set the `GITHUB_TOKEN` environment variable in your system or PowerShell profile:

**Windows PowerShell (User Profile):**
```powershell
# Add to $PROFILE (usually ~\Documents\PowerShell\Microsoft.PowerShell_profile.ps1)
$env:GITHUB_TOKEN = "your_token_here"
```

**Windows System Environment Variable:**
1. Open System Properties → Environment Variables
2. Add new User variable: `GITHUB_TOKEN` = `your_token_here`

**Option 2: Use MCP Token**

If using Cursor with MCP GitHub integration, the token may be available via MCP configuration.

## Scripts

### `query_ci_errors.py`

Query CI workflow run status without extracting detailed errors.

**Usage:**
```bash
python .github/scripts/query_ci_errors.py \
  --repo owner/repo \
  --token $GITHUB_TOKEN \
  --latest \
  --branch main \
  --jobs \
  --output-json
```

### `report_ci_errors.py`

Extract detailed error information from failed CI jobs.

**Usage:**
```bash
python .github/scripts/report_ci_errors.py \
  --workflow-run-id <run_id> \
  --repo owner/repo \
  --token $GITHUB_TOKEN \
  --output-json
```

## Agent Integration

The Cursor agent automatically uses these scripts after each `git push` to:
1. Check CI status
2. Extract and report errors if CI fails
3. Offer to help fix errors

