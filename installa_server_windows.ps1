# installa_server_windows.ps1 — installazione e configurazione di
# CaronteApp come server sempre acceso su un PC Windows della rete
# scolastica (accesso da qualunque altro dispositivo via browser,
# nessuna installazione sui client — vedi DEVLOG.md).
#
# Cosa fa, in ordine:
#   1. Verifica i permessi di amministratore (richiesti).
#   2. Installa Git e Python se mancanti (via winget).
#   3. Clona/aggiorna il repository in una cartella a scelta.
#   4. Crea il venv e installa le dipendenze Python.
#   5. Prova a installare il runtime GTK3 (serve a WeasyPrint per i
#      PDF); se fallisce, l'app resta comunque funzionante col
#      fallback HTML già previsto per i documenti (non è un errore).
#   6. Verifica che database.db sia presente (NON viene copiato in
#      automatico: va portato a mano da una chiavetta o da rete dal
#      Mac — non è mai stato nel repository, vedi CLAUDE.md).
#   7. Apre la porta 5002 in entrata sul Firewall di Windows.
#   8. Registra un'attività pianificata che avvia CaronteApp
#      all'accensione del PC (eseguita come SYSTEM: non richiede un
#      utente loggato), con riavvio automatico se il processo termina.
#
# Uso: aprire PowerShell "come amministratore" sul PC Windows che
# farà da server, poi:
#   powershell -ExecutionPolicy Bypass -File installa_server_windows.ps1
#
# Rieseguibile senza danni: ogni passo controlla prima se è già a
# posto (stesso principio delle migrazioni additive di app.py).

param(
    [string]$Cartella = "C:\CaronteApp",
    [string]$RepoUrl  = "https://github.com/robertodaltoe/caronteApp.git",
    [switch]$ImpedisciSospensione   # opt-in: cambia le impostazioni di
                                    # risparmio energetico del PC (vedi
                                    # step finale) — di default NON tocca
                                    # nulla, perché è un'impostazione di
                                    # sistema che riguarda tutto il PC,
                                    # non solo CaronteApp.
)

$ErrorActionPreference = 'Stop'

function Titolo($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Ok($t)      { Write-Host "  OK  $t" -ForegroundColor Green }
function Avviso($t)  { Write-Host "  ATTENZIONE  $t" -ForegroundColor Yellow }

# ── 0. Permessi amministratore ──────────────────────────────────────
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Questo script va eseguito come Amministratore." -ForegroundColor Red
    Write-Host "Tasto destro su PowerShell -> 'Esegui come amministratore', poi rilancia lo script." -ForegroundColor Red
    exit 1
}

# ── 1. Git e Python ──────────────────────────────────────────────────
Titolo "Strumenti di base (Git, Python)"

function Assicura-Comando($comando, $wingetId, $nome) {
    if (Get-Command $comando -ErrorAction SilentlyContinue) {
        Ok "$nome gia' installato"
        return
    }
    Avviso "$nome non trovato: installazione via winget..."
    winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements
    if (-not (Get-Command $comando -ErrorAction SilentlyContinue)) {
        Write-Host "$nome non risulta installato dopo winget. Installalo manualmente e rilancia lo script." -ForegroundColor Red
        exit 1
    }
    Ok "$nome installato"
}

Assicura-Comando "git" "Git.Git" "Git"
Assicura-Comando "python" "Python.Python.3.12" "Python"

# ── 2. Codice sorgente ───────────────────────────────────────────────
Titolo "Codice CaronteApp in $Cartella"

if (Test-Path (Join-Path $Cartella ".git")) {
    Ok "Repository gia' presente: aggiorno (git pull)"
    Push-Location $Cartella
    git pull --ff-only
    Pop-Location
} else {
    if (Test-Path $Cartella) {
        Write-Host "La cartella $Cartella esiste ma non e' un repository git. Scegli un'altra cartella con -Cartella oppure svuotala." -ForegroundColor Red
        exit 1
    }
    git clone $RepoUrl $Cartella
    Ok "Repository clonato"
}

# ── 3. Ambiente Python (venv + dipendenze) ──────────────────────────
Titolo "Ambiente Python"

Push-Location $Cartella

if (-not (Test-Path "venv\Scripts\python.exe")) {
    python -m venv venv
    Ok "venv creato"
} else {
    Ok "venv gia' presente"
}

& "venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
& "venv\Scripts\python.exe" -m pip install -r requirements.txt
Ok "Dipendenze Python installate"

# ── 4. GTK3 Runtime (per i PDF di WeasyPrint) ───────────────────────
Titolo "GTK3 Runtime (necessario per generare i PDF)"

$gtkGia = Get-ItemProperty "HKLM:\SOFTWARE\GTK3-Runtime Win64" -ErrorAction SilentlyContinue
if ($gtkGia) {
    Ok "GTK3 Runtime gia' installato"
} else {
    try {
        winget install --id tschoonj.GTKforWindowsRuntimeEnvironmentInstaller -e --accept-source-agreements --accept-package-agreements
        Ok "GTK3 Runtime installato"
    } catch {
        Avviso "Installazione automatica di GTK3 non riuscita."
        Avviso "Scaricalo a mano da: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases"
        Avviso "Senza GTK3 i documenti/PDF vengono comunque generati, ma in HTML invece che in PDF (fallback automatico gia' previsto, non un errore bloccante)."
    }
}

# ── 5. database.db ───────────────────────────────────────────────────
Titolo "Database"

if (Test-Path "database.db") {
    Ok "database.db presente"
} else {
    Avviso "database.db NON presente in $Cartella."
    Avviso "Non viene copiato automaticamente (non e' mai stato nel repository)."
    Avviso "Copialo a mano dal Mac (es. da una chiavetta o da una cartella di rete) in:"
    Avviso "  $Cartella\database.db"
    Avviso "Lo script continua comunque la configurazione, ma NON avviare il servizio prima di aver copiato il file:"
    Avviso "un avvio senza database.db ne creerebbe uno vuoto, diverso da quello reale."
}

# ── 6. Script di avvio dedicato (senza sync su Google Drive) ────────
Titolo "Script di avvio del server"

# Questo PC e' l'unica fonte del database (accesso diretto via LAN da
# tutti i client): a differenza di avvia_caronte.bat, NON deve fare
# sync_db.py scarica/carica con Google Drive ad ogni avvio/arresto,
# altrimenti i due meccanismi (LAN diretta + sync Drive) entrerebbero
# in conflitto sullo stesso file.
$avviaServerPath = Join-Path $Cartella "avvia_server_windows.bat"
@"
@echo off
REM Avvia CaronteApp come server permanente (accesso diretto via LAN,
REM nessun sync su Google Drive: questo PC e' l'unica fonte dati).
cd /d "%~dp0"
call venv\Scripts\activate.bat
:loop
python app.py
echo.
echo CaronteApp si e' fermata: riavvio tra 5 secondi (CTRL+C per uscire davvero)...
timeout /t 5 >nul
goto loop
"@ | Set-Content -Path $avviaServerPath -Encoding ASCII
Ok "Creato $avviaServerPath"

# ── 7. Firewall: porta 5002 in entrata ──────────────────────────────
Titolo "Firewall di Windows (porta 5002)"

$regolaEsistente = Get-NetFirewallRule -DisplayName "CaronteApp (5002)" -ErrorAction SilentlyContinue
if ($regolaEsistente) {
    Ok "Regola firewall gia' presente"
} else {
    New-NetFirewallRule -DisplayName "CaronteApp (5002)" -Direction Inbound -Protocol TCP -LocalPort 5002 -Action Allow | Out-Null
    Ok "Regola firewall creata (TCP 5002 in entrata consentito)"
}

# ── 8. Attivita' pianificata: avvio automatico all'accensione ──────
Titolo "Avvio automatico all'accensione del PC"

$nomeTask = "CaronteApp Server"
$taskEsistente = Get-ScheduledTask -TaskName $nomeTask -ErrorAction SilentlyContinue
if ($taskEsistente) {
    Ok "Attivita' pianificata gia' presente: la aggiorno"
    Unregister-ScheduledTask -TaskName $nomeTask -Confirm:$false
}

$azione   = New-ScheduledTaskAction -Execute $avviaServerPath -WorkingDirectory $Cartella
$trigger  = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $nomeTask -Action $azione -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
Ok "Attivita' pianificata '$nomeTask' creata: si avvia da sola all'accensione, gira come SYSTEM (non serve un utente loggato)"

# ── 9. Riepilogo ──────────────────────────────────────────────────
Titolo "Riepilogo"

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "Installazione completata." -ForegroundColor Green
Write-Host "Indirizzo da usare sugli altri PC della rete: http://$ip`:5002" -ForegroundColor Green
Write-Host ""
if (-not (Test-Path "database.db")) {
    Write-Host "RICORDA: copia database.db in $Cartella prima di avviare/riavviare il PC." -ForegroundColor Yellow
}
Write-Host "Il server partira' da solo al prossimo avvio del PC (attivita' pianificata '$nomeTask')." -ForegroundColor Green
Write-Host "Per avviarlo subito senza riavviare il PC: Start-ScheduledTask -TaskName '$nomeTask'" -ForegroundColor Green

if ($ImpedisciSospensione) {
    Titolo "Impostazioni di risparmio energetico (richiesto con -ImpedisciSospensione)"
    powercfg /change standby-timeout-ac 0
    powercfg /change monitor-timeout-ac 0
    Ok "Il PC non andra' piu' in sospensione mentre e' collegato alla corrente"
    Avviso "Lo schermo puo' comunque spegnersi: non influisce sul server, che resta attivo."
} else {
    Avviso "Impostazioni di risparmio energetico NON modificate."
    Avviso "Se questo PC puo' andare in sospensione, va disattivata a mano (Impostazioni > Alimentazione e batteria),"
    Avviso "oppure rilancia lo script con -ImpedisciSospensione."
}

Pop-Location
