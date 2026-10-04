# Installs Context Bonsai from this clone into your Claude Code (Windows).
#
#   -Plan       print what would change (including the exact settings.json edits) and change nothing
#   -Yes        do it without asking (how Claude runs it, after showing you the plan)
#   -Uninstall  remove it again: plugin, marketplace, status line, shortcuts (your widget settings stay)
#   -SkipApp    leave the desktop app alone (no npm install/build, no shortcut changes)
#
# Run with no switches to see the plan and be asked before anything changes.
# It: adds this clone as a plugin marketplace and installs (or updates) the context-bonsai plugin, which
# provides the compaction hooks; moves ~/.claude/settings.json off the old hand-installed hooks and points
# the status line at the clone (backing the file up first); builds the desktop app; creates the Start menu
# shortcuts; and records the clone's location in ~/.claude/widget/install.json for the plugin's commands.
param([switch]$Plan, [switch]$Yes, [switch]$Uninstall, [switch]$SkipApp)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$claudeDir = Join-Path $HOME '.claude'
$data = Join-Path $claudeDir 'widget'
$programs = [Environment]::GetFolderPath('Programs')
$app = Join-Path $repo 'desktop'
$electron = Join-Path $app 'node_modules\electron\dist\electron.exe'
$market = 'context-bonsai'
$pluginId = 'context-bonsai@context-bonsai'

function Need($cmd, $why) {
    $c = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $c) { throw "$cmd not found on PATH ($why)." }
    $c.Source
}

function Native { # run a native command; fail loudly on a non-zero exit
    param([string]$what, [Parameter(ValueFromRemainingArguments = $true)] $cmd)
    $rest = @($cmd | Select-Object -Skip 1)
    $out = & $cmd[0] @rest 2>&1 | Out-String
    if ($LASTEXITCODE) { throw "$what failed (exit $LASTEXITCODE):`n$out" }
    $out
}

function Step($text) { Write-Host "- $text" }

$python = Need 'python' 'the hooks and status line are Python scripts'
$pythonw = Need 'pythonw' 'the classic widget runs under pythonw'
$claude = Need 'claude' 'installs the plugin'
if (-not $SkipApp -and -not $Uninstall) { Need 'npm' 'builds the desktop app (Node.js)' | Out-Null }

# --- what's there now ---
$markets = (& $claude plugin marketplace list 2>&1 | Out-String)
$hasMarket = $markets -match "(?m)^\s*.*\b$market\b"
$plugins = (& $claude plugin list 2>&1 | Out-String)
$hasPlugin = $plugins -match [regex]::Escape($pluginId)
$migrateArgs = @((Join-Path $repo 'scripts\settings_migrate.py'), 'plan', '--repo', $repo)
if ($Uninstall) { $migrateArgs += '--uninstall' }
$settingsPlan = (Native 'Planning the settings changes' $python @migrateArgs) | ConvertFrom-Json
$legacy = @('hooks\rehydrate.py', 'statusline.py', 'widget\bonsai_widget.pyw', 'widget\precompact_signal.py') |
    ForEach-Object { Join-Path $claudeDir $_ } | Where-Object { Test-Path $_ }

# --- the plan ---
Write-Host "Context Bonsai $(if ($Uninstall) { 'uninstall' } else { 'install' }) from $repo"
if ($Uninstall) {
    if ($hasPlugin) { Step "uninstall the $pluginId plugin" }
    if ($hasMarket) { Step "remove the $market marketplace" }
} else {
    Step "check the plugin (claude plugin validate --strict)"
    Step $(if ($hasMarket) { "refresh the $market marketplace from this clone" } else { "add this clone as the $market marketplace" })
    Step $(if ($hasPlugin) { "update the $pluginId plugin (restart Claude Code to load it)" } else { "install the $pluginId plugin for your user" })
}
if ($settingsPlan.changes.Count) {
    Step "edit $($settingsPlan.settings) (backed up first):"
    $settingsPlan.changes | ForEach-Object { Write-Host "    * $_" }
} else { Step "no settings.json changes needed" }
if (-not $SkipApp) {
    if ($Uninstall) { Step "remove the Start menu shortcuts and $data\install.json (your widget settings stay)" }
    else {
        Step "build the desktop app in $app (npm install, npm run build)"
        Step "Start menu: 'Context Bonsai' opens the desktop app, 'Context Bonsai (classic)' the Tk widget"
        Step "record this clone in $data\install.json for /context-bonsai:widget and :setup"
    }
}
if ($legacy -and -not $Uninstall) {
    Step "these old hand-installed copies are no longer used and can be deleted (left in place):"
    $legacy | ForEach-Object { Write-Host "    $_" }
}
if ($Plan) { return }
if (-not $Yes) {
    if ((Read-Host 'Go ahead? [y/N]') -notmatch '^(y|yes)$') { Write-Host 'Nothing changed.'; return }
}

# --- do it ---
if ($Uninstall) {
    if ($hasPlugin) { Native 'Uninstalling the plugin' $claude plugin uninstall $pluginId | Out-Null }
    if ($hasMarket) { Native 'Removing the marketplace' $claude plugin marketplace remove $market | Out-Null }
} else {
    Native 'Validating the plugin' $claude plugin validate --strict (Join-Path $repo 'plugin') | Out-Null
    if ($hasMarket) { Native 'Refreshing the marketplace' $claude plugin marketplace update $market | Out-Null }
    else { Native 'Adding the marketplace' $claude plugin marketplace add $repo | Out-Null }
    if ($hasPlugin) { Native 'Updating the plugin' $claude plugin update $pluginId | Out-Null }
    else { Native 'Installing the plugin' $claude plugin install $pluginId --scope user | Out-Null }
}
$migrateArgs[1] = 'apply'
$applied = (Native 'Updating settings.json' $python @migrateArgs) | ConvertFrom-Json
if ($applied.backup) { Write-Host "settings.json backed up to $($applied.backup)" }

if (-not $SkipApp) {
    $lnkMain = Join-Path $programs 'Context Bonsai.lnk'
    $lnkClassic = Join-Path $programs 'Context Bonsai (classic).lnk'
    if ($Uninstall) {
        foreach ($f in $lnkMain, $lnkClassic, (Join-Path $data 'install.json')) { if (Test-Path $f) { Remove-Item $f } }
    } else {
        Push-Location $app
        try {
            Native 'npm install' npm install --no-fund --no-audit | Out-Null
            Native 'Building the desktop app' npm run build | Out-Null
        } finally { Pop-Location }
        $icon = Join-Path $repo 'widget\bonsai.ico'
        $classicScript = Join-Path $repo 'widget\bonsai_widget.pyw'
        $shell = New-Object -ComObject WScript.Shell
        foreach ($s in @(
            @($lnkMain, $electron, "`"$app`"", $app, 'Show or hide Context Bonsai'),
            @($lnkClassic, $pythonw, "`"$classicScript`"", (Join-Path $repo 'widget'), 'Show or hide the classic Tk Context Bonsai widget'))) {
            $sc = $shell.CreateShortcut($s[0])
            $sc.TargetPath = $s[1]; $sc.Arguments = $s[2]; $sc.WorkingDirectory = $s[3]
            $sc.IconLocation = "$icon,0"; $sc.Description = $s[4]
            $sc.Save()
        }
        New-Item -ItemType Directory -Force $data | Out-Null
        $version = (Get-Content (Join-Path $repo 'plugin\.claude-plugin\plugin.json') -Raw | ConvertFrom-Json).version
        @{ repo = $repo; version = $version
           launch = @{ file = $electron; args = "`"$app`"" }
           classic = @{ file = $pythonw; args = "`"$classicScript`"" } } |
            ConvertTo-Json -Depth 4 | Set-Content (Join-Path $data 'install.json') -Encoding UTF8
    }
}
Write-Host $(if ($Uninstall) { 'Context Bonsai removed.' } else { 'Context Bonsai installed. New sessions use the plugin hooks; restart Claude Code if it was already running.' })
