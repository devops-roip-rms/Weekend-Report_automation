$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $ProjectRoot

$EnvPath = "deploy\docker\env\rabbitmq.env"
if (-not (Test-Path $EnvPath)) { throw "$EnvPath does not exist." }

function Set-EnvValue {
    param([string]$Path,[string]$Name,[string]$Value)
    $lines = @(Get-Content $Path)
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match ('^' + [regex]::Escape($Name) + '=')) {
            $lines[$i] = "$Name=$Value"
            $found = $true
        }
    }
    if (-not $found) { throw "$Name was not found in $Path" }
    [System.IO.File]::WriteAllLines((Resolve-Path $Path), $lines, (New-Object System.Text.UTF8Encoding($false)))
}

function Configure-RabbitMQSite {
    param([int]$SiteNumber)

    Write-Host ""
    Write-Host "RabbitMQ Site $SiteNumber"
    Write-Host "--------------------"

    $Url = (Read-Host "Management base URL (without /api)").Trim().TrimEnd('/')
    if ([string]::IsNullOrWhiteSpace($Url)) { throw "URL cannot be empty." }
    if ($Url -match '/api$') { throw "Use the RabbitMQ Management base URL WITHOUT /api." }
    if ($Url -notmatch '^https?://') { throw "URL must start with http:// or https://." }

    $Username = (Read-Host "Username").Trim()
    if ([string]::IsNullOrWhiteSpace($Username)) { throw "Username cannot be empty." }

    $SecurePassword = Read-Host "Password" -AsSecureString
    $BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)

    try {
        $Password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR)
        if ([string]::IsNullOrWhiteSpace($Password)) { throw "Password cannot be empty." }

        $Pair = "${Username}:${Password}"
        $Bytes = [System.Text.Encoding]::UTF8.GetBytes($Pair)
        $BasicAuth = [Convert]::ToBase64String($Bytes)
        $Headers = @{ Authorization = "Basic $BasicAuth"; Accept = "application/json" }

        Write-Host "Testing $Url/api/queues ..."
        Invoke-RestMethod -Uri "$Url/api/queues" -Headers $Headers -Method Get | Out-Null
        Write-Host "PASS: queues API"

        Write-Host "Testing $Url/api/nodes ..."
        Invoke-RestMethod -Uri "$Url/api/nodes" -Headers $Headers -Method Get | Out-Null
        Write-Host "PASS: nodes API"

        $Prefix = "RABBITMQ_SITE$SiteNumber"
        Set-EnvValue $EnvPath "${Prefix}_URL" $Url
        Set-EnvValue $EnvPath "${Prefix}_USER" $Username
        Set-EnvValue $EnvPath "${Prefix}_PASSWORD" $Password
        Write-Host "RabbitMQ Site $SiteNumber configured successfully."
    }
    finally {
        if ($BSTR -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR) }
        $Password = $null
        $Pair = $null
        $BasicAuth = $null
    }
}

Configure-RabbitMQSite -SiteNumber 1
Configure-RabbitMQSite -SiteNumber 2

Write-Host ""
Write-Host "RabbitMQ configuration completed. Credentials were not displayed."
