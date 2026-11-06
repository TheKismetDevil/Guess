param(
    [string]$PythonExe = 'python',
    [switch]$IncludePostgres
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$resolvedPython = (Get-Command $PythonExe -ErrorAction Stop).Source
$previousTestUrl = $env:TEST_DATABASE_URL
$startedTestDatabase = $false

function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $Executable $Arguments"
    }
}

Push-Location $projectRoot
try {
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        Invoke-Checked 'pnpm' @('run', 'test:typecheck')
        Invoke-Checked 'pnpm' @('test')
        Invoke-Checked 'pnpm' @('build')
    }
    finally { Pop-Location }

    Push-Location (Join-Path $projectRoot 'backend')
    try { Invoke-Checked $resolvedPython @('-m', 'pytest', '-m', 'not postgres', '-q') }
    finally { Pop-Location }

    if ($IncludePostgres) {
        $existingTestDatabase = & docker compose -p guess-tests -f compose.test.yml ps --status running --quiet
        if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the test database; start Docker Desktop first.' }
        $startedTestDatabase = -not [bool]$existingTestDatabase
        Invoke-Checked 'docker' @('compose', '-p', 'guess-tests', '-f', 'compose.test.yml', 'up', '-d', '--wait')
        $env:TEST_DATABASE_URL = 'postgresql+asyncpg://guess_test:guess_test_password@localhost:55432/guess_test'
        Push-Location (Join-Path $projectRoot 'backend')
        try { Invoke-Checked $resolvedPython @('-m', 'pytest', '-m', 'postgres', '-q') }
        finally { Pop-Location }
    }
}
finally {
    $env:TEST_DATABASE_URL = $previousTestUrl
    if ($startedTestDatabase) {
        & docker compose -p guess-tests -f compose.test.yml down
    }
    Pop-Location
}
