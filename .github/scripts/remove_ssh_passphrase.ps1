# PowerShell script to remove passphrase from SSH key
# Usage: .\remove_ssh_passphrase.ps1 [key_file]

param(
    [string]$KeyFile = "$env:USERPROFILE\.ssh\digitalocean_laptop_ssh"
)

if (-not (Test-Path $KeyFile)) {
    Write-Host "Error: SSH key file not found: $KeyFile" -ForegroundColor Red
    exit 1
}

Write-Host "=== Removing passphrase from SSH key ===" -ForegroundColor Cyan
Write-Host "Key file: $KeyFile"
Write-Host ""
Write-Host "This will prompt you for the current passphrase."
Write-Host "Then press Enter twice (leave new passphrase empty)."
Write-Host ""

# Create backup
$BackupFile = "${KeyFile}.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
Copy-Item $KeyFile $BackupFile
Write-Host "Backup created: $BackupFile" -ForegroundColor Green
Write-Host ""

# Remove passphrase using ssh-keygen
Write-Host "Running: ssh-keygen -p -f $KeyFile" -ForegroundColor Yellow
ssh-keygen -p -f $KeyFile

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=== Passphrase removed successfully ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "1. Get the private key: Get-Content $KeyFile"
    Write-Host "2. Update GitHub secret SSH_PRIVATE_KEY with the key content"
    Write-Host "3. Ensure the public key is on the droplet:"
    Write-Host "   ssh-copy-id -i ${KeyFile}.pub deploy@134.122.35.239"
    Write-Host ""
    Write-Host "Or if the public key is already on the droplet, you're done!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Error: Failed to remove passphrase" -ForegroundColor Red
    Write-Host "Restoring from backup..." -ForegroundColor Yellow
    Copy-Item $BackupFile $KeyFile -Force
    exit 1
}
