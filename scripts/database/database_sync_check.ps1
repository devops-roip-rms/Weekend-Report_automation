Set-StrictMode -Version Latest

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# The Python caller will interpret:
#
#   exit 0 = synchronization test PASS
#   exit 1 = synchronization test FAIL
#   exit 2 = technical/configuration/cleanup ERROR
#
# Standard output contains exactly one JSON document.

$Password = ""
$Credential = $null
$SecurePassword = $null

$Site1Nodes = @()
$Site2Nodes = @()
$AllNodes = @()

$RunToken = "{0}_{1}" -f `
    (Get-Date -Format "yyyyMMddHHmmss"), `
    ([guid]::NewGuid().ToString("N").Substring(0, 8))

$DatabasePrefix = "wr_sync_$RunToken"

$Result = [ordered]@{
    schema_version = 1
    status = "ERROR"
    code = "DATABASE_SYNC_SCRIPT_NOT_COMPLETED"
    message = "Database synchronization check did not complete"
    run_id = $RunToken
    sites = @()
    cleanup = "NOT_RUN"
}

$ExitCode = 2
$Phase = "configuration"


function Get-RequiredEnv
{
    [CmdletBinding()]
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
        throw "Required environment variable is missing or unresolved: $Name"
    }

    return $Value.Trim()
}


function Get-RequiredIntEnv
{
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true)]
        [string]
        $Name,

        [int]
        $Minimum = 1,

        [int]
        $Maximum = 65535
    )

    $RawValue = Get-RequiredEnv -Name $Name

    $ParsedValue = 0

    if (-not [int]::TryParse($RawValue, [ref]$ParsedValue))
    {
        throw "Environment variable $Name must be an integer"
    }

    if (
        $ParsedValue -lt $Minimum -or
        $ParsedValue -gt $Maximum
    )
    {
        throw "Environment variable $Name is outside the allowed range"
    }

    return $ParsedValue
}


function Get-SafeErrorMessage
{
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true)]
        [System.Exception]
        $Exception,

        [string]
        $Secret
    )

    $Message = $Exception.Message

    if (-not [string]::IsNullOrEmpty($Secret))
    {
        $Message = $Message.Replace($Secret, "***")
    }

    return $Message
}


function Get-DatabaseNames
{
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true)]
        [psobject]
        $Node
    )

    $Rows = @(
        Invoke-SqlQuery `
            -ConnectionName $Node.ConnectionName `
            -Query "SHOW DATABASES;" `
            -WarningAction SilentlyContinue `
            -ErrorAction Stop
    )

    $Names = @()

    foreach ($Row in $Rows)
    {
        $DatabaseProperty = $Row.PSObject.Properties["Database"]

        if ($null -eq $DatabaseProperty)
        {
            throw "SHOW DATABASES returned an unexpected result structure"
        }

        $Names += [string]$DatabaseProperty.Value
    }

    return $Names
}


function Wait-ForDatabaseState
{
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true)]
        [System.Object[]]
        $Nodes,

        [Parameter(Mandatory = $true)]
        [string[]]
        $DatabaseNames,

        [Parameter(Mandatory = $true)]
        [ValidateSet("present", "absent")]
        [string]
        $ExpectedState,

        [int]
        $MaximumAttempts = 5,

        [int]
        $DelaySeconds = 2
    )

    $ShouldExist = ($ExpectedState -eq "present")

    for ($Attempt = 1; $Attempt -le $MaximumAttempts; $Attempt++)
    {
        $AllNodesMatch = $true

        foreach ($Node in $Nodes)
        {
            $CurrentDatabases = @(
                Get-DatabaseNames -Node $Node
            )

            foreach ($DatabaseName in $DatabaseNames)
            {
                $Exists = $CurrentDatabases -contains $DatabaseName

                if ($Exists -ne $ShouldExist)
                {
                    $AllNodesMatch = $false
                    break
                }
            }

            if (-not $AllNodesMatch)
            {
                break
            }
        }

        if ($AllNodesMatch)
        {
            return $true
        }

        if ($Attempt -lt $MaximumAttempts)
        {
            Start-Sleep -Seconds $DelaySeconds
        }
    }

    return $false
}


function Test-SiteSynchronization
{
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true)]
        [string]
        $SiteName,

        [Parameter(Mandatory = $true)]
        [System.Object[]]
        $Nodes
    )

    $ExpectedDatabases = @(
        $Nodes | ForEach-Object {
            $_.TestDatabase
        }
    )

    #
    # Create one unique database from each node.
    #
    # If the cluster is synchronized correctly, every node in this
    # site should eventually see all three databases.
    #
    foreach ($Node in $Nodes)
    {
        $CreateQuery = "CREATE DATABASE $($Node.TestDatabase);"

        Invoke-SqlQuery `
            -ConnectionName $Node.ConnectionName `
            -Query $CreateQuery `
            -WarningAction SilentlyContinue `
            -ErrorAction Stop |
            Out-Null
    }

    $CreateVisible = Wait-ForDatabaseState `
        -Nodes $Nodes `
        -DatabaseNames $ExpectedDatabases `
        -ExpectedState "present"

    #
    # Always attempt the normal deletion phase.
    #
    # A synchronization failure after CREATE is a reliable FAIL, but
    # we still want to test deletion propagation and leave the site
    # in a clean state.
    #
    foreach ($Node in $Nodes)
    {
        $DropQuery = "DROP DATABASE $($Node.TestDatabase);"

        Invoke-SqlQuery `
            -ConnectionName $Node.ConnectionName `
            -Query $DropQuery `
            -WarningAction SilentlyContinue `
            -ErrorAction Stop |
            Out-Null
    }

    $DropVisible = Wait-ForDatabaseState `
        -Nodes $Nodes `
        -DatabaseNames $ExpectedDatabases `
        -ExpectedState "absent"

    $CreateState = if ($CreateVisible)
    {
        "PASS"
    }
    else
    {
        "FAIL"
    }

    $DropState = if ($DropVisible)
    {
        "PASS"
    }
    else
    {
        "FAIL"
    }

    if ($CreateVisible -and $DropVisible)
    {
        $Status = "PASS"
        $Code = "DATABASE_SITE_SYNC_PASS"
    }
    elseif (-not $CreateVisible -and -not $DropVisible)
    {
        $Status = "FAIL"
        $Code = "DATABASE_CREATE_AND_DROP_NOT_SYNCHRONIZED"
    }
    elseif (-not $CreateVisible)
    {
        $Status = "FAIL"
        $Code = "DATABASE_CREATE_NOT_SYNCHRONIZED"
    }
    else
    {
        $Status = "FAIL"
        $Code = "DATABASE_DROP_NOT_SYNCHRONIZED"
    }

    return [pscustomobject]@{
        name = $SiteName
        status = $Status
        code = $Code
        create_visibility = $CreateState
        drop_visibility = $DropState
        node_count = $Nodes.Count
    }

    #
    # Drop each database from the node on which it was created.
    #
    # The drop must also synchronize to all three nodes.
    #
    foreach ($Node in $Nodes)
    {
        $DropQuery = "DROP DATABASE $($Node.TestDatabase);"

        Invoke-SqlQuery `
            -ConnectionName $Node.ConnectionName `
            -Query $DropQuery `
            -WarningAction SilentlyContinue `
            -ErrorAction Stop |
            Out-Null
    }

    $DropVisible = Wait-ForDatabaseState `
        -Nodes $Nodes `
        -DatabaseNames $ExpectedDatabases `
        -ExpectedState "absent"

    if (-not $DropVisible)
    {
        return [pscustomobject]@{
            name = $SiteName
            status = "FAIL"
            code = "DATABASE_DROP_NOT_SYNCHRONIZED"
            create_visibility = "PASS"
            drop_visibility = "FAIL"
            node_count = $Nodes.Count
        }
    }

    return [pscustomobject]@{
        name = $SiteName
        status = "PASS"
        code = "DATABASE_SITE_SYNC_PASS"
        create_visibility = "PASS"
        drop_visibility = "PASS"
        node_count = $Nodes.Count
    }
}


function Invoke-BestEffortCleanup
{
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true)]
        [System.Object[]]
        $Nodes
    )

    $CleanupErrors = @()

    $ConnectedNodes = @(
        $Nodes |
            Where-Object {
                $_.Connected
            }
    )

    foreach ($Node in $ConnectedNodes)
    {
        #
        # On cleanup, try every generated DB name on every connected
        # node in the same site.
        #
        # This prevents failed synchronization from leaving test
        # databases behind.
        #
        $SiteDatabaseNames = @(
            $Nodes |
                Where-Object {
                    $_.Site -eq $Node.Site
                } |
                ForEach-Object {
                    $_.TestDatabase
                }
        )

        foreach ($DatabaseName in $SiteDatabaseNames)
        {
            try
            {
                $CleanupQuery = "DROP DATABASE IF EXISTS $DatabaseName;"

                Invoke-SqlQuery `
                    -ConnectionName $Node.ConnectionName `
                    -Query $CleanupQuery `
                    -WarningAction SilentlyContinue `
                    -ErrorAction Stop |
                    Out-Null
            }
            catch
            {
                $CleanupErrors += (
                    "cleanup failed on connection {0} for generated database {1}" -f `
                        $Node.ConnectionName,
                        $DatabaseName
                )
            }
        }
    }

    return $CleanupErrors
}


function Close-AllConnections
{
    [CmdletBinding()]
    param (
        [Parameter(Mandatory = $true)]
        [System.Object[]]
        $Nodes
    )

    $CloseErrors = @()

    foreach ($Node in $Nodes)
    {
        if (-not $Node.Connected)
        {
            continue
        }

        try
        {
            Close-SqlConnection `
                -ConnectionName $Node.ConnectionName `
                -ErrorAction Stop |
                Out-Null

            $Node.Connected = $false
        }
        catch
        {
            $CloseErrors += (
                "could not close connection {0}" -f
                    $Node.ConnectionName
            )
        }
    }

    return $CloseErrors
}


try
{
    #
    # Read and verify configuration.
    #
    $Phase = "configuration"

    $PairCount = Get-RequiredIntEnv `
        -Name "DATABASE_PAIR_COUNT" `
        -Minimum 1 `
        -Maximum 100

    if ($PairCount -ne 3)
    {
        throw "DATABASE_PAIR_COUNT must be exactly 3"
    }

    $Username = Get-RequiredEnv -Name "DATABASE_USERNAME"

    $PasswordFile = Get-RequiredEnv `
        -Name "DATABASE_PASSWORD_FILE"

    if (-not (Test-Path -LiteralPath $PasswordFile -PathType Leaf))
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

    #
    # Convert the three configured pairs into two independent
    # three-node site arrays.
    #
    for ($Index = 1; $Index -le $PairCount; $Index++)
    {
        $PairName = Get-RequiredEnv `
            -Name "DATABASE_PAIR_${Index}_NAME"

        $Site1Host = Get-RequiredEnv `
            -Name "DATABASE_PAIR_${Index}_SITE1_HOST"

        $Site2Host = Get-RequiredEnv `
            -Name "DATABASE_PAIR_${Index}_SITE2_HOST"

        $Port = Get-RequiredIntEnv `
            -Name "DATABASE_PAIR_${Index}_PORT"

        $Site1Node = [pscustomobject]@{
            Site = "site1"
            PairName = $PairName
            Index = $Index
            Host = $Site1Host
            Port = $Port
            ConnectionName = "wr_site1_$Index"
            TestDatabase = "${DatabasePrefix}_s1_$Index"
            Connected = $false
        }

        $Site2Node = [pscustomobject]@{
            Site = "site2"
            PairName = $PairName
            Index = $Index
            Host = $Site2Host
            Port = $Port
            ConnectionName = "wr_site2_$Index"
            TestDatabase = "${DatabasePrefix}_s2_$Index"
            Connected = $false
        }

        $Site1Nodes += $Site1Node
        $Site2Nodes += $Site2Node
    }

    $AllNodes = @(
        $Site1Nodes
        $Site2Nodes
    )

    #
    # SimplySql provides Open-MySqlConnection and Invoke-SqlQuery.
    #
    $Phase = "module_import"

    Import-Module SimplySql `
        -ErrorAction Stop

    #
    # Open all six database connections.
    #
    $Phase = "database_connection"

    foreach ($Node in $AllNodes)
    {
        Open-MySqlConnection `
            -ConnectionName $Node.ConnectionName `
            -Credential $Credential `
            -Server $Node.Host `
            -Port $Node.Port `
            -ErrorAction Stop |
            Out-Null

        $Node.Connected = $true
    }

    #
    # Run the synchronization test independently at both sites.
    #
    $Phase = "synchronization_test"

    $Site1Result = Test-SiteSynchronization `
        -SiteName "site1" `
        -Nodes $Site1Nodes

    $Site2Result = Test-SiteSynchronization `
        -SiteName "site2" `
        -Nodes $Site2Nodes

    $Result["sites"] = @(
        $Site1Result
        $Site2Result
    )

    if (
        $Site1Result.status -eq "PASS" -and
        $Site2Result.status -eq "PASS"
    )
    {
        $Result["status"] = "PASS"
        $Result["code"] = "DATABASE_SYNC_PASS"
        $Result["message"] = (
            "Database synchronization passed for both sites"
        )

        $ExitCode = 0
    }
    else
    {
        $Result["status"] = "FAIL"
        $Result["code"] = "DATABASE_SYNC_FAIL"
        $Result["message"] = (
            "Database synchronization failed on one or more sites"
        )

        $ExitCode = 1
    }
}
catch
{
    $SafeMessage = Get-SafeErrorMessage `
        -Exception $_.Exception `
        -Secret $Password

    $Result["status"] = "ERROR"
    $Result["code"] = "DATABASE_SYNC_SCRIPT_ERROR"
    $Result["message"] = (
        "Database synchronization check failed during {0}: {1}" -f
            $Phase,
            $SafeMessage
    )

    $ExitCode = 2
}
finally
{
    #
    # Cleanup is mandatory.
    #
    # Even when synchronization fails, try every temporary database
    # against every connected node in its site.
    #
    $ConnectedBeforeCleanup = @(
        $AllNodes |
            Where-Object {
                $_.Connected
            }
    )

    if ($ConnectedBeforeCleanup.Count -gt 0)
    {
        $CleanupErrors = @(
            Invoke-BestEffortCleanup -Nodes $AllNodes
        )

        $CloseErrors = @(
            Close-AllConnections -Nodes $AllNodes
        )

        $CleanupErrors += $CloseErrors

        if ($CleanupErrors.Count -gt 0)
        {
            $Result["cleanup"] = "ERROR"
            $Result["cleanup_errors"] = $CleanupErrors

            $Result["status"] = "ERROR"
            $Result["code"] = "DATABASE_SYNC_CLEANUP_FAILED"
            $Result["message"] = (
                "Database synchronization check could not prove complete cleanup"
            )

            $ExitCode = 2
        }
        else
        {
            $Result["cleanup"] = "PASS"
        }
    }

    #
    # Remove credential material from variables before finishing.
    #
    $Password = ""
    $Credential = $null
    $SecurePassword = $null
}


[Console]::Out.WriteLine(
    ($Result | ConvertTo-Json -Depth 8 -Compress)
)

exit $ExitCode