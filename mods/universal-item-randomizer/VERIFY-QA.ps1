$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ManifestPath = Join-Path $Root "BUILD-MANIFEST.txt"
$NrmPath = Join-Path $Root "universal-item-randomizer.nrm"

$Required = @(
    "BUILD-MANIFEST.txt",
    "universal-item-randomizer.nrm",
    "TESTING.md",
    "QA-CHECKLIST.md",
    "QA-TELEMETRY.md",
    "STATUS.md",
    "SEED-VECTORS.md"
)

foreach ($Name in $Required) {
    $Path = Join-Path $Root $Name
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing QA payload file: $Name"
    }
}

$Manifest = @{}
foreach ($Line in Get-Content -LiteralPath $ManifestPath) {
    if ($Line -match '^([^=]+)=(.*)$') {
        $Manifest[$Matches[1]] = $Matches[2]
    }
}

if ($Manifest["version"] -ne "0.3.1") {
    throw "Unexpected randomizer version: $($Manifest['version'])"
}

$Expected = $Manifest["nrm_sha256"]
if ([string]::IsNullOrWhiteSpace($Expected)) {
    throw "Manifest has no nrm_sha256"
}

$Actual = (Get-FileHash -LiteralPath $NrmPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Actual -ne $Expected.ToLowerInvariant()) {
    throw "NRM SHA-256 mismatch. Expected $Expected, got $Actual"
}

if ($Manifest["save_policy"] -ne "no_randomizer_metadata_in_native_save") {
    throw "Unexpected save policy marker"
}

if ($Manifest["config_lifecycle"] -ne "restart_required") {
    throw "Unexpected or missing config lifecycle marker"
}

Write-Host "Universal Item Randomizer QA payload: PASS"
Write-Host "Version: $($Manifest['version'])"
Write-Host "Source commit: $($Manifest['source_commit'])"
Write-Host "Host suite: $($Manifest['host_suite'])"
Write-Host "NRM SHA-256: $Actual"
