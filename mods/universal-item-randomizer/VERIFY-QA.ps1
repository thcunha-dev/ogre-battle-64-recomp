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
    "SEED-VECTORS.md",
    "verify_randomizer_rev_a_rom.py",
    "audit_randomizer_grant_abi_rom.py",
    "audit_randomizer_post_battle_abi_rom.py",
    "audit_randomizer_coupled_a1_abi_rom.py",
    "audit_randomizer_starting_block_abi_rom.py"
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

if ($Manifest["persistence_model"] -ne "5000_on_off_on_sequences") {
    throw "Unexpected or missing native-save persistence model marker"
}

if ($Manifest["postgame_persistence_model"] -ne "2000_finished_game_on_off_on_sequences") {
    throw "Unexpected or missing post-game persistence model marker"
}

if ($Manifest["use_repair"] -ne "native_slot_indexed") {
    throw "Unexpected or missing native slot-indexed use-repair marker"
}

if ($Manifest["central_grant_a1"] -ne "native_consumable_used_flag") {
    throw "Unexpected or missing central-grant a1 marker"
}

if ($Manifest["bank_r_coupled_grants"] -ne "two_a1_one_callers_fail_closed") {
    throw "Unexpected or missing coupled Bank-R grant marker"
}

if ($Manifest["starting_items_scope"] -ne "forty_literal_a1_zero_no_store_calls") {
    throw "Unexpected or missing STARTING ITEMS scope marker"
}

if ($Manifest["rom_verifier"] -ne "one_command_four_audits") {
    throw "Unexpected or missing one-command ROM verifier marker"
}

Write-Host "Universal Item Randomizer QA payload: PASS"
Write-Host "Version: $($Manifest['version'])"
Write-Host "Source commit: $($Manifest['source_commit'])"
Write-Host "Host suite: $($Manifest['host_suite'])"
Write-Host "Persistence model: $($Manifest['persistence_model'])"
Write-Host "Post-game persistence model: $($Manifest['postgame_persistence_model'])"
Write-Host "Use repair: $($Manifest['use_repair'])"
Write-Host "Central grant a1: $($Manifest['central_grant_a1'])"
Write-Host "Bank-R coupled grants: $($Manifest['bank_r_coupled_grants'])"
Write-Host "Starting items scope: $($Manifest['starting_items_scope'])"
Write-Host "ROM verifier: $($Manifest['rom_verifier'])"
Write-Host "Rev-A verifier command: python verify_randomizer_rev_a_rom.py <Rev-A.z64>"
Write-Host "NRM SHA-256: $Actual"
