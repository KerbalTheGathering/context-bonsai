# Dev aid: launch the app, let it settle, and report CPU per Electron process over a window of time,
# as % of one core. Optional: -Cfg '{"ambient":false}' (unsaved overrides), -Theme Aurora, -Bare (a plain
# Electron window, for the baseline).
param([string]$Cfg = "", [string]$Theme = "", [int]$Settle = 8, [int]$Seconds = 15, [switch]$Bare)

$app = Split-Path -Parent $PSScriptRoot
$electron = Join-Path $app 'node_modules\electron\dist\electron.exe'
if ($Cfg) { $env:BONSAI_CFG = $Cfg } else { Remove-Item Env:BONSAI_CFG -ErrorAction SilentlyContinue }
if ($Theme) { $env:BONSAI_THEME = $Theme } else { Remove-Item Env:BONSAI_THEME -ErrorAction SilentlyContinue }
$target = $app
if ($Bare) {
    $target = Join-Path $env:TEMP 'bonsai-bare'
    New-Item -ItemType Directory -Force $target | Out-Null
    Set-Content (Join-Path $target 'package.json') '{"name":"bare","main":"main.js"}'
    Set-Content (Join-Path $target 'main.js') @'
const { app, BrowserWindow } = require("electron");
app.whenReady().then(() => {
  const w = new BrowserWindow({ width: 300, height: 400, frame: false, alwaysOnTop: true, skipTaskbar: true });
  w.loadURL("data:text/html,<body style='background:#123'>idle</body>");
});
'@
}
$p = Start-Process -FilePath $electron -ArgumentList "`"$target`"" -PassThru
try {
    Start-Sleep -Seconds $Settle
    $a = @{}; Get-Process electron | ForEach-Object { $a[$_.Id] = $_.CPU }
    Start-Sleep -Seconds $Seconds
    $total = 0; $parts = @()
    Get-CimInstance Win32_Process -Filter "Name='electron.exe'" | ForEach-Object {
        $id = [int]$_.ProcessId
        $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
        if (-not $proc -or -not $a.ContainsKey($id)) { return }
        $type = if ($_.CommandLine -match '--type=(\S+)') { $Matches[1] } else { 'main' }
        $c = ($proc.CPU - $a[$id]) / $Seconds * 100
        $total += $c
        $parts += ('{0} {1:N1}' -f $type, $c)
    }
    '{0:N1}% of one core  ({1})' -f $total, ($parts -join ', ')
} finally {
    Get-Process electron -ErrorAction SilentlyContinue | Stop-Process -Force
    Remove-Item Env:BONSAI_CFG, Env:BONSAI_THEME -ErrorAction SilentlyContinue
}
