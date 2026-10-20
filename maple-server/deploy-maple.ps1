# Sends the Maple market to your DigitalOcean server and installs or updates it.
# Run from this folder:   powershell -ExecutionPolicy Bypass -File deploy-maple.ps1
# Add -Check to only look at the server and report (changes nothing):
#                          powershell -ExecutionPolicy Bypass -File deploy-maple.ps1 -Check
param([string]$Server = "root@vendormarket.app", [switch]$Check)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$files = @("server.py", "manage.py", "market.html", "icon.ico", "install.sh")
foreach ($f in $files) { if (-not (Test-Path $f)) { throw "Missing $f - extract the whole maple-server zip first." } }

# install.sh must have Linux line endings
$sh = [IO.File]::ReadAllText("$PSScriptRoot\install.sh") -replace "`r`n", "`n"
[IO.File]::WriteAllText("$PSScriptRoot\install.sh", $sh)

Write-Host "Packing..." -ForegroundColor Cyan
if (Test-Path maple-upload.tar.gz) { Remove-Item maple-upload.tar.gz }
tar -czf maple-upload.tar.gz $files
if ($LASTEXITCODE -ne 0) { throw "Packing failed." }

Write-Host "Sending to $Server (it may ask for your password or key passphrase)..." -ForegroundColor Cyan
scp maple-upload.tar.gz "${Server}:/root/maple-upload.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "Sending failed. Can you log in with: ssh $Server ?" }

$mode = if ($Check) { "--check" } else { "" }
Write-Host "Installing on the server..." -ForegroundColor Cyan
ssh $Server "rm -rf /root/maple-upload && mkdir -p /root/maple-upload && tar -xzf /root/maple-upload.tar.gz -C /root/maple-upload && bash /root/maple-upload/install.sh $mode"
if ($LASTEXITCODE -ne 0) { throw "The install stopped. Copy this window and send it to Claude." }
Remove-Item maple-upload.tar.gz
Write-Host "`nAll done." -ForegroundColor Green
