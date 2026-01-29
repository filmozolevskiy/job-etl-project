# Deployment Debugging Guide

## Current Status

Deployment workflow is failing. Run ID: 21358586546
Check logs: https://github.com/filmozolevskiy/job-etl-project/actions/runs/21358586546

## Steps to Debug

### 1. Check Workflow Logs

Visit the workflow run URL and check which step failed:
- https://github.com/filmozolevskiy/job-etl-project/actions/runs/21358586546

Look for:
- Red X marks indicating failed steps
- Error messages in the step logs
- Exit codes (non-zero means failure)

### 2. Common Failure Points

#### A. SSH Key Validation
**Step**: "Validate SSH key format"
**Symptoms**: 
- Error about key format
- Missing header/footer
- Wrong line endings

**Fix**: Ensure SSH_PRIVATE_KEY secret:
- Starts with `-----BEGIN ... PRIVATE KEY-----`
- Ends with `-----END ... PRIVATE KEY-----`
- Uses LF line endings (not CRLF)
- No extra spaces

#### B. SSH Agent Setup
**Step**: "Set up SSH"
**Symptoms**:
- "Error loading key"
- "error in libcrypto"

**Fix**: 
- Verify key format (see above)
- Ensure key matches public key on droplet

#### C. SSH Connection
**Step**: "Configure Git and SSH" or "Deploy to production"
**Symptoms**:
- "Permission denied"
- "Connection refused"
- "Host key verification failed"

**Fix**:
- Verify public key is in `~/.ssh/authorized_keys` on droplet
- Test SSH connection: `ssh deploy@134.122.35.239`
- Check droplet firewall settings

#### D. Git Operations
**Step**: "Deploy to production" (git pull/fetch)
**Symptoms**:
- "Permission denied (publickey)"
- "Host key verification failed"
- "Repository not found"

**Fix**:
- Ensure droplet has GitHub in known_hosts (handled by workflow)
- Verify repository URL is correct
- Check if repository is private (may need deploy key)

#### E. Docker Commands
**Step**: "Deploy to production" (docker compose)
**Symptoms**:
- "docker: command not found"
- "Permission denied"
- "Cannot connect to Docker daemon"

**Fix**:
- Ensure Docker is installed on droplet
- Check user permissions (deploy user in docker group)
- Verify docker-compose.yml exists

#### F. Health Check
**Step**: "Verify deployment"
**Symptoms**:
- "Connection refused"
- "Timeout"
- "404 Not Found"

**Fix**:
- Check if application is running: `docker compose ps`
- Verify port 5010 is exposed
- Check application logs: `docker compose logs`

### 3. Manual Testing

Test each component manually:

```bash
# 1. Test SSH connection
ssh deploy@134.122.35.239 "echo 'SSH works'"

# 2. Test git access
ssh deploy@134.122.35.239 "cd ~/staging-10/job-search-project && git fetch origin"

# 3. Test Docker
ssh deploy@134.122.35.239 "cd ~/staging-10 && docker compose ps"

# 4. Test health endpoint
curl http://134.122.35.239:5010/api/health
```

### 4. Check Droplet Status

```bash
# SSH into droplet
ssh deploy@134.122.35.239

# Check staging-10 directory
cd ~/staging-10
ls -la

# Check environment file
cat .env.staging-10

# Check Docker containers
docker compose ps
docker compose logs

# Check if port 5010 is listening
sudo netstat -tlnp | grep 5010
```

### 5. Workflow Improvements

If you identify the issue, we can:
- Add better error handling
- Add more validation steps
- Improve error messages
- Add retry logic

## Next Steps

1. **Check the workflow logs** at the URL above
2. **Identify which step failed** and the error message
3. **Share the error details** so we can fix it
4. **Test manually** if needed to verify the fix

## Quick Fixes

### If SSH key validation fails:
- Update SSH_PRIVATE_KEY secret with properly formatted key

### If SSH connection fails:
- Verify public key is on droplet: `cat ~/.ssh/authorized_keys`
- Test connection: `ssh deploy@134.122.35.239`

### If deployment script fails:
- Check logs on droplet: `cd ~/staging-10 && docker compose logs`
- Verify environment variables: `cat .env.staging-10`

### If health check fails:
- Check if app is running: `docker compose ps`
- Check logs: `docker compose logs campaign_ui`
- Restart if needed: `docker compose restart`
