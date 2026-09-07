$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

$EnvPath = "deploy\docker\env\splunk.env"
if (-not (Test-Path $EnvPath)) { throw "$EnvPath does not exist." }

Write-Host ""
Write-Host "Configure Splunk dashboards"
Write-Host "---------------------------"

do {
    $raw = Read-Host "How many Splunk dashboards should be reviewed?"
    $DashboardCount = 0
    $valid = [int]::TryParse($raw, [ref]$DashboardCount)
    if (-not $valid -or $DashboardCount -lt 1) { Write-Host "Enter a positive integer." }
} until ($valid -and $DashboardCount -ge 1)

$Dashboards = @()
$UsedIds = @{}

for ($i = 1; $i -le $DashboardCount; $i++) {
    Write-Host ""
    Write-Host "Dashboard $i"
    Write-Host "-----------"

    do {
        $Id = (Read-Host "Dashboard ID (short unique name)").Trim()
        if ([string]::IsNullOrWhiteSpace($Id)) { Write-Host "Dashboard ID cannot be empty."; continue }
        if ($UsedIds.ContainsKey($Id)) { Write-Host "Dashboard ID '$Id' is already used."; $Id = ""; continue }
    } until (-not [string]::IsNullOrWhiteSpace($Id))
    $UsedIds[$Id] = $true

    do { $DisplayName = (Read-Host "Display name").Trim() } until (-not [string]::IsNullOrWhiteSpace($DisplayName))

    do {
        $Url = (Read-Host "Full Splunk dashboard URL").Trim()
        if ($Url -notmatch '^https?://') { Write-Host "URL must start with http:// or https://"; $Url = "" }
    } until (-not [string]::IsNullOrWhiteSpace($Url))

    $Dashboards += [PSCustomObject]@{ Id=$Id; DisplayName=$DisplayName; Url=$Url }
}

$Lines = @("# Splunk dashboard review targets.", "", "SPLUNK_DASHBOARD_COUNT=$DashboardCount", "")
for ($i = 0; $i -lt $Dashboards.Count; $i++) {
    $n = $i + 1
    $d = $Dashboards[$i]
    $Lines += "SPLUNK_DASHBOARD_${n}_ID=$($d.Id)"
    $Lines += "SPLUNK_DASHBOARD_${n}_DISPLAY_NAME=$($d.DisplayName)"
    $Lines += "SPLUNK_DASHBOARD_${n}_URL=$($d.Url)"
    $Lines += ""
}

[System.IO.File]::WriteAllLines((Resolve-Path $EnvPath), $Lines, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ""
Write-Host "Splunk configuration completed. $DashboardCount dashboard(s) written."
