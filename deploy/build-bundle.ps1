[CmdletBinding()]
param(
    [string]$OutputPath = "dist/it-audit-installer.sh"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$gitStatus = git -C $repoRoot status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Could not read the Git repository state."
}
if ($gitStatus) {
    throw "Commit all changes first: the bundle is built only from a clean HEAD."
}

$output = Join-Path $repoRoot $OutputPath
$outputDirectory = Split-Path -Parent $output
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$archive = Join-Path ([System.IO.Path]::GetTempPath()) "it-audit-$([guid]::NewGuid()).tar.gz"
try {
    git -C $repoRoot archive --format=tar.gz --output=$archive HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "Не удалось собрать архив из Git HEAD."
    }

    $sha256 = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $payload = [Convert]::ToBase64String([IO.File]::ReadAllBytes($archive))
    $header = @'
#!/usr/bin/env bash
set -Eeuo pipefail

readonly EXPECTED_SHA256="__SHA256__"
extract_dir="$(mktemp -d)"
archive_path="${extract_dir}/it-audit.tar.gz"
trap 'rm -rf "${extract_dir}"' EXIT

payload_line="$(awk '/^__IT_AUDIT_PAYLOAD_BELOW__$/ {print NR + 1; exit}' "$0")"
[[ -n "${payload_line}" ]] || { echo "The installer payload is missing." >&2; exit 1; }
tail -n +"${payload_line}" "$0" | base64 --decode > "${archive_path}"

actual_sha256="$(sha256sum "${archive_path}" | awk '{print $1}')"
[[ "${actual_sha256}" == "${EXPECTED_SHA256}" ]] || {
    echo "The installer checksum does not match." >&2
    exit 1
}

tar -xzf "${archive_path}" -C "${extract_dir}"
bash "${extract_dir}/deploy/install.sh"
exit 0

__IT_AUDIT_PAYLOAD_BELOW__
'@
    $header = $header.Replace("__SHA256__", $sha256)
    $header = $header.Replace("`r`n", "`n").Replace("`r", "`n")
    $content = $header + "`n" + $payload + "`n"
    [IO.File]::WriteAllText($output, $content, [Text.UTF8Encoding]::new($false))
    Write-Host "Created: $output"
    Write-Host "Run on the VPS: sudo bash ./it-audit-installer.sh"
}
finally {
    Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
}
