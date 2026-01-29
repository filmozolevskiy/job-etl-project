# SSH Key Passphrase Fix

## Problem

The SSH key in GitHub secrets has a passphrase, and the workflow is failing with:
```
Enter passphrase for (stdin):
```

GitHub Actions cannot provide passphrases interactively, so the SSH agent setup fails.

## Solution

You need to use an SSH key **without a passphrase** for CI/CD deployments.

### Option 1: Generate New Key Pair (Recommended)

1. **Generate a new SSH key without a passphrase**:
   ```bash
   # Generate new key (press Enter when asked for passphrase - leave it empty)
   ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy -N ""
   
   # Or if ed25519 is not available:
   ssh-keygen -t rsa -b 4096 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy -N ""
   ```

2. **Copy the public key to the droplet**:
   ```bash
   # Option A: Using ssh-copy-id
   ssh-copy-id -i ~/.ssh/github_actions_deploy.pub deploy@134.122.35.239
   
   # Option B: Manual copy
   cat ~/.ssh/github_actions_deploy.pub | ssh deploy@134.122.35.239 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
   
   # Option C: If you have existing SSH access
   ssh deploy@134.122.35.239
   # Then on the droplet:
   echo "YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

3. **Get the private key**:
   ```bash
   cat ~/.ssh/github_actions_deploy
   ```

4. **Update GitHub Secret**:
   - Go to: https://github.com/filmozolevskiy/job-etl-project/settings/secrets/actions
   - Edit `SSH_PRIVATE_KEY`
   - Paste the entire private key (including `-----BEGIN...` and `-----END...` lines)
   - Save

5. **Test the connection**:
   ```bash
   ssh -i ~/.ssh/github_actions_deploy deploy@134.122.35.239 "echo 'Connection successful'"
   ```

### Option 2: Remove Passphrase from Existing Key

If you want to use your existing key:

1. **Remove the passphrase**:
   ```bash
   # Create a backup first
   cp ~/.ssh/id_rsa ~/.ssh/id_rsa.backup
   
   # Remove passphrase (will prompt for current passphrase)
   ssh-keygen -p -f ~/.ssh/id_rsa
   # When prompted, enter the current passphrase, then press Enter twice for new passphrase (empty)
   ```

2. **Update GitHub Secret** with the new key (without passphrase)

3. **Test the connection**:
   ```bash
   ssh deploy@134.122.35.239 "echo 'Connection successful'"
   ```

### Option 3: Use SSH Key with Passphrase (Not Recommended)

If you must use a key with a passphrase, you would need to:
- Store the passphrase in another GitHub secret
- Use a custom action that can handle passphrases
- This is more complex and less secure

**Not recommended** - it's better to use a dedicated deployment key without a passphrase.

## Security Best Practices

1. **Use a dedicated key for CI/CD**:
   - Don't use your personal SSH key
   - Generate a key specifically for deployments
   - Name it clearly (e.g., `github_actions_deploy`)

2. **Restrict key permissions**:
   - The key should only have access to what's needed for deployment
   - Consider using a separate user account on the droplet for deployments

3. **Rotate keys regularly**:
   - Update keys periodically
   - Remove old keys from the droplet when rotating

4. **Monitor key usage**:
   - Check droplet logs for SSH access
   - Use GitHub Actions audit logs to track deployments

## Verification

After updating the secret:

1. **Test locally** (if you have the key):
   ```bash
   ssh -i ~/.ssh/github_actions_deploy deploy@134.122.35.239 "echo 'SSH works'"
   ```

2. **Re-run the deployment workflow**:
   - Go to: https://github.com/filmozolevskiy/job-etl-project/actions/workflows/deploy-production.yml
   - Click "Re-run failed jobs" or trigger a new run

3. **Monitor the workflow**:
   - The "Set up SSH" step should now succeed
   - No more passphrase prompts

## Next Steps

1. Generate new key pair without passphrase
2. Add public key to droplet
3. Update GitHub secret with private key
4. Re-run deployment workflow

The workflow should now proceed past the SSH setup step!
