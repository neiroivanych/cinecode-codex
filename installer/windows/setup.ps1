param([string]$Destination, [switch]$ExistingOnly)

$ErrorActionPreference = 'Stop'

function Find-CineCodePython {
    $candidates = @(Get-Command python.exe, python3.exe -CommandType Application -All -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty Source)
    foreach ($root in @("$env:LOCALAPPDATA\Programs\Python", $env:ProgramFiles)) {
        $candidates += @(Get-ChildItem -LiteralPath $root -Directory -Filter 'Python3*' -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'python.exe' })
    }
    $py = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue |
        Where-Object Source -NotLike '*\Microsoft\WindowsApps\*' | Select-Object -First 1
    if ($py) {
        $registered = & $py.Source -0p 2>$null
        if ($LASTEXITCODE -eq 0) {
            foreach ($line in $registered) {
                if ($line -match '^\s*-\S+\s+(?:\*\s+)?(.+\.exe)\s*$') { $candidates += $Matches[1] }
            }
        }
    }
    foreach ($candidate in $candidates) {
        if (-not $candidate -or $candidate -like '*\Microsoft\WindowsApps\*' -or
                -not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        & $candidate -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { return $candidate }
    }
}

function Get-CineCodePython {
    param([switch]$ExistingOnly)
    $interpreter = Find-CineCodePython
    if ($interpreter) { return $interpreter }
    if ($ExistingOnly) { throw 'Existing-components check could not verify Python 3.9 or later.' }
    $winget = Get-Command winget.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $winget) {
        throw 'Windows App Installer / WinGet is required. See https://learn.microsoft.com/windows/package-manager/winget/'
    }
    Write-Host 'Preparing Python via WinGet...'
    $log = New-TemporaryFile
    & $winget.Source install --id Python.Python.3.13 --exact --source winget --silent --scope user `
        --accept-source-agreements --accept-package-agreements --disable-interactivity *> $log.FullName
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { throw "Python could not be installed. Setup log: $($log.FullName)" }
    $interpreter = Find-CineCodePython
    if (-not $interpreter) { throw "Python could not be verified after WinGet setup. Setup log: $($log.FullName)" }
    return $interpreter
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        foreach ($required in 'manifest.json', 'install.py', 'payload/cinecode-codex/VERSION') {
            if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $required) -PathType Leaf)) {
                throw 'Extract the whole CineCode ZIP into one folder and run the launcher again.'
            }
        }
        $env:PYTHONUTF8 = '1'
        [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
        $interpreter = Get-CineCodePython -ExistingOnly:$ExistingOnly
        $arguments = @('-B', (Join-Path $PSScriptRoot 'install.py'))
        if ($Destination) { $arguments += @('--destination', $Destination) }
        if ($ExistingOnly) { $arguments += '--existing-only' }
        & $interpreter @arguments
        exit $LASTEXITCODE
    } catch {
        [Console]::Error.WriteLine("CineCode setup could not finish.`n$($_.Exception.Message)")
        exit 2
    }
}
