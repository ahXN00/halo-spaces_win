# halo.spaces – Installieren / Deinstallieren im Thunderbird-Profil (Windows)
# Aufruf über halo-spaces.cmd im Repo (Menü). Ohne Menü: -Action Install|Uninstall; -ProfileDir für ein
# anderes Profil, -NoPause ohne Tastendruck am Ende (z. B. zum Ausprobieren mit einem Testprofil)
param([string]$ProfileDir, [ValidateSet("Install", "Uninstall")][string]$Action, [switch]$NoPause)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$AddonId = "mail-cards@sebastian.local"
# Kopfzeile der userChrome.css, die „Design ohne Aufblitzen beim Start“ schreibt – nur diese wird entfernt
$EarlyHead = "/* halo.spaces: automatisch geschrieben"

function Pause-Key([string]$Text = "Press any key to close.") {
    if ($NoPause) { return }
    Write-Host ""
    Write-Host $Text
    [void][System.Console]::ReadKey($true)
}

# Profil, das Thunderbird wirklich startet: [Install…] Default= in profiles.ini, sonst [Profile…] Default=1
function Find-Profile {
    $base = Join-Path $env:APPDATA "Thunderbird"
    $ini = Join-Path $base "profiles.ini"
    if (-not (Test-Path $ini)) { return $null }
    $sections = @{}; $name = $null
    foreach ($line in Get-Content $ini) {
        if ($line -match '^\[(.+)\]$') { $name = $Matches[1]; $sections[$name] = @{} }
        elseif ($name -and $line -match '^([^=]+)=(.*)$') { $sections[$name][$Matches[1]] = $Matches[2] }
    }
    $path = ($sections.Keys | Where-Object { $_ -like "Install*" } | ForEach-Object { $sections[$_]["Default"] } | Where-Object { $_ } | Select-Object -First 1)
    $relative = $true
    if (-not $path) {
        $p = $sections.Keys | Where-Object { $_ -like "Profile*" -and $sections[$_]["Default"] -eq "1" } | Select-Object -First 1
        if (-not $p) { $p = $sections.Keys | Where-Object { $_ -like "Profile*" } | Sort-Object | Select-Object -First 1 }
        if (-not $p) { return $null }
        $path = $sections[$p]["Path"]
        $relative = $sections[$p]["IsRelative"] -ne "0"
    }
    if ($relative) { $path = Join-Path $base ($path -replace '/', '\') }
    return $path
}

# Thunderbird muss geschlossen sein, sonst übernimmt es die Änderung nicht sauber
function Wait-ThunderbirdClosed {
    while (Get-Process -Name thunderbird -ErrorAction SilentlyContinue) {
        Write-Host ""
        Write-Host "Thunderbird is open. Please close Thunderbird, then press any key to continue (Q to cancel)." -ForegroundColor Yellow
        $key = [System.Console]::ReadKey($true)
        if ($key.Key -eq "Q") { return $false }
        Start-Sleep -Seconds 1
    }
    return $true
}

# frisch bauen, wenn Python da ist – sonst das neueste gebaute Paket
function Get-Package {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notlike "*WindowsApps*") {
        Write-Host "Building the package ..."
        & $python.Source (Join-Path $Root "build.py") | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "build.py failed" }
    }
    $xpi = Get-ChildItem (Join-Path $Root "dist") -Filter "halo-spaces-*.xpi" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike "*-atn.xpi" } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    return $xpi
}

function Install-Halo([string]$prof) {
    $xpi = Get-Package
    if (-not $xpi) {
        Write-Host "No package found. Install Python 3 (then this builds it) or put halo-spaces-<version>.xpi into the dist folder." -ForegroundColor Red
        return $false
    }
    if (-not (Wait-ThunderbirdClosed)) { return $false }
    $ext = Join-Path $prof "extensions"
    New-Item -ItemType Directory -Force -Path $ext | Out-Null
    $target = Join-Path $ext "$AddonId.xpi"
    $update = Test-Path $target
    Copy-Item $xpi.FullName $target -Force
    Write-Host ""
    Write-Host ("Installed {0} into {1}" -f $xpi.Name, $prof) -ForegroundColor Green
    if (-not $update) {
        Write-Host "Start Thunderbird. If it asks whether to enable halo.spaces, choose Enable."
    } else {
        Write-Host "Updated. The new version is active the next time Thunderbird starts."
    }
    return $true
}

function Uninstall-Halo([string]$prof) {
    if (-not (Wait-ThunderbirdClosed)) { return $false }
    $target = Join-Path $prof "extensions\$AddonId.xpi"
    $found = Test-Path $target
    if ($found) { Remove-Item $target -Force }
    # userChrome.css nur entfernen, wenn halo.spaces sie selbst geschrieben hat
    $css = Join-Path $prof "chrome\userChrome.css"
    if ((Test-Path $css) -and ((Get-Content $css -TotalCount 1 -Encoding UTF8) -like "$EarlyHead*")) {
        Remove-Item $css -Force
        $found = $true
    }
    Write-Host ""
    if ($found) {
        Write-Host "Uninstalled halo.spaces from $prof" -ForegroundColor Green
        Write-Host "Thunderbird looks like before the next time it starts."
    } else {
        Write-Host "halo.spaces is not installed in $prof" -ForegroundColor Yellow
    }
    return $true
}

try {
    $prof = if ($ProfileDir) { $ProfileDir } else { Find-Profile }
    Write-Host "halo.spaces for Windows" -ForegroundColor Cyan
    Write-Host "======================="
    if (-not $prof -or -not (Test-Path $prof)) {
        Write-Host "No Thunderbird profile found. Start Thunderbird once, close it, and try again." -ForegroundColor Red
        Pause-Key
        exit 1
    }
    Write-Host "Profile: $prof"
    Write-Host ""
    Write-Host "  1  Install (or update)"
    Write-Host "  2  Uninstall"
    Write-Host "  Q  Quit"
    Write-Host ""
    $choice = @{ Install = "1"; Uninstall = "2" }[$Action]
    while ($choice -notin @("1", "2", "Q")) {
        $choice = ([string][System.Console]::ReadKey($true).KeyChar).ToUpper()
    }
    $ok = $true
    switch ($choice) {
        "1" { $ok = Install-Halo $prof; if ($ok) { Write-Host ""; Write-Host "Install finished." -ForegroundColor Green } }
        "2" { $ok = Uninstall-Halo $prof; if ($ok) { Write-Host ""; Write-Host "Uninstall finished." -ForegroundColor Green } }
        "Q" { exit 0 }
    }
    if (-not $ok) { Write-Host ""; Write-Host "Cancelled - nothing was changed." -ForegroundColor Yellow }
    Pause-Key
    exit ([int](-not $ok))
} catch {
    Write-Host ""
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Pause-Key
    exit 1
}
