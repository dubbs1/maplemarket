# Sends the Maple market to its DigitalOcean droplet and installs or updates it there.
# Run from this folder:
#   powershell -ExecutionPolicy Bypass -File deploy-maple.ps1            install / update (safe to repeat)
#   powershell -ExecutionPolicy Bypass -File deploy-maple.ps1 -Check     only look at the server and report
#   powershell -ExecutionPolicy Bypass -File deploy-maple.ps1 -Remove    take the Maple site down (keeps its data)
# The first time it asks for the droplet's login (like root@203.0.113.7) and remembers it in deploy-target.json.
# Options: -Server root@203.0.113.7   -Domain maple.vendormarket.app   -Email you@example.com
param([string]$Server = "", [string]$Domain = "", [string]$Email = "", [switch]$Check, [switch]$Remove)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$files = @("server.py", "manage.py", "market.html", "icon.ico", "install.sh")
foreach ($f in $files) { if (-not (Test-Path $f)) { throw "Missing $f - extract the whole maple-server zip first." } }

# Where to send it: what was typed, else what was used last time, else ask.
$saved = @{}
if (Test-Path deploy-target.json) {
  (Get-Content deploy-target.json -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $saved[$_.Name] = $_.Value }
}
if (-not $Server) { $Server = $saved["Server"] }
if (-not $Server) {
  Write-Host "Which droplet? Type its login: root@ then the droplet's IP address from the DigitalOcean page." -ForegroundColor Cyan
  $Server = (Read-Host "For example root@203.0.113.7").Trim()
}
if (-not $Domain) { $Domain = $saved["Domain"] }
if (-not $Domain) { $Domain = "maple.vendormarket.app" }
if (-not $Email) { $Email = $saved["Email"] }
if (-not $Email) { $Email = "" }
if ($Server -notmatch '^[A-Za-z0-9._-]+@[A-Za-z0-9.:-]+$') { throw "'$Server' doesn't look like root@203.0.113.7" }
if ($Domain -notmatch '^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$') { throw "'$Domain' isn't a web address like maple.vendormarket.app" }
if ($Email -and $Email -notmatch '^[^@\s''"]+@[^@\s''"]+\.[^@\s''"]+$') { throw "'$Email' isn't an email address" }
@{ Server = $Server; Domain = $Domain; Email = $Email } | ConvertTo-Json | Set-Content deploy-target.json
Write-Host "Droplet: $Server    Address: https://$Domain" -ForegroundColor Cyan

# install.sh must have Linux line endings
$shPath = Join-Path $PSScriptRoot "install.sh"
[IO.File]::WriteAllText($shPath, ([IO.File]::ReadAllText($shPath) -replace "`r`n", "`n"))

Write-Host "Packing..." -ForegroundColor Cyan
if (Test-Path maple-upload.tar.gz) { Remove-Item maple-upload.tar.gz }
tar -czf maple-upload.tar.gz $files
if ($LASTEXITCODE -ne 0) { throw "Packing failed." }

Write-Host "Sending to $Server (the first time it asks 'Are you sure...?': type yes and press Enter)..." -ForegroundColor Cyan
scp maple-upload.tar.gz "${Server}:/root/maple-upload.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "Sending failed. Can you log in with: ssh $Server ?" }

$mode = if ($Remove) { "--remove" } elseif ($Check) { "--check" } else { "" }
Write-Host "Installing on the server..." -ForegroundColor Cyan
ssh $Server "rm -rf /root/maple-upload && mkdir -p /root/maple-upload && tar -xzf /root/maple-upload.tar.gz -C /root/maple-upload && MAPLE_DOMAIN='$Domain' MAPLE_EMAIL='$Email' bash /root/maple-upload/install.sh $mode"
if ($LASTEXITCODE -ne 0) { throw "The install stopped. Copy this window and send it to Claude." }
Remove-Item maple-upload.tar.gz
Write-Host "`nAll done." -ForegroundColor Green
