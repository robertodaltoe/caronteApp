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
#      all'accesso dell'utente (non come SYSTEM: Google Drive Desktop e' visibile solo nella sessione utente) (non richiede un
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

function Trovato($comando) {
    # Get-Command da solo non basta per "python": se Python non e'
    # installato, Windows registra comunque un python.exe fittizio
    # (alias di esecuzione app -> apre il Microsoft Store) che risulta
    # "trovato" ma non esegue nulla di vero. Verifica quindi anche che
    # il comando risponda davvero a --version.
    $cmd = Get-Command $comando -ErrorAction SilentlyContinue
    if (-not $cmd) { return $false }
    try {
        $out = & $comando --version 2>&1
        return ($LASTEXITCODE -eq 0 -and $out -match '\d')
    } catch {
        return $false
    }
}

function Assicura-Comando($comando, $wingetId, $nome) {
    if (Trovato $comando) {
        Ok "$nome gia' installato"
        return
    }
    Avviso "$nome non trovato (o e' solo l'alias fittizio del Microsoft Store): installazione via winget..."
    winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements
    if (-not (Trovato $comando)) {
        Write-Host "$nome non risulta installato dopo winget." -ForegroundColor Red
        if ($comando -eq 'python') {
            Write-Host "Se il problema persiste, disattiva l'alias fittizio: Impostazioni > App > Impostazioni app avanzate > Alias di esecuzione app > disattiva 'python.exe' e 'python3.exe', poi rilancia lo script." -ForegroundColor Red
        }
        Write-Host "Dopo aver installato/corretto $nome, chiudi e riapri PowerShell come amministratore prima di rilanciare lo script (serve ad aggiornare il PATH)." -ForegroundColor Red
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
        if ($LASTEXITCODE -ne 0) { throw "winget non ha trovato/installato il pacchetto" }
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

# Il server gira con l'utente che esegue questo script (non come SYSTEM):
# Google Drive Desktop monta l'unita' G: solo nella sessione dell'utente
# loggato, SYSTEM non la vede e il sync con Drive salterebbe in silenzio.
# Conseguenza: parte all'accesso di quell'utente, quindi dopo un riavvio
# serve l'accesso automatico a Windows (vedi riepilogo finale).
$utenteServer = "$env:USERDOMAIN\$env:USERNAME"
$azione   = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -NoProfile -Command `"& '$avviaServerPath'`"" -WorkingDirectory $Cartella
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $utenteServer
$principal = New-ScheduledTaskPrincipal -UserId $utenteServer -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $nomeTask -Action $azione -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
Ok "Attivita' pianificata '$nomeTask' creata: si avvia da sola all'accesso di $utenteServer (Drive richiede la sessione utente)"

# ── 8b. Aggiornamento automatico del codice da GitHub ───────────────
# Ogni 15 minuti confronta la versione locale con origin/main; se
# diversa, scarica il codice nuovo e riavvia il server (fermando e
# rifacendo ripartire l'attivita' pianificata sopra, che rilegge tutto
# da zero). Se trova modifiche locali non previste in questa cartella
# (non dovrebbe mai succedere: e' una copia solo per il server, non un
# posto dove si lavora a mano) si ferma senza toccarle, e lo segnala
# nel log, invece di scartarle in silenzio.
Titolo "Aggiornamento automatico del codice"

$aggiornaPath = Join-Path $Cartella "aggiorna_e_riavvia_windows.ps1"
@'
param([string]$Cartella = "C:\CaronteApp")
$log = Join-Path $Cartella "aggiornamento.log"
function Scrivi($t) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $t" | Add-Content -Path $log }

Push-Location $Cartella
try {
    git fetch origin main *> $null
    $locale = git rev-parse HEAD
    $remoto = git rev-parse origin/main
    if ($locale -eq $remoto) {
        exit 0   # nessuna novita': niente da scrivere nel log ad ogni giro
    }
    if (git status --porcelain) {
        Scrivi "Trovate modifiche locali non previste in $Cartella: aggiornamento SALTATO per sicurezza. Verificare a mano."
        exit 1
    }
    Scrivi "Nuova versione disponibile ($($locale.Substring(0,7)) -> $($remoto.Substring(0,7))): aggiorno."
    git pull --ff-only *>> $log
    & "venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
    Stop-ScheduledTask -TaskName "CaronteApp Server" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-ScheduledTask -TaskName "CaronteApp Server"
    Scrivi "Codice aggiornato e server riavviato."
} catch {
    Scrivi "Errore durante l'aggiornamento automatico: $_"
} finally {
    Pop-Location
}
'@ | Set-Content -Path $aggiornaPath -Encoding UTF8
Ok "Creato $aggiornaPath"

$nomeTaskUpdate = "CaronteApp AutoUpdate"
if (Get-ScheduledTask -TaskName $nomeTaskUpdate -ErrorAction SilentlyContinue) {
    Ok "Attivita' di aggiornamento gia' presente: la aggiorno"
    Unregister-ScheduledTask -TaskName $nomeTaskUpdate -Confirm:$false
}

$azioneUpd   = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$aggiornaPath`" -Cartella `"$Cartella`"" -WorkingDirectory $Cartella
$triggerUpd  = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
$principalUpd = New-ScheduledTaskPrincipal -UserId $utenteServer -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $nomeTaskUpdate -Action $azioneUpd -Trigger $triggerUpd -Principal $principalUpd -Settings $settings | Out-Null
Ok "Attivita' pianificata '$nomeTaskUpdate' creata: controlla GitHub ogni 15 minuti, aggiorna e riavvia da sola se trova novita'"
Ok "Log degli aggiornamenti: $Cartella\aggiornamento.log"

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
Write-Host "IMPORTANTE: il server parte all'accesso a Windows di $utenteServer. Per farlo ripartire da solo dopo un riavvio, imposta l'accesso automatico (Win+R, netplwiz, togli la spunta a 'Per utilizzare questo computer...') e blocca lo schermo invece di disconnetterti." -ForegroundColor Yellow
Write-Host "Il server partira' da solo al prossimo accesso (attivita' pianificata '$nomeTask')." -ForegroundColor Green
Write-Host "Per avviarlo subito senza riavviare il PC: Start-ScheduledTask -TaskName '$nomeTask'" -ForegroundColor Green
Write-Host "Il codice si aggiorna da solo da GitHub ogni 15 minuti (attivita' '$nomeTaskUpdate'); per forzare subito un controllo: Start-ScheduledTask -TaskName '$nomeTaskUpdate'" -ForegroundColor Green

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
