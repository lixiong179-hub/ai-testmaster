$ErrorActionPreference = 'Continue'
$d = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$M = 'docker.m.daocloud.io/library'
$log = Join-Path $env:TEMP 'k4_pull.log'
"START $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append $log -Encoding utf8

foreach ($img in @('mysql:8.0', 'redis:7-alpine', 'python:3.11-slim', 'node:20-alpine')) {
    "=== pulling $img ===" | Out-File -Append $log -Encoding utf8
    & $d pull "$M/$img" *>> $log
    if ($LASTEXITCODE -eq 0) {
        & $d tag "$M/$img" $img *>> $log
        "OK $img" | Out-File -Append $log -Encoding utf8
    }
    else {
        "FAIL $img (exit=$LASTEXITCODE)" | Out-File -Append $log -Encoding utf8
    }
}

"ALL_DONE $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append $log -Encoding utf8
