<#
  Mini-servicio "webhook": escucha en http://<NAS>:9000/deploy los POST que
  manda GitHub cuando hay push a main, y dispara el despliegue
  (deploy-nas.ps1 -SoloActualizar).

  Alternativa mas simple que el self-hosted runner de Actions. Menos robusto
  (sin logs bonitos, sin reintentos), pero no depende de nadie.

  ── Instalar en el NAS (como Administrador) ────────────────────────────────
    # 1. Elegir un secreto y guardarlo:
    setx INSEVIG_WEBHOOK_SECRET "un-secreto-largo-y-random" /M
    # 2. Registrar como servicio con NSSM:
    C:\insevig\tools\nssm.exe install insevig-webhook `
        "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" `
        "-NoProfile -ExecutionPolicy Bypass -File E:\Sistemas_Dev\NOMINA_ROLES_SISTEMA_INSEVIG\deploy\windows\webhook-deploy.ps1"
    C:\insevig\tools\nssm.exe set insevig-webhook Start SERVICE_AUTO_START
    C:\insevig\tools\nssm.exe set insevig-webhook AppStdout C:\insevig\logs\webhook.out.log
    C:\insevig\tools\nssm.exe set insevig-webhook AppStderr C:\insevig\logs\webhook.err.log
    Start-Service insevig-webhook
    New-NetFirewallRule -DisplayName "INSEVIG Webhook 9000" -Direction Inbound -Protocol TCP -LocalPort 9000 -Action Allow
    # 3. En GitHub: Settings -> Webhooks -> Add webhook
    #    Payload URL:  http://<IP-publica-o-tunel>:9000/deploy
    #    Content type: application/json
    #    Secret:       el mismo INSEVIG_WEBHOOK_SECRET
    #    Events:       Just the push event
  ──────────────────────────────────────────────────────────────────────────
#>
[CmdletBinding()]
param(
    [int]$Puerto   = 9000,
    [string]$Rama  = 'refs/heads/main',
    [string]$Script = 'E:\Sistemas_Dev\NOMINA_ROLES_SISTEMA_INSEVIG\deploy\windows\deploy-nas.ps1'
)
$ErrorActionPreference = 'Stop'
$secret = $env:INSEVIG_WEBHOOK_SECRET
if (-not $secret) { throw "Falta la variable de entorno INSEVIG_WEBHOOK_SECRET" }

function Test-Firma($body, $sigHeader) {
    if (-not $sigHeader) { return $false }
    $key  = [Text.Encoding]::UTF8.GetBytes($secret)
    $hmac = [Security.Cryptography.HMACSHA256]::new($key)
    $hash = ($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($body)) | ForEach-Object { $_.ToString('x2') }) -join ''
    $expected = "sha256=$hash"
    # comparacion en tiempo constante
    $a = [Text.Encoding]::ASCII.GetBytes($expected); $b = [Text.Encoding]::ASCII.GetBytes($sigHeader)
    if ($a.Length -ne $b.Length) { return $false }
    $diff = 0; for ($i = 0; $i -lt $a.Length; $i++) { $diff = $diff -bor ($a[$i] -bxor $b[$i]) }
    return ($diff -eq 0)
}

$listener = [Net.HttpListener]::new()
$listener.Prefixes.Add("http://+:$Puerto/")
$listener.Start()
Write-Host "webhook escuchando en :$Puerto/deploy" -ForegroundColor Green

while ($listener.IsListening) {
    $ctx = $listener.GetContext()
    $req = $ctx.Request; $res = $ctx.Response
    try {
        if ($req.Url.AbsolutePath -ne '/deploy' -or $req.HttpMethod -ne 'POST') {
            $res.StatusCode = 404; $res.Close(); continue
        }
        $body = [IO.StreamReader]::new($req.InputStream, $req.ContentEncoding).ReadToEnd()
        if (-not (Test-Firma $body $req.Headers['X-Hub-Signature-256'])) {
            Write-Host "$(Get-Date -f s)  firma invalida, ignorado" -ForegroundColor Yellow
            $res.StatusCode = 401; $res.Close(); continue
        }
        $evt = $req.Headers['X-GitHub-Event']
        $payload = $body | ConvertFrom-Json
        if ($evt -eq 'push' -and $payload.ref -eq $Rama) {
            Write-Host "$(Get-Date -f s)  push a main -> desplegando..." -ForegroundColor Cyan
            $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $Script -SoloActualizar 2>&1
            $out | Out-Host
            $res.StatusCode = 200
            $bytes = [Text.Encoding]::UTF8.GetBytes("deploy lanzado`n")
            $res.OutputStream.Write($bytes, 0, $bytes.Length)
        } else {
            $res.StatusCode = 202   # aceptado pero no aplica (ping, otra rama, etc.)
        }
    } catch {
        Write-Host "$(Get-Date -f s)  ERROR: $_" -ForegroundColor Red
        $res.StatusCode = 500
    } finally {
        $res.Close()
    }
}
