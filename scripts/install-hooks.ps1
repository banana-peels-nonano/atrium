# Installs the committed git hooks into .git/hooks (run once after clone / git init).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root 'scripts\hooks'
$dst = Join-Path $root '.git\hooks'
if (-not (Test-Path $dst)) { throw "no .git/hooks — is this a git repo?" }
Get-ChildItem $src -File | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $dst $_.Name) -Force
    Write-Host "installed hook: $($_.Name)"
}
