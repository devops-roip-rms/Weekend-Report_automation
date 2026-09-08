Set-StrictMode -Version Latest

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Get-RequiredEnv
{
    param (
        [Parameter(Mandatory = $true)]
        [string]
        $Name
    )

    $Value = [Environment]::GetEnvironmentVariable($Name)

    if (
        [string]::IsNullOrWhiteSpace($Value) -or
        $Value.Trim() -eq "<TBD>"
    )
    {
        throw "Required environment variable is missing: $Name"
    }

    return $Value.Trim()
}


function Get-Port
{
    param (
        [Parameter(Mandatory = $true)]
        [string]
        $Name
    )

    $Raw = Get-RequiredEnv -Name $Name
    $Port = 0

    if (-not [int]::TryParse($Raw, [ref]$Port))
    {
        throw "$Name must be an integer"
    }

    if ($Port -lt 1 -or $Port -gt 65535)
    {
        throw "$Name is outside the valid TCP port range"
    }

    return $Port
}


$Password = ""
$Results = @()
$OverallPass = $true

try
{
    $PairCountRaw = Get-RequiredEnv `
        -Name "DATABASE_PAIR_COUNT"

    $PairCount = 0

    if (
        -not [int]::TryParse(
            $PairCountRaw,
            [ref]$PairCount
        )
    )
    {
        throw "DATABASE_PAIR_COUNT must be an integer"
    }

    if ($PairCount -ne 3)
    {
        throw "DATABASE_PAIR_COUNT must be exactly 3"
    }

    $Username = Get-RequiredEnv `
        -Name "DATABASE_USERNAME"

    $PasswordFile = Get-RequiredEnv `
        -Name "DATABASE_PASSWORD_FILE"

    if (
        -not (
            Test-Path `
                -LiteralPath $PasswordFile `
                -PathType Leaf
        )
    )
    {
        throw "Database password file does not exist"
    }

    $Password = (
        Get-Content `
            -LiteralPath $PasswordFile `
            -Raw `
            -ErrorAction Stop
    ).TrimEnd([char[]]"`r`n")

    if ([string]::IsNullOrEmpty($Password))
    {
        throw "Database password file is empty"
    }

    $SecurePassword = ConvertTo-SecureString `
        -String $Password `
        -AsPlainText `
        -Force

    $Credential = New-Object `
        System.Management.Automation.PSCredential (
            $Username,
            $SecurePassword
        )

    Import-Module SimplySql `
        -ErrorAction Stop

    for ($Index = 1; $Index -le $PairCount; $Index++)
    {
        $PairName = Get-RequiredEnv `
            -Name "DATABASE_PAIR_${Index}_NAME"

        $Port = Get-Port `
            -Name "DATABASE_PAIR_${Index}_PORT"

        $Targets = @(
            [pscustomobject]@{
                Site = "site1"
                Host = Get-RequiredEnv `
                    -Name "DATABASE_PAIR_${Index}_SITE1_HOST"
            }

            [pscustomobject]@{
                Site = "site2"
                Host = Get-RequiredEnv `
                    -Name "DATABASE_PAIR_${Index}_SITE2_HOST"
            }
        )

        foreach ($Target in $Targets)
        {
            $ConnectionName = (
                "wr_connectivity_{0}_{1}" -f
                    $Target.Site,
                    $Index
            )

            $Connected = $false

            try
            {
                Open-MySqlConnection `
                    -ConnectionName $ConnectionName `
                    -Credential $Credential `
                    -Server $Target.Host `
                    -Port $Port `
                    -ErrorAction Stop |
                    Out-Null

                $Connected = $true

                $Rows = @(
                    Invoke-SqlQuery `
                        -ConnectionName $ConnectionName `
                        -Query "SELECT 1 AS connection_test;" `
                        -ErrorAction Stop
                )

                if ($Rows.Count -lt 1)
                {
                    throw "SELECT 1 returned no result"
                }

                $Property = (
                    $Rows[0].PSObject.Properties[
                        "connection_test"
                    ]
                )

                if (
                    $null -eq $Property -or
                    [int]$Property.Value -ne 1
                )
                {
                    throw "SELECT 1 returned an unexpected result"
                }

                $Results += [pscustomobject]@{
                    pair = $PairName
                    site = $Target.Site
                    host = $Target.Host
                    port = $Port
                    status = "PASS"
                }
            }
            catch
            {
                $OverallPass = $false

                $SafeMessage = $_.Exception.Message

                if (
                    -not [string]::IsNullOrEmpty($Password)
                )
                {
                    $SafeMessage = $SafeMessage.Replace(
                        $Password,
                        "***"
                    )
                }

                $Results += [pscustomobject]@{
                    pair = $PairName
                    site = $Target.Site
                    host = $Target.Host
                    port = $Port
                    status = "ERROR"
                    error = $SafeMessage
                }
            }
            finally
            {
                if ($Connected)
                {
                    try
                    {
                        Close-SqlConnection `
                            -ConnectionName $ConnectionName `
                            -ErrorAction Stop |
                            Out-Null
                    }
                    catch
                    {
                        # Process termination will also close
                        # this read-only connection.
                    }
                }
            }
        }
    }
}
catch
{
    $OverallPass = $false

    $SafeMessage = $_.Exception.Message

    if (-not [string]::IsNullOrEmpty($Password))
    {
        $SafeMessage = $SafeMessage.Replace(
            $Password,
            "***"
        )
    }

    $Results += [pscustomobject]@{
        status = "ERROR"
        error = $SafeMessage
    }
}


if ($OverallPass)
{
    $Status = "PASS"
    $Code = "DATABASE_CONNECTIVITY_PASS"
    $ExitCode = 0
}
else
{
    $Status = "ERROR"
    $Code = "DATABASE_CONNECTIVITY_ERROR"
    $ExitCode = 2
}


$Output = [ordered]@{
    status = $Status
    code = $Code
    endpoints = $Results
}

[Console]::Out.WriteLine(
    ($Output | ConvertTo-Json -Depth 6)
)

$Password = ""
$Credential = $null
$SecurePassword = $null

exit $ExitCode