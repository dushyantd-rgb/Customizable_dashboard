[CmdletBinding()]
param(
    [string]$DatabaseUrl = $env:DATABASE_DIRECT_URL
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    throw "Set DATABASE_DIRECT_URL before applying migrations."
}

$psql = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psql) {
    throw "psql was not found. Install PostgreSQL client tools or run this script in a Supabase CLI environment."
}

$migrationDirectory = Join-Path $PSScriptRoot "migrations"
$migrations = Get-ChildItem -LiteralPath $migrationDirectory -File -Filter "*.sql" | Sort-Object Name

if (-not $migrations) {
    throw "No migration files were found."
}

foreach ($migration in $migrations) {
    Write-Host "Applying $($migration.Name)"
    & $psql.Source $DatabaseUrl --set ON_ERROR_STOP=1 --file $migration.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "Migration failed: $($migration.Name)"
    }
}

Write-Host "Applied $($migrations.Count) migration(s)."
