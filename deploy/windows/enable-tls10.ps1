<#
  FALLBACK: reactivar TLS 1.0 (cliente) en SCHANNEL para hablar con SQL Server 2008 R2.
  Usar SOLO si no se puede parchear la BD (SP3 + KB3144114 dan TLS 1.2).
  Ejecutar como Administrador. Requiere reinicio. Documentar como excepción de seguridad:
  el servidor está en segmento interno con línea de vista únicamente a 192.168.2.115.
#>
$ErrorActionPreference = 'Stop'

$base = 'HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.0\Client'
New-Item -Path $base -Force | Out-Null
New-ItemProperty -Path $base -Name 'Enabled' -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $base -Name 'DisabledByDefault' -Value 0 -PropertyType DWord -Force | Out-Null
Write-Host "TLS 1.0 Client habilitado en SCHANNEL." -ForegroundColor Green

# Cipher suites legadas que usa SQL Server 2008 R2 (WS2022 las quita por defecto)
$ciphers = @(
    'TLS_RSA_WITH_AES_128_CBC_SHA',
    'TLS_RSA_WITH_AES_256_CBC_SHA',
    'TLS_RSA_WITH_3DES_EDE_CBC_SHA'
)
foreach ($c in $ciphers) {
    try { Enable-TlsCipherSuite -Name $c -ErrorAction Stop; Write-Host "  + $c" }
    catch { Write-Host "  ! no se pudo habilitar $c ($_)" -ForegroundColor Yellow }
}

Write-Host "`nReinicia el servidor y prueba:" -ForegroundColor Cyan
Write-Host "  cd C:\insevig\app; .\.venv\Scripts\python -m scripts.healthcheck" -ForegroundColor Yellow
