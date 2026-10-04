# Packages the desktop app as a standalone copy: Electron's runtime with the app in resources\app and the
# exe renamed ContextBonsai.exe, so it no longer depends on the clone. The app has no runtime npm
# dependencies (PixiJS is bundled into dist\app.js), so only five things are copied.
#   -Dest   where to put it (default: %LOCALAPPDATA%\Programs\ContextBonsai)
# Build first (npm run build in desktop\). Closes a running copy so its files can be replaced.
param([string]$Dest = (Join-Path $env:LOCALAPPDATA 'Programs\ContextBonsai'))

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$app = Join-Path $repo 'desktop'
$runtime = Join-Path $app 'node_modules\electron\dist'
if (-not (Test-Path (Join-Path $runtime 'electron.exe'))) { throw "Electron isn't installed in $app (run npm install there)." }
if (-not (Test-Path (Join-Path $app 'dist\app.js'))) { throw "The app isn't built (run npm run build in $app)." }

$exe = Join-Path $Dest 'ContextBonsai.exe'
Get-Process ContextBonsai -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe } | Stop-Process -Force
Start-Sleep -Milliseconds 300

if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
New-Item -ItemType Directory -Force $Dest | Out-Null
Copy-Item (Join-Path $runtime '*') $Dest -Recurse
Rename-Item (Join-Path $Dest 'electron.exe') 'ContextBonsai.exe'
Remove-Item (Join-Path $Dest 'resources\default_app.asar') -ErrorAction SilentlyContinue
# Chromium's UI translations: the widget shows no browser UI, so English is enough
Get-ChildItem (Join-Path $Dest 'locales') -Filter '*.pak' | Where-Object { $_.Name -ne 'en-US.pak' } | Remove-Item

$target = Join-Path $Dest 'resources\app'
New-Item -ItemType Directory -Force $target | Out-Null
foreach ($part in 'main', 'shared', 'dist', 'index.html', 'package.json') {
    Copy-Item (Join-Path $app $part) $target -Recurse
}
Get-ChildItem (Join-Path $target 'dist') -Filter '*.map' | Remove-Item
Copy-Item (Join-Path $repo 'widget\bonsai.ico') $target
Write-Output $exe
