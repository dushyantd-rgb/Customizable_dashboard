[CmdletBinding()]
param(
    [string]$DatabaseUrl = $env:DATABASE_DIRECT_URL,
    [switch]$ApplyDatabase
)

$ErrorActionPreference = "Stop"

$migrationDirectory = Join-Path $PSScriptRoot "migrations"
$migrations = @(Get-ChildItem -LiteralPath $migrationDirectory -File -Filter "*.sql" | Sort-Object Name)

if (-not $migrations) {
    throw "No migration files were found."
}

$expectedTables = @(
    "clients",
    "client_knowledge",
    "client_kpis",
    "integration_connections",
    "google_sheet_configs",
    "field_mappings",
    "status_mappings",
    "sync_runs",
    "raw_sheet_rows",
    "lead_records",
    "lead_matches",
    "metric_snapshots",
    "reports",
    "report_versions",
    "report_version_metric_snapshots",
    "audit_events"
)

$clientOwnedTables = @($expectedTables | Where-Object { $_ -ne "clients" })
$phaseTwoMigrations = @($migrations | Where-Object { $_.Name -ne "20260801000000_empty_baseline.sql" })
$errors = [System.Collections.Generic.List[string]]::new()

if ($migrations.Count -ne (@($migrations.Name | Sort-Object -Unique)).Count) {
    $errors.Add("Migration filenames are not unique.")
}

foreach ($migration in $migrations) {
    if ($migration.Name -notmatch '^\d{14}_[a-z0-9_]+\.sql$') {
        $errors.Add("Invalid migration filename: $($migration.Name)")
    }
}

$orderedNames = @($migrations.Name | Sort-Object)
for ($index = 1; $index -lt $orderedNames.Count; $index++) {
    $previousTimestamp = $orderedNames[$index - 1].Substring(0, 14)
    $currentTimestamp = $orderedNames[$index].Substring(0, 14)
    if ($currentTimestamp -le $previousTimestamp) {
        $errors.Add("Migration timestamps are not strictly increasing: $($orderedNames[$index - 1]), $($orderedNames[$index])")
    }
}

foreach ($migration in $phaseTwoMigrations) {
    $content = Get-Content -LiteralPath $migration.FullName -Raw
    if ($content -notmatch '(?is)^\s*--.*?\bbegin\s*;' -or $content -notmatch '(?is)\bcommit\s*;\s*$') {
        $errors.Add("Phase 2 migration is not transaction-wrapped: $($migration.Name)")
    }
}

$combinedSql = ($migrations | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw }) -join "`n"

foreach ($table in $expectedTables) {
    $createPattern = "(?is)create\s+table\s+if\s+not\s+exists\s+public\." + [regex]::Escape($table) + "\s*\((.*?)\n\);"
    $tableMatch = [regex]::Match($combinedSql, $createPattern)
    if (-not $tableMatch.Success) {
        $errors.Add("Missing expected table: $table")
        continue
    }

    $body = $tableMatch.Groups[1].Value
    if ($table -ne "report_version_metric_snapshots" -and $body -notmatch '(?im)^\s*id\s+uuid\s+primary\s+key\b') {
        $errors.Add("Table $table does not have a UUID primary key.")
    }
}

foreach ($table in $clientOwnedTables) {
    $createPattern = "(?is)create\s+table\s+if\s+not\s+exists\s+public\." + [regex]::Escape($table) + "\s*\((.*?)\n\);"
    $tableMatch = [regex]::Match($combinedSql, $createPattern)
    if ($tableMatch.Success -and $tableMatch.Groups[1].Value -notmatch '(?im)^\s*client_id\s+uuid\s+not\s+null\b') {
        $errors.Add("Client-owned table $table is missing non-null client_id.")
    }

    $clientIndexPattern = "(?is)create\s+(?:unique\s+)?index\s+if\s+not\s+exists\s+\w+\s+on\s+public\." + [regex]::Escape($table) + "\s*\(\s*client_id\b"
    if ($combinedSql -notmatch $clientIndexPattern) {
        $errors.Add("Client-owned table $table is missing an explicit client-leading index.")
    }
}

$foreignKeyMatches = [regex]::Matches($combinedSql, '(?is)references\s+public\.(\w+)\s*\(')
foreach ($foreignKeyMatch in $foreignKeyMatches) {
    $targetTable = $foreignKeyMatch.Groups[1].Value
    $targetCreate = [regex]::Match(
        $combinedSql,
        "(?is)create\s+table\s+if\s+not\s+exists\s+public\." + [regex]::Escape($targetTable) + "\s*\("
    )
    if (-not $targetCreate.Success) {
        $errors.Add("Foreign key target is not created by these migrations: $targetTable")
    }
    elseif ($targetCreate.Index -gt $foreignKeyMatch.Index) {
        $errors.Add("Foreign key target $targetTable is created after it is referenced.")
    }
}

$requiredSameClientForeignKeys = @(
    'foreign key (client_id, integration_connection_id)',
    'foreign key (client_id, google_sheet_config_id)',
    'foreign key (client_id, sync_run_id)',
    'foreign key (client_id, raw_sheet_row_id)',
    'foreign key (client_id, lead_record_id)',
    'foreign key (client_id, kpi_id)',
    'foreign key (client_id, report_id)',
    'foreign key (client_id, report_version_id)',
    'foreign key (client_id, metric_snapshot_id)'
)

foreach ($foreignKey in $requiredSameClientForeignKeys) {
    if ($combinedSql -notmatch [regex]::Escape($foreignKey)) {
        $errors.Add("Missing same-client foreign key shape: $foreignKey")
    }
}

$forbiddenSchemaPatterns = @(
    '(?im)^\s*create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?(users|profiles|memberships|roles)\b',
    '(?im)^\s*create\s+policy\b',
    '(?im)^\s*alter\s+table\b.*\benable\s+row\s+level\s+security\b',
    '(?im)^\s*(insert\s+into|copy\s+)\b',
    '(?i)\b(access_token|refresh_token|client_secret|service_role_key|secret_key|api_key|database_url|password)\b',
    '(?i)\b(phone_e164|email_normalized)\b',
    '(?i)postgres(?:ql)?://',
    '(?i)https://[a-z0-9-]+\.supabase\.co',
    '(?i)\beyJ[a-zA-Z0-9_-]{20,}',
    '(?i)\bsk-[a-zA-Z0-9_-]{16,}',
    '(?is)\bstatus\s+in\s*\('
)

foreach ($pattern in $forbiddenSchemaPatterns) {
    if ($combinedSql -match $pattern) {
        $errors.Add("Forbidden schema or data pattern matched: $pattern")
    }
}

if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Error $_ }
    throw "Migration validation failed with $($errors.Count) error(s)."
}

Write-Host "Static migration validation passed."
Write-Host "Validated $($migrations.Count) ordered migration(s) and $($expectedTables.Count) table(s)."
Write-Host "Validated transaction wrappers, UUID keys, client scope, FK order, indexes, and secret/PII guards."

if ($ApplyDatabase) {
    if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
        throw "Set DATABASE_DIRECT_URL or pass -DatabaseUrl to validate against an empty test database."
    }

    $runner = Join-Path $PSScriptRoot "apply-migrations.ps1"
    & $runner -DatabaseUrl $DatabaseUrl
    if ($LASTEXITCODE -ne 0) {
        throw "Database migration application failed."
    }

    Write-Host "Database application validation passed."
}
elseif (-not [string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    Write-Host "DATABASE_DIRECT_URL is set; database application was skipped because -ApplyDatabase was not supplied."
}
else {
    Write-Host "Database application skipped: DATABASE_DIRECT_URL is not set."
}
