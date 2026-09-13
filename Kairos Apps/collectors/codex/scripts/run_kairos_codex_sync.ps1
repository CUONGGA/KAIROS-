param(
	[string]$Distro = "Ubuntu-24.04"
)

$ErrorActionPreference = "Stop"
$runnerWindowsPath = Join-Path $PSScriptRoot "run_kairos_codex_sync.sh"

if (-not (Test-Path -LiteralPath $runnerWindowsPath -PathType Leaf)) {
	throw "WSL runner was not found: $runnerWindowsPath"
}

$runnerWslPath = (& wsl.exe -d $Distro -- wslpath -a $runnerWindowsPath).Trim()
if ($LASTEXITCODE -ne 0 -or -not $runnerWslPath) {
	throw "Could not convert the collector runner path for WSL distro '$Distro'."
}

& wsl.exe -d $Distro -- bash $runnerWslPath
exit $LASTEXITCODE
