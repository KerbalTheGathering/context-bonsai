# Copies the mods into ~/.claude and adds the "Context Bonsai" Start menu shortcut.
# Hook and status line settings are not touched: merge settings.example.json into
# ~/.claude/settings.json yourself (replace YOU with your user name).
# -Desktop also builds the Electron + PixiJS version in .\desktop (needs Node.js) and makes
# "Context Bonsai" open it; the Tk widget stays available as "Context Bonsai (classic)".
param([switch]$Desktop)

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$claude = Join-Path $HOME '.claude'
$programs = [Environment]::GetFolderPath('Programs')

New-Item -ItemType Directory -Force (Join-Path $claude 'hooks'), (Join-Path $claude 'widget') | Out-Null
Copy-Item (Join-Path $repo 'hooks\rehydrate.py') (Join-Path $claude 'hooks\')
Copy-Item (Join-Path $repo 'statusline\statusline.py') $claude
foreach ($f in 'bonsai_widget.pyw', 'precompact_signal.py', 'bonsai.ico') {
    Copy-Item (Join-Path $repo "widget\$f") (Join-Path $claude 'widget\')
}
$widget = Join-Path $claude 'widget'

function Set-Shortcut($name, $target, $arguments, $workdir, $description) {
    $lnk = Join-Path $programs "$name.lnk"
    $sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
    $sc.TargetPath = $target
    $sc.Arguments = $arguments
    $sc.WorkingDirectory = $workdir
    $sc.IconLocation = (Join-Path $widget 'bonsai.ico') + ',0'
    $sc.Description = $description
    $sc.Save()
    Write-Host "Shortcut: $lnk"
}

$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pythonw) { throw 'pythonw.exe not found on PATH (the widget needs Python with Tk and Pillow).' }
$classic = '"' + (Join-Path $widget 'bonsai_widget.pyw') + '"'

if ($Desktop) {
    $app = Join-Path $repo 'desktop'
    Push-Location $app
    try {
        npm install
        if ($LASTEXITCODE) { throw 'npm install failed' }
        npm run build
        if ($LASTEXITCODE) { throw 'npm run build failed' }
    } finally { Pop-Location }
    Set-Shortcut 'Context Bonsai' (Join-Path $app 'node_modules\electron\dist\electron.exe') ('"' + $app + '"') $app `
        'Show or hide Context Bonsai'
    Set-Shortcut 'Context Bonsai (classic)' $pythonw $classic $widget 'Show or hide the classic Tk Context Bonsai widget'
    $old = Join-Path $programs 'Context Bonsai (desktop).lnk'
    if (Test-Path $old) { Remove-Item $old }
} else {
    Set-Shortcut 'Context Bonsai' $pythonw $classic $widget 'Show or hide the Context Bonsai widget'
}

Write-Host "Installed to $claude"
Write-Host 'If the widget is running, open the shortcut twice to restart it on the new version.'
