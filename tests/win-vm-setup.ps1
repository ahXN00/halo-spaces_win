# Richtet die Windows-VM auf dem Testrechner für halo.spaces ein und prüft sie
# (Anleitung: tests/MAC-MINI.md, Abschnitt „Windows-VM“). Läuft in der VM,
# aufgerufen vom Mac über prlctl exec – beliebig oft, Erledigtes bleibt.
#   -Check      nur prüfen, nichts ändern
#   -Benutzer   Einstellungen des angemeldeten Benutzers (Bildschirmschoner,
#               Sperre); muss mit prlctl exec --current-user laufen
# ohne -Benutzer als SYSTEM (prlctl exec ohne --current-user): Energie,
# Sperrbildschirm, Neustarts durch Windows Update, Thunderbird Release und
# Beta, Python, OpenSSL (Git für Windows).
# Ausgabe wie tests/mac-mini-setup.sh: OK / OFFEN / HINWEIS, Rückgabewert 0 nur ohne OFFEN.
param([switch]$Check, [switch]$Benutzer)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$TB = "C:\Program Files\Mozilla Thunderbird"
$TB_BETA = "C:\Program Files\Thunderbird Beta"
$PY_VERSION = "3.15.1"   # wie auf dem Mac
$PY = "C:\Program Files\Python315-arm64\python.exe"
$GIT_VERSION = "2.56.0.3"
$OPENSSL = "C:\Program Files\Git\usr\bin\openssl.exe"
$CACHE = "C:\ProgramData\halo-spaces\downloads"

$script:offen = 0
function ok($a, $b = "") { Write-Output ("OK       $a" + $(if ($b) { " – $b" })) }
function offen($a, $b = "") { Write-Output ("OFFEN    $a" + $(if ($b) { " – $b" })); $script:offen++ }
function hinweis($a, $b = "") { Write-Output ("HINWEIS  $a" + $(if ($b) { " – $b" })) }

function RegWert($pfad, $name) {
  try { (Get-ItemProperty -Path $pfad -Name $name -ErrorAction Stop).$name } catch { $null }
}
function RegSetzen($pfad, $name, $wert, $typ = "DWord") {
  if (-not (Test-Path $pfad)) { New-Item -Path $pfad -Force | Out-Null }
  New-ItemProperty -Path $pfad -Name $name -Value $wert -PropertyType $typ -Force | Out-Null
}

# Lädt ein Installationsprogramm und startet es nur mit gültiger Signatur des erwarteten Herausgebers
function Laden($url, $datei, $herausgeber) {
  New-Item -ItemType Directory -Force -Path $CACHE | Out-Null
  $ziel = Join-Path $CACHE $datei
  Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $ziel
  $sig = Get-AuthenticodeSignature $ziel
  if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "O=`"?$herausgeber") {
    Remove-Item $ziel -Force
    throw "Signatur von $datei ist nicht von $herausgeber ($($sig.Status), $($sig.SignerCertificate.Subject))"
  }
  $ziel
}

# installierte Version: wie heruntergeladen (application.ini nennt bei der Beta nur „159.0“ statt „159.0b5“)
function TbVersion($ordner) {
  $merk = Join-Path $ordner "distribution\halo-version.txt"
  if (Test-Path $merk) { return (Get-Content $merk -First 1).Trim() }
  $ini = Join-Path $ordner "application.ini"
  if (Test-Path $ini) { ((Get-Content $ini) -match "^Version=") -replace "^Version=", "" | Select-Object -First 1 }
}

# neueste Version laut download.mozilla.org (aus der Weiterleitung, ohne Download)
function TbAktuell($produkt) {
  $r = [Net.HttpWebRequest]::Create("https://download.mozilla.org/?product=$produkt&os=win64&lang=en-US")
  $r.AllowAutoRedirect = $false
  $a = $r.GetResponse()
  $ort = $a.Headers["Location"]; $a.Close()
  if ($ort -match "/releases/([^/]+)/") { $Matches[1] } else { throw "Version von $produkt nicht ermittelbar" }
}

function Thunderbird($name, $produkt, $ordner) {
  $ist = TbVersion $ordner
  try { $soll = TbAktuell $produkt } catch { $soll = $null; hinweis $name "neueste Version nicht abrufbar ($_)" }
  if ($ist -and (-not $soll -or $ist -eq $soll)) { ok $name "$ist in $ordner"; return }
  if ($Check) { offen $name $(if ($ist) { "$ist installiert, $soll verfügbar" } else { "nicht installiert" }); return }
  # x64-Paket (Mozilla baut Thunderbird nicht für ARM64), läuft unter der Emulation von Windows 11
  $url = if ($soll) { "https://download-installer.cdn.mozilla.net/pub/thunderbird/releases/$soll/win64/en-US/Thunderbird%20Setup%20$soll.exe" }
         else { "https://download.mozilla.org/?product=$produkt&os=win64&lang=en-US" }
  $exe = Laden $url "$produkt.exe" "Mozilla Corporation"
  $p = Start-Process $exe -Wait -PassThru -ArgumentList "/S", "/InstallDirectoryPath=`"$ordner`"", "/MaintenanceService=false",
    "/DesktopShortcut=false", "/StartMenuShortcut=false", "/TaskbarShortcut=false", "/PrivateBrowsingShortcut=false"
  Remove-Item $exe -Force
  # keine eigenen Updates: die Version bestimmt dieses Skript
  New-Item -ItemType Directory -Force -Path "$ordner\distribution" | Out-Null
  Set-Content -Encoding ASCII "$ordner\distribution\policies.json" '{"policies": {"DisableAppUpdate": true, "DisableTelemetry": true}}'
  if ($soll) { Set-Content -Encoding ASCII "$ordner\distribution\halo-version.txt" $soll }
  $ist = TbVersion $ordner
  if ($p.ExitCode -eq 0 -and $ist) { ok $name "$ist installiert in $ordner" } else { offen $name "Installation fehlgeschlagen (Exitcode $($p.ExitCode))" }
}

if ($Benutzer) {
  # ---- angemeldeter Benutzer ----
  $desk = "HKCU:\Control Panel\Desktop"
  $schoner = RegWert $desk "ScreenSaveActive"
  $sperre = RegWert $desk "DelayLockInterval"
  $dyn = RegWert "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" "EnableGoodbye"
  if ($schoner -eq "0" -and [uint32]($sperre -band 0xFFFFFFFFL) -eq [uint32]::MaxValue -and $dyn -ne 1) { ok "Bildschirmschoner und Sperre" "aus" }
  elseif ($Check) { offen "Bildschirmschoner und Sperre" "Schoner=$schoner, Anmeldung nach Abwesenheit=$sperre, dynamische Sperre=$dyn" }
  else {
    RegSetzen $desk "ScreenSaveActive" "0" "String"
    RegSetzen $desk "ScreenSaverIsSecure" "0" "String"
    RegSetzen $desk "DelayLockInterval" 0xFFFFFFFF          # „Anmeldung erforderlich nach Abwesenheit“: nie
    RegSetzen "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" "EnableGoodbye" 0
    ok "Bildschirmschoner und Sperre" "ausgeschaltet"
  }
  $hell = RegWert "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" "AppsUseLightTheme"
  hinweis "Farbschema" $(if ($hell -eq 0) { "dunkel" } else { "hell" })
  exit [int]($script:offen -gt 0)
}

# ---- System (als SYSTEM) ----
$winlogon = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
if ((RegWert $winlogon "AutoAdminLogon") -eq "1") { ok "Automatische Anmeldung" (RegWert $winlogon "DefaultUserName") }
else { hinweis "Automatische Anmeldung" "nicht über Winlogon eingetragen (evtl. per Autologon/LSA) – nach dem Neustart prüfen" }

# Energie: nie Ruhezustand, Bildschirm nie aus, nach dem Aufwachen keine Anmeldung
$energie = powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String "Current AC Power Setting Index: 0x00000000"
$bild = powercfg /query SCHEME_CURRENT SUB_VIDEO VIDEOIDLE | Select-String "Current AC Power Setting Index: 0x00000000"
$hib = (RegWert "HKLM:\SYSTEM\CurrentControlSet\Control\Power" "HibernateEnabled") -eq 0
if ($energie -and $bild -and $hib) { ok "Energie" "kein Ruhezustand, Bildschirm bleibt an" }
elseif ($Check) { offen "Energie" "Ruhezustand oder Bildschirmabschaltung aktiv" }
else {
  foreach ($w in "monitor-timeout", "standby-timeout", "hibernate-timeout", "disk-timeout") {
    powercfg /change "$w-ac" 0; powercfg /change "$w-dc" 0
  }
  powercfg /hibernate off
  powercfg /setacvalueindex SCHEME_CURRENT SUB_NONE CONSOLELOCK 0
  powercfg /setdcvalueindex SCHEME_CURRENT SUB_NONE CONSOLELOCK 0
  powercfg /setactive SCHEME_CURRENT
  ok "Energie" "Ruhezustand und Bildschirmabschaltung ausgeschaltet"
}

# Sperrbildschirm und automatische Sperre aus, Windows Update startet nicht neu, solange jemand angemeldet ist
$pers = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization"
$sys = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
$wu = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
if ((RegWert $pers "NoLockScreen") -eq 1 -and (RegWert $sys "InactivityTimeoutSecs") -eq 0 -and (RegWert $wu "NoAutoRebootWithLoggedOnUsers") -eq 1) {
  ok "Sperrbildschirm und Neustarts" "kein Sperrbildschirm, keine Sperre bei Inaktivität, kein Update-Neustart bei Anmeldung"
} elseif ($Check) { offen "Sperrbildschirm und Neustarts" "Richtlinien fehlen" }
else {
  RegSetzen $pers "NoLockScreen" 1
  RegSetzen $sys "InactivityTimeoutSecs" 0
  RegSetzen $wu "NoAutoRebootWithLoggedOnUsers" 1
  ok "Sperrbildschirm und Neustarts" "Richtlinien gesetzt"
}

Thunderbird "Thunderbird" "thunderbird-latest-SSL" $TB
Thunderbird "Thunderbird Beta" "thunderbird-beta-latest-SSL" $TB_BETA

if (Test-Path $PY) { ok "Python" ((& $PY --version) -join "") }
elseif ($Check) { offen "Python" "nicht installiert" }
else {
  $exe = Laden "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-arm64.exe" "python.exe" "Python Software Foundation"
  $p = Start-Process $exe -Wait -PassThru -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=0", "Include_test=0", "Include_launcher=0", "Shortcuts=0"
  Remove-Item $exe -Force
  if (Test-Path $PY) { ok "Python" "$PY_VERSION installiert" } else { offen "Python" "Installation fehlgeschlagen (Exitcode $($p.ExitCode))" }
}

# openssl für den HTTPS-Testserver der Netzprüfungen
if (Test-Path $OPENSSL) { ok "OpenSSL" ((& $OPENSSL version) -join "") }
elseif ($Check) { offen "OpenSSL" "Git für Windows nicht installiert" }
else {
  $exe = Laden "https://github.com/git-for-windows/git/releases/download/v$($GIT_VERSION -replace '\.(\d+)$', '.windows.$1')/Git-$GIT_VERSION-arm64.exe" "git.exe" "Johannes Schindelin"
  $p = Start-Process $exe -Wait -PassThru -ArgumentList "/VERYSILENT", "/NORESTART", "/NOCANCEL", "/SP-", "/SUPPRESSMSGBOXES"
  Remove-Item $exe -Force
  if (Test-Path $OPENSSL) { ok "OpenSSL" ((& $OPENSSL version) -join "") } else { offen "OpenSSL" "Installation fehlgeschlagen (Exitcode $($p.ExitCode))" }
}

exit [int]($script:offen -gt 0)
