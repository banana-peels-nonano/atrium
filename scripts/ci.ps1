# Charter House — local CI (the 10 merge gates of docs/63).
# Run before every merge to `main`. Exit non-zero if any gate fails.
# ALL TEN GATES ARE LIVE (Phase-7 exit hardening, 2026-07-22): the last four
# placeholders (1 architecture-contracts, 5 anti-coupling, 9 ownership,
# 10 determinism) activated once every subsystem was real.
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

# 2: Lifecycle invariants (INV-SM-*) — the A11 invariant harness, live now that S5 is real.
# Verifies every INV-SM-1..6 maps to a collectable test (docs/55 §4); an unmapped or
# renamed/deleted invariant test fails the gate rather than passing silently.
Gate 2 'lifecycle invariants (INV-SM-*)' {
    & $py (Join-Path $root 'scripts\invariant_check.py') 'INV-SM'
    if ($LASTEXITCODE -ne 0) { throw "invariant harness failed" }
}

# Gates 1/5/9/10 — activated at Phase-7 exit (all subsystems real, 2026-07-22):
Gate 1 'architecture contracts / ICR drift' {
    & $py (Join-Path $root 'scripts\architecture_check.py')
    if ($LASTEXITCODE -ne 0) { throw "architecture-contract drift" }
}
Gate 5 'anti-coupling import check (43 §8)' {
    & $py (Join-Path $root 'scripts\anticoupling_check.py')
    if ($LASTEXITCODE -ne 0) { throw "forbidden cross-subsystem import" }
}
Gate 9 'ownership check (60)' {
    $files = git ls-files
    & $py (Join-Path $root 'scripts\ownership_check.py') @files
    if ($LASTEXITCODE -ne 0) { throw "orphan file without an owner" }
}
Gate 10 'determinism import check (INV-DET)' {
    & $py (Join-Path $root 'scripts\determinism_check.py')
    if ($LASTEXITCODE -ne 0) { throw "deterministic module touched the LLM path" }
}

if ($fail.Count) {
    Write-Host "`nCI RED — merge blocked:" -ForegroundColor Red
    $fail | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}
Write-Host "`nCI GREEN — all active gates pass." -ForegroundColor Green
exit 0
