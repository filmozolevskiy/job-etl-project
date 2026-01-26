# Production Deployment Setup Checklist

Use this checklist to verify all required secrets and configuration are in place.

## ✅ GitHub Secrets Configuration

Configure these secrets in your GitHub repository:
**Settings → Secrets and variables → Actions → New repository secret**

### 1. `DIGITALOCEAN_API_TOKEN` ⚠️ REQUIRED

**Status:** [ ] Not Set / [ ] Set

**How to create:**
1. Go to https://cloud.digitalocean.com/account/api/tokens
2. Click "Generate New Token"
3. Name: `GitHub Actions Deploy`
4. Scope: `Write` (or `Read` for verification only)
5. Copy the token immediately (you won't see it again)

**To add to GitHub:**
- Repository Settings → Secrets and variables → Actions
- New repository secret
- Name: `DIGITALOCEAN_API_TOKEN`
- Value: `<paste your token>`

**Verify it's set:**
- The workflow will show a warning if not set, but will still proceed
- Check workflow logs for: "⚠️ DIGITALOCEAN_API_TOKEN not set"

---

### 2. `SSH_PRIVATE_KEY` ⚠️ REQUIRED

**Status:** [ ] Not Set / [ ] Set

**You have SSH keys in:** `project_documentation/digitalocean_laptop_ssh` and `digitalocean_laptop_ssh.pub`

**Steps to configure:**

1. **Verify the public key is on the droplet:**
   ```bash
   # Check if public key is already on droplet
   ssh deploy@134.122.35.239 "cat ~/.ssh/authorized_keys | grep -f project_documentation/digitalocean_laptop_ssh.pub"
   ```

2. **If not on droplet, add it:**
   ```bash
   # Copy public key to droplet
   ssh-copy-id -i project_documentation/digitalocean_laptop_ssh.pub deploy@134.122.35.239
   
   # Or manually:
   cat project_documentation/digitalocean_laptop_ssh.pub | ssh deploy@134.122.35.239 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
   ```

3. **Add private key to GitHub secrets:**
   - Read the private key: `cat project_documentation/digitalocean_laptop_ssh`
   - Copy the entire contents (including `-----BEGIN` and `-----END` lines)
   - Repository Settings → Secrets and variables → Actions
   - New repository secret
   - Name: `SSH_PRIVATE_KEY`
   - Value: `<paste entire private key>`

**Verify it works:**
```bash
# Test SSH connection
ssh -i project_documentation/digitalocean_laptop_ssh deploy@134.122.35.239 "echo 'SSH connection successful'"
```

---

### 3. `DROPLET_HOST` (Optional)

**Status:** [ ] Not Set (will use default) / [ ] Set

**Default:** `134.122.35.239`

**Only set if:**
- Your droplet has a different IP address
- You want to use a hostname instead of IP

**To set:**
- Repository Settings → Secrets and variables → Actions
- New repository secret
- Name: `DROPLET_HOST`
- Value: `134.122.35.239` (or your droplet IP/hostname)

---

## ✅ Droplet Configuration

### 4. Staging-10 Environment File

**Status:** [ ] Not Set / [ ] Set

**Verify on droplet:**
```bash
ssh deploy@134.122.35.239 "test -f ~/staging-10/.env.staging-10 && echo 'EXISTS' || echo 'MISSING'"
```

**If missing, create it:**
- Follow instructions in `project_documentation/deployment-staging.md`
- Or use `scripts/setup_staging_slot.sh 10 main` on the droplet

---

### 5. Staging-10 Database

**Status:** [ ] Not Set / [ ] Set

**Verify database exists:**
- Check DigitalOcean console: Databases → Your cluster → Databases
- Should see: `job_search_staging_10`

**If missing:**
```bash
# On DigitalOcean console or via doctl
doctl databases db create <CLUSTER_ID> job_search_staging_10
```

---

## ✅ Repository Configuration

### 6. Workflow File

**Status:** ✅ Created
- `.github/workflows/deploy-production.yml` exists

### 7. CI Workflow

**Status:** ✅ Exists
- `.github/workflows/ci.yml` exists and runs on push to main

---

## 🧪 Testing the Setup

### Test 1: Verify Secrets (Manual Check)
1. Go to: `https://github.com/<your-org>/<your-repo>/settings/secrets/actions`
2. Verify you see:
   - `DIGITALOCEAN_API_TOKEN` ✅
   - `SSH_PRIVATE_KEY` ✅
   - `DROPLET_HOST` (optional) ✅

### Test 2: Test SSH Connection
```bash
ssh -i project_documentation/digitalocean_laptop_ssh deploy@134.122.35.239 "whoami"
# Should output: deploy
```

### Test 3: Test DigitalOcean API
```bash
# Replace YOUR_TOKEN with your actual token
curl -X GET \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  "https://api.digitalocean.com/v2/droplets" | jq '.droplets[] | select(.networks.v4[].ip_address == "134.122.35.239")'
```

### Test 4: Manual Workflow Trigger
1. Go to: `https://github.com/<your-org>/<your-repo>/actions/workflows/deploy-production.yml`
2. Click "Run workflow"
3. Select branch: `main`
4. Click "Run workflow"
5. Watch the workflow run and check for errors

---

## 🚀 First Deployment

Once all secrets are configured:

1. **Push to main** (or merge a PR)
2. **CI workflow runs** (lint, test, dbt)
3. **Deploy workflow triggers** automatically after CI passes
4. **Check deployment:**
   - Workflow logs in GitHub Actions
   - Health endpoint: `http://134.122.35.239:5010/api/health`
   - Production URL: `https://staging-10.jobsearch.example.com` (if DNS configured)

---

## ❌ Common Issues

### "SSH connection failed"
- ✅ Verify `SSH_PRIVATE_KEY` secret is set correctly
- ✅ Verify public key is in `~/.ssh/authorized_keys` on droplet
- ✅ Test SSH connection manually

### "DIGITALOCEAN_API_TOKEN not set"
- ⚠️ This is a warning, not an error
- Workflow will still proceed using `DROPLET_HOST` secret
- Set the token for better verification

### "Environment file not found"
- ✅ Run `scripts/setup_staging_slot.sh 10 main` on the droplet
- ✅ Or manually create `~/staging-10/.env.staging-10`

### "CI workflow not found"
- ⚠️ Normal for first few commits
- Workflow will proceed anyway
- For subsequent runs, CI must pass first

---

## 📝 Quick Reference

**GitHub Secrets:**
- `DIGITALOCEAN_API_TOKEN` - DigitalOcean API token
- `SSH_PRIVATE_KEY` - SSH private key for droplet access
- `DROPLET_HOST` - Droplet IP (optional, defaults to 134.122.35.239)

**Droplet Requirements:**
- `~/staging-10/.env.staging-10` - Environment configuration
- `job_search_staging_10` - Database exists
- SSH access for `deploy` user

**Workflow Files:**
- `.github/workflows/deploy-production.yml` - Deployment workflow
- `.github/workflows/ci.yml` - CI workflow
