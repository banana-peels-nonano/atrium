# Charter House — local CI (the 10 merge gates of docs/63).
# Run before every merge to `main`. Exit non-zero if any active gate fails.
# Gates needing subsystems that don't exist yet are PLACEHOLDERs (clearly marked),
# to be activated as their subsystems land — the framework is wired now (Phase 0).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }
$fail = @()

function Gate($n, $name, [scriptblock]$check) {
    Write-Host "[gate $n] $name ..." -NoNewline
    try { & $check; Write-Host " PASS" -ForegroundColor Green }
    catch { Write-Host " FAIL" -ForegroundColor Red; $script:fail += "$n $name -- $($_.Exception.Message)" }
}
function Skip($n, $name, $why) { Write-Host "[gate $n] $name -- PLACEHOLDER ($why)" -ForegroundColor Yellow }

# 4 & 8: Tests pass + acceptance criteria (structure test = A0 acceptance).
Gate 4 'tests pass (pytest)' { & $py -m pytest -q; if ($LASTEXITCODE -ne 0) { throw "pytest failed" } }
# 6 & 7: Security + PII routing — deterministic secret / .private.md scan over tracked files.
Gate '6+7' 'secret / PII-sidecar scan' {
    $files = git ls-files
    & $py (Join-Path $root 'scripts\secret_scan.py') @files
    if ($LASTEXITCODE -ne 0) { throw "secret/PII scan failed" }
}
# 3: Documentation present (BUILD_TRACKER + IB entry exist; full doc-sync check lands with 62 tooling).
Gate 3 'docs present' {
    foreach ($d in 'docs\BUILD_TRACKER.md','docs\README.md','AGENTS.md') {
        if (-not (Test-Path (Join-Path $root $d))) { throw "missing $d" }
    }
}

# Placeholders — activated as the owning subsystems land:
Skip 1  'architecture contracts / ICR check' 'no 40/API surfaces yet'
Skip 2  'lifecycle invariants (INV-SM-*)'    'S5 not built (Phase 2)'
Skip 5  'anti-coupling import check (43 §8)' 'no subsystem modules yet'
Skip 9  'ownership check (60)'               'OWNERS map lands with 60 tooling'
Skip 10 'determinism import check (INV-DET)' 'no LLM-path modules yet'

if ($fail.Count) {
    Write-Host "`nCI RED — merge blocked:" -ForegroundColor Red
    $fail | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}
Write-Host "`nCI GREEN — all active gates pass." -ForegroundColor Green
exit 0
