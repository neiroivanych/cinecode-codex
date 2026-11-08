param([Parameter(Mandatory=$true)][string]$Setup)

. $Setup
$script:fixtureLog = [IO.Path]::GetTempFileName()

function New-TemporaryFile { [PSCustomObject]@{ FullName = $script:fixtureLog } }
function Find-CineCodePython {
    $script:probes++
    if ($script:probes -ge $script:readyAfter) { 'C:\Fixture with spaces\python.exe' }
}
function Get-Command {
    if ($script:managerAvailable) { [PSCustomObject]@{ Source = 'Invoke-MockWinGet' } }
}
function Invoke-MockWinGet {
    $script:packageArguments = $args
    $global:LASTEXITCODE = $script:managerExit
}

function Expect-Error($Message, $Run) {
    try { & $Run; throw 'Expected failure' }
    catch { if ($_.Exception.Message -notlike $Message) { throw } }
}

try {
    $script:probes = 0
    $script:readyAfter = 1
    $script:managerAvailable = $false
    if ((Get-CineCodePython) -notlike '*python.exe' -or $script:probes -ne 1) { throw 'Valid Python was not reused' }

    $script:probes = 0
    $script:readyAfter = 2
    $script:managerAvailable = $true
    $script:managerExit = 0
    if ((Get-CineCodePython) -notlike '*python.exe' -or $script:probes -ne 2 -or
            $script:packageArguments -notcontains 'Python.Python.3.13' -or $script:packageArguments -notcontains '--exact') {
        throw 'Missing Python did not use the reviewed package then re-probe'
    }

    $script:probes = 0
    $script:readyAfter = 99
    Expect-Error 'Python could not be verified*' { Get-CineCodePython }
    $script:managerExit = 1
    Expect-Error 'Python could not be installed*' { Get-CineCodePython }
    $script:managerAvailable = $false
    Expect-Error 'Windows App Installer*' { Get-CineCodePython }
    Expect-Error 'Existing-components*' { Get-CineCodePython -ExistingOnly }
    Write-Output 'Windows native bootstrap: 6 mocked scenarios passed'
} finally {
    Remove-Item -LiteralPath $script:fixtureLog
}
