# Copies the mods into ~/.claude and adds the "Context Bonsai" Start menu shortcut.
# Hook and status line settings are not touched: merge settings.example.json into
# ~/.claude/settings.json yourself (replace YOU with your user name).

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$claude = Join-Path $HOME '.claude'

New-Item -ItemType Directory -Force (Join-Path $claude 'hooks'), (Join-Path $claude 'widget') | Out-Null
Copy-Item (Join-Path $repo 'hooks\rehydrate.py') (Join-Path $claude 'hooks\')
Copy-Item (Join-Path $repo 'statusline\statusline.py') $claude
foreach ($f in 'bonsai_widget.pyw', 'precompact_signal.py', 'bonsai.ico') {
    Copy-Item (Join-Path $repo "widget\$f") (Join-Path $claude 'widget\')
}

$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pythonw) { throw 'pythonw.exe not found on PATH (the widget needs Python with Tk and Pillow).' }
$widget = Join-Path $claude 'widget'
$lnk = Join-Path ([Environment]::GetFolderPath('Programs')) 'Context Bonsai.lnk'
$sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$sc.TargetPath = $pythonw
$sc.Arguments = '"' + (Join-Path $widget 'bonsai_widget.pyw') + '"'
$sc.WorkingDirectory = $widget
$sc.IconLocation = (Join-Path $widget 'bonsai.ico') + ',0'
$sc.Description = 'Show or hide the Context Bonsai widget'
$sc.Save()

Write-Host "Installed to $claude and created $lnk"
Write-Host 'If the widget is running, open the shortcut twice to restart it on the new version.'
