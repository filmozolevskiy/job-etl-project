# Fix: SSH Connection Timed Out (GitHub Actions → Droplet)

## Problem

```
ssh: connect to host 134.122.35.239 port 22: Connection timed out
```

GitHub Actions runners cannot reach your droplet on port 22.

**Checked via DigitalOcean MCP:** The **DigitalOcean Cloud Firewall** (`staging-firewall`) already allows TCP 22 from `0.0.0.0/0`. The block is almost certainly **UFW** on the droplet (host-level firewall). UFW cannot be changed via DigitalOcean MCP; use recovery console or SSH.

## Solution

Fix **UFW on the droplet** via **recovery console** (or SSH if you have access). DigitalOcean Cloud Firewall is already allowing SSH.

---

## Option A: Allow SSH from anywhere (quickest)

Use this if you're okay with SSH being reachable from any IP. Access is still protected by key-only auth and fail2ban.

### Via recovery console

1. Log in as `root` (or `deploy` with sudo).
2. Check current rules:
   ```bash
   sudo ufw status numbered
   ```
3. Ensure SSH is allowed from anywhere:
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw reload
   sudo ufw status
   ```
4. **DigitalOcean Cloud Firewall** already allows SSH from `0.0.0.0/0` (verified via MCP). No change needed there.

---

## Option B: Allow SSH only from GitHub Actions IPs (more secure)

GitHub publishes Actions IP ranges at https://api.github.com/meta (`actions` key). These change over time.

### 1. Fetch current ranges

```bash
curl -s https://api.github.com/meta | jq -r '.actions[]'
```

### 2. Add UFW rules on the droplet

From recovery console (or SSH):

```bash
# Example – replace with actual CIDRs from the API
sudo ufw allow from 20.0.0.0/8 to any port 22 proto tcp
# ... add each CIDR from .actions[]
sudo ufw reload
```

### 3. DigitalOcean Cloud Firewall

If you use a DO firewall, add one inbound rule per GitHub Actions CIDR:

- **Type:** Custom
- **Protocol:** TCP
- **Port:** 22
- **Sources:** One CIDR per rule (e.g. `20.0.0.0/8`)

You’ll need to update these when GitHub changes their ranges.

---

## Verify

1. Re-run the deployment workflow:
   - https://github.com/filmozolevskiy/job-etl-project/actions/workflows/deploy-production.yml → **Run workflow**
2. The "Deploy to production (staging-10)" step should get past the SSH connection.

---

## Summary

| Layer | Status | Where to change |
|-------|--------|------------------|
| **DigitalOcean Firewall** | OK — SSH from `0.0.0.0/0` | No change needed (verified via MCP) |
| **UFW** (on droplet) | Likely blocking | Recovery console: `ufw allow 22/tcp` then `ufw reload` |

After fixing UFW, re-run the deployment workflow.
