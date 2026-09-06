@echo off
REM ---------------------------------------------------------------------------
REM Mapea las unidades de red del servidor NAS INSEVIG (192.168.2.181).
REM
REM   X:  \\192.168.2.181\Sistemas_Dev$    codigo/proyecto Reflex  (solo GRP_DEVS)
REM   Y:  \\192.168.2.181\Apps_Empresa$    lanzadores .exe          (RRHH/GENERAL: solo lectura)
REM
REM Ambos son shares OCULTOS (terminan en $): no aparecen navegando "Red".
REM Para X: hace falta una cuenta Windows del servidor miembro de GRP_DEVS
REM (es grupo de trabajo, no dominio: Windows pedira usuario y clave).
REM
REM Personal de RRHH/general: NO necesitan este .bat. Ejecutan directamente
REM   \\192.168.2.181\Apps_Empresa$\Lanzadores\INSEVIG_Demo.exe
REM ---------------------------------------------------------------------------

net use Y: \\192.168.2.181\Apps_Empresa$ /persistent:yes
net use X: \\192.168.2.181\Sistemas_Dev$ /persistent:yes

echo.
net use
pause
