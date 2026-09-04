"""CRUD de empleados (RPEMPLEA). Porta `empleados/SISTEMA_GESTION_EMPLEADOS_10.pyw`.

Escrituras SOLO a SQL Server (login RW), con vista previa y `AuditWriter`.
Concurrencia optimista: hash de los campos editables al abrir el editor; si cambió
al guardar, se rechaza.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from core.audit.writer import audit_scope
from core.config import get_settings
from core.db import sqlserver, supabase_client
from core.db.health import FUENTE_SUPABASE
from core.utils import a_float, normalizar_cedula

# Campos editables de RPEMPLEA. Organizados como el legado
# (`SISTEMA_GESTION_EMPLEADOS_10.pyw`): pestaña -> [(subsección, campos)].
# Nombres de columna EXACTOS del legado.
SECCIONES: dict[str, list[tuple[str, tuple[str, ...]]]] = {
    "Datos generales": [
        ("Información personal", (
            "NOMBRES", "APELLIDOS", "CEDULA", "SEXO", "ESTADO_CI",
            "FECHA_NAC", "LUGAR_NAC", "NACIONAL", "CONYUGUE",
        )),
        ("Ubicación", ("DIRECCION", "PROVINCIA", "CANTON", "PARROQUIA")),
        ("Contacto", ("TELEFONO", "RPCAM", "emp_mail")),
        ("Información laboral", (
            "FECHA_ING", "FECHA_SAL", "DEPTO", "CARGO", "SECCION",
            "ESTADO", "TIPO_TRA", "ACTIVIDAD",
        )),
        ("Estudios", ("PRIMARIA", "SECUNDARIA", "EST_SUP", "TITULO", "ANIO_EST")),
    ],
    "Ingresos / descuentos": [
        ("Sueldo y beneficios de ley", (
            "SUELDO", "BONIFI", "COMPEN", "TRANSP", "HOR25", "HOR50", "HOR100",
        )),
        ("Acumulados de beneficios sociales", ("DECIMO3", "DECIMO4", "VACACION", "FONRESER")),
        ("Rol extra", (
            "MOVILIZA", "LUNCH", "ANTICIPO", "DESCUENTO", "ING_EXTRA", "DCT_EXTRA", "CONCEPTO",
        )),
        ("Parámetros de nómina", ("CAT_PROYECT_7", "CAT_PROYECT_8", "RPCAM2")),
    ],
    "Otros datos": [
        ("Generales", ("INCL_ROL", "INCL_BAN", "CARGAS", "ULTLIQ", "ULTDIATRA", "DIAS_TRA",
                       "TIP_SAN", "TIPO_PGO")),
        ("Cuentas contables", ("CODCTA", "CTADPT", "CTAAUX")),
        ("Información bancaria", ("RUTA4", "CTA_CTE", "CTA_AHO")),
    ],
    "Certificados / familiares": [
        ("Familiares", ("NOM_FAM", "DIR_FAM", "TEL_FAM")),
        ("No familiares", ("NOM_NO_FAM", "DIR_NO_FAM", "TEL_NO_FAM")),
    ],
    "Referencias": [
        ("Datos referenciales", (
            "CED_MIL", "EDAD", "IDVOTA", "LICCOND", "CODIESS", "ID_CONADIS", "OBSERV",
        )),
        ("Servicios", (
            "RPCAM5", "CONTINS", "RPCAM3", "RPCAM4",
            "certificados", "reentrenamiento", "vacuna", "FZA_PUB", "SER_MIL",
        )),
        ("Información adicional", ("CERTVINF", "MANIOBRAS", "NUM_AFIL")),
    ],
}

# Compat: pestaña -> tupla plana de campos (lo usan los PDF de ficha/documentos).
GRUPOS: dict[str, tuple[str, ...]] = {
    tab: tuple(c for _sub, campos in secs for c in campos)
    for tab, secs in SECCIONES.items()
}
CAMPOS_EDITABLES: tuple[str, ...] = tuple(c for cs in GRUPOS.values() for c in cs)

# Etiquetas legibles para el formulario web (las que no están usan el nombre crudo).
ETIQUETAS: dict[str, str] = {
    "emp_mail": "Email", "RPCAM": "2do teléfono", "TIPO_TRA": "Tipo de empleado",
    "ESTADO_CI": "Estado civil", "LUGAR_NAC": "Lugar nac.", "FECHA_NAC": "Fecha nac.",
    "FECHA_ING": "Fecha ingreso", "FECHA_SAL": "Fecha salida", "NACIONAL": "Nacionalidad",
    "BONIFI": "Bonificación", "COMPEN": "Compensación", "TRANSP": "Transporte",
    "HOR25": "Horas 25%", "HOR50": "Horas 50%", "HOR100": "Horas 100%",
    "DECIMO3": "Décimo 3ro", "DECIMO4": "Décimo 4to", "FONRESER": "Fdo. reserva",
    "MOVILIZA": "Movilización", "ING_EXTRA": "Ing. extra", "DCT_EXTRA": "Dct. extra",
    "CAT_PROYECT_7": "Décimo 3ro se paga aparte", "CAT_PROYECT_8": "Décimo 4to se paga aparte",
    "RPCAM2": "Aporta IESS cónyuge (3.41%)", "INCL_ROL": "Incluir en el rol",
    "INCL_BAN": "Acreditar al banco", "ULTLIQ": "Últ. liquidación",
    "ULTDIATRA": "Últ. día trabajado", "DIAS_TRA": "Días trab.", "TIP_SAN": "Grupo sanguíneo",
    "TIPO_PGO": "Período de pago", "CODCTA": "Código cta.", "CTADPT": "Cta. depto.",
    "CTAAUX": "Cta. auxiliar", "RUTA4": "Banco", "CTA_CTE": "Cta. corriente",
    "CTA_AHO": "Cta. ahorros", "NOM_FAM": "Familiar — nombres", "DIR_FAM": "Familiar — dirección",
    "TEL_FAM": "Familiar — teléfonos", "NOM_NO_FAM": "No familiar — nombres",
    "DIR_NO_FAM": "No familiar — dirección", "TEL_NO_FAM": "No familiar — teléfonos",
    "CED_MIL": "Cédula militar", "IDVOTA": "Nro cert. votación", "LICCOND": "Licencia conducir",
    "CODIESS": "Código IESS", "ID_CONADIS": "Carnet Conadis", "OBSERV": "Visita domiciliaria",
    "EST_SUP": "Universidad", "ANIO_EST": "Años estudio", "RPCAM5": "Tipo de servicio",
    "CONTINS": "Contrato inspectoría", "RPCAM3": "GIPASE", "RPCAM4": "AFIS",
    "FZA_PUB": "Miembro activo Fuerza Pública", "SER_MIL": "Realizó servicio militar",
    "CERTVINF": "Cert. violencia intrafamiliar", "NUM_AFIL": "No. afiliación IESS",
}

CAMPOS_NUMERICOS = frozenset({
    "SUELDO", "BONIFI", "COMPEN", "TRANSP", "HOR25", "HOR50", "HOR100",
    "DECIMO3", "DECIMO4", "VACACION", "FONRESER", "MOVILIZA", "LUNCH", "ANTICIPO",
    "DESCUENTO", "ING_EXTRA", "DCT_EXTRA", "CARGAS", "DIAS_TRA", "EDAD", "ANIO_EST",
})
# 'S'/'N' como texto (RPEMPLEA.INCL_ROL / INCL_BAN)
CAMPOS_SN = frozenset({"INCL_ROL", "INCL_BAN"})
# '1'/'0' como texto (columnas varchar genéricas reutilizadas como flags de nómina)
CAMPOS_FLAG_TXT = frozenset({"CAT_PROYECT_7", "CAT_PROYECT_8", "RPCAM2"})
# 1/0 como entero (estudios / servicio militar)
CAMPOS_FLAG_INT = frozenset({"PRIMARIA", "SECUNDARIA", "EST_SUP", "FZA_PUB", "SER_MIL"})

# Combos con catálogo fijo: campo -> [(código, etiqueta)]
CAMPOS_COMBO: dict[str, list[tuple[str, str]]] = {
    "SEXO": [("1", "Masculino"), ("2", "Femenino")],
    "ESTADO_CI": [
        ("1", "Casado"), ("2", "Soltero"), ("3", "Divorciado"), ("4", "Viudo"), ("5", "Unión libre"),
    ],
    "ESTADO": [("ACT", "Activo"), ("LIQ", "Liquidado"), ("SUS", "Suspendido")],
    "TIPO_TRA": [("1", "Empleado"), ("2", "Código 2"), ("3", "Obrero")],
    "TIPO_PGO": [("1", "1"), ("2", "2"), ("3", "3")],
    "TIP_SAN": [(x, x) for x in ("O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-")],
}

# Combos que se llenan desde DBTABLAS: campo -> TIPO
CAMPOS_CATALOGO: dict[str, str] = {"DEPTO": "DPT", "CARGO": "FNC", "SECCION": "SEC", "RUTA4": "BAN"}

# Catálogos de DBTABLAS a cargar (TIPO -> etiqueta). El legado real usa FNC/SEC/DPT/BAN.
CATALOGOS = {"FNC": "cargos", "SEC": "secciones", "DPT": "departamentos", "BAN": "bancos"}


@dataclass
class Empleado:
    empleado: str
    campos: dict[str, object]
    token: str  # hash de concurrencia
    creado_por: str = ""
    fecha_crea: str = ""
    mod_por: str = ""
    fecha_mod: str = ""


def _token(campos: dict) -> str:
    payload = json.dumps({k: str(campos.get(k, "")) for k in CAMPOS_EDITABLES}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ── Lectura ──────────────────────────────────────────────────────────────────


# Filtro de estado para la lista: etiqueta -> códigos RPEMPLEA.ESTADO
_ESTADOS_FILTRO = {
    "ACTIVOS": ("ACT",),
    "INACTIVOS": ("LIQ", "SUS"),
    "TODOS": (),
}


def buscar(
    texto: str, fuente: str, *, solo_activos: bool = False, estado: str = "", limite: int = 300
) -> list[dict]:
    texto = texto.strip()
    if solo_activos and not estado:
        estado = "ACTIVOS"
    codigos = _ESTADOS_FILTRO.get(estado.upper(), ())
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        q = sb.table("rpemplea").select("empleado,apellidos,nombres,cedula,cargo,estado").eq("codemp", "10")
        if len(codigos) == 1:
            q = q.eq("estado", codigos[0])
        elif len(codigos) > 1:
            q = q.in_("estado", list(codigos))
        if texto:
            q = (
                q.eq("empleado", texto)
                if texto.isdigit()
                else q.or_(f"apellidos.ilike.%{texto}%,nombres.ilike.%{texto}%")
            )
        filas = q.order("apellidos").limit(limite).execute().data or []
        return [
            {
                "empleado": str(r["empleado"]).strip(),
                "apellidos_nombres": f"{(r.get('apellidos') or '').strip()} {(r.get('nombres') or '').strip()}".strip(),
                "cedula": normalizar_cedula(r.get("cedula")),
                "cargo": str(r.get("cargo") or ""),
                "estado": r.get("estado") or "",
            }
            for r in filas
        ]
    flt = get_settings().sqlserver_filter
    cond = flt
    params: list = []
    if len(codigos) == 1:
        cond += " AND [ESTADO] = ?"
        params.append(codigos[0])
    elif len(codigos) > 1:
        cond += " AND [ESTADO] IN (" + ",".join("?" * len(codigos)) + ")"
        params.extend(codigos)
    if texto:
        if texto.isdigit():
            cond += " AND [EMPLEADO] = ?"
            params.append(texto)
        else:
            cond += " AND ([APELLIDOS] LIKE ? OR [NOMBRES] LIKE ?)"
            params += [f"%{texto}%", f"%{texto}%"]
    filas = sqlserver.filas(
        f"""SELECT TOP {limite} [EMPLEADO],[APELLIDOS],[NOMBRES],[CEDULA],[CARGO],[ESTADO]
            FROM [insevig].[dbo].[RPEMPLEA] WHERE {cond} ORDER BY [APELLIDOS]""",
        tuple(params),
    )
    return [
        {
            "empleado": str(r["EMPLEADO"]).strip(),
            "apellidos_nombres": f"{(r.get('APELLIDOS') or '').strip()} {(r.get('NOMBRES') or '').strip()}".strip(),
            "cedula": normalizar_cedula(r.get("CEDULA")),
            "cargo": str(r.get("CARGO") or ""),
            "estado": r.get("ESTADO") or "",
        }
        for r in filas
    ]


def buscar_avanzado(
    fuente: str, *, apellidos: str = "", nombres: str = "", cedula: str = "",
    estado: str = "", depto: str = "", cargo: str = "", limite: int = 1000,
) -> list[dict]:
    """Búsqueda por múltiples criterios (como el diálogo 'Búsqueda Avanzada' del
    legado). Devuelve filas anchas con nombre de cargo/depto, sueldo, tel, email."""
    apellidos, nombres, cedula = apellidos.strip(), nombres.strip(), cedula.strip()
    depto, cargo = depto.strip(), cargo.strip()
    est = {"ACTIVO": "ACT", "LIQUIDADO": "LIQ", "SUSPENDIDO": "SUS", "ACT": "ACT",
           "LIQ": "LIQ", "SUS": "SUS"}.get(estado.upper(), "")
    cat = catalogos(fuente)
    n_cargo = {x["codigo"]: x["nombre"] for x in cat.get("FNC", [])}
    n_depto = {x["codigo"]: x["nombre"] for x in cat.get("DPT", [])}

    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        q = sb.table("rpemplea").select(
            "empleado,apellidos,nombres,cedula,cargo,depto,sueldo,telefono,emp_mail,estado"
        ).eq("codemp", "10")
        if apellidos:
            q = q.ilike("apellidos", f"%{apellidos}%")
        if nombres:
            q = q.ilike("nombres", f"%{nombres}%")
        if cedula.isdigit():
            q = q.eq("cedula", int(cedula))
        if est:
            q = q.eq("estado", est)
        if depto:
            q = q.eq("depto", depto)
        if cargo:
            q = q.eq("cargo", cargo)
        filas = q.order("apellidos").limit(limite).execute().data or []
        get = lambda r, k: r.get(k)  # noqa: E731
    else:
        flt = get_settings().sqlserver_filter
        cond = flt
        params: list = []
        if apellidos:
            cond += " AND UPPER([APELLIDOS]) LIKE UPPER(?)"
            params.append(f"%{apellidos}%")
        for parte in nombres.split():
            cond += " AND UPPER([NOMBRES]) LIKE UPPER(?)"
            params.append(f"%{parte}%")
        if cedula:
            cond += " AND [CEDULA] = ?"
            params.append(cedula)
        if est:
            cond += " AND [ESTADO] = ?"
            params.append(est)
        if depto:
            cond += " AND [DEPTO] = ?"
            params.append(depto)
        if cargo:
            cond += " AND [CARGO] = ?"
            params.append(cargo)
        filas = sqlserver.filas(
            f"""SELECT TOP {limite} [EMPLEADO],[APELLIDOS],[NOMBRES],[CEDULA],[CARGO],[DEPTO],
                       [SUELDO],[TELEFONO],[emp_mail],[ESTADO]
                FROM [insevig].[dbo].[RPEMPLEA] WHERE {cond} ORDER BY [APELLIDOS],[NOMBRES]""",
            tuple(params),
        )
        get = lambda r, k: r.get(k.upper()) or r.get(k)  # noqa: E731
    out = []
    for r in filas:
        cg = str(get(r, "cargo") or "").strip()
        dp = str(get(r, "depto") or "").strip()
        out.append({
            "empleado": str(get(r, "empleado") or "").strip(),
            "apellidos": (get(r, "apellidos") or "").strip(),
            "nombres": (get(r, "nombres") or "").strip(),
            "cedula": normalizar_cedula(get(r, "cedula")),
            "cargo": cg, "cargo_nombre": n_cargo.get(cg, ""),
            "depto": dp, "depto_nombre": n_depto.get(dp, ""),
            "sueldo": a_float(get(r, "sueldo")),
            "telefono": str(get(r, "telefono") or ""),
            "email": str(get(r, "emp_mail") or ""),
            "estado": str(get(r, "estado") or ""),
        })
    return out


def obtener(empleado: str, fuente: str) -> Empleado | None:
    cols = ",".join(f"[{c}]" for c in CAMPOS_EDITABLES)
    aud = "[creado_por],[fecha_crea],[mod_por],[fecha_mod]"
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        r = sb.table("rpemplea").select("*").eq("codemp", "10").eq("empleado", str(empleado)).limit(1).execute()
        if not r.data:
            return None
        row = r.data[0]
    else:
        flt = get_settings().sqlserver_filter
        filas = sqlserver.filas(
            f"SELECT {cols},{aud} FROM [insevig].[dbo].[RPEMPLEA] WHERE {flt} AND [EMPLEADO] = ?",
            (str(empleado),),
        )
        if not filas:
            return None
        row = filas[0]
    low = {str(k).lower(): v for k, v in row.items()}  # RPEMPLEA vs supabase: distinta capitalización
    campos = {c: low.get(c.lower()) for c in CAMPOS_EDITABLES}
    return Empleado(
        empleado=str(empleado).strip(),
        campos=campos,
        token=_token(campos),
        creado_por=str(row.get("creado_por") or row.get("CREADO_POR") or ""),
        fecha_crea=str(row.get("fecha_crea") or row.get("FECHA_CREA") or "")[:19],
        mod_por=str(row.get("mod_por") or row.get("MOD_POR") or ""),
        fecha_mod=str(row.get("fecha_mod") or row.get("FECHA_MOD") or "")[:19],
    )


# ── Escritura (siempre SQL Server) ───────────────────────────────────────────


class ConflictoConcurrencia(RuntimeError):
    """Otro usuario modificó el registro desde que se abrió el editor."""


def _norm_valor(k: str, v: object) -> object:
    """Convierte el valor del formulario al tipo/codificación de la columna RPEMPLEA."""
    if k in CAMPOS_NUMERICOS:
        return a_float(v)
    s = "" if v is None else str(v).strip()
    if k in CAMPOS_SN:
        return "S" if s in ("S", "s", "1", "true", "True") else "N"
    if k in CAMPOS_FLAG_TXT:
        return "1" if s in ("1", "S", "true", "True") else "0"
    if k in CAMPOS_FLAG_INT:
        return 1 if s in ("1", "S", "true", "True") else 0
    return None if s == "" else s


def _normalizar(campos: dict) -> dict:
    return {k: _norm_valor(k, campos.get(k)) for k in CAMPOS_EDITABLES if k in campos}


def actualizar(empleado: str, campos: dict, token_previo: str, *, usuario: str, roles: set[str]) -> None:
    actual = obtener(empleado, "sqlserver")
    if actual is None:
        raise LookupError(f"Empleado {empleado} no existe")
    if actual.token != token_previo:
        raise ConflictoConcurrencia(
            "Otro usuario modificó este empleado. Recarga el editor y vuelve a intentar."
        )
    nuevos = _normalizar(campos)
    flt = get_settings().sqlserver_filter
    sets = ", ".join(f"[{c}] = ?" for c in nuevos)
    with audit_scope(
        "empleados", "editar", usuario=usuario, roles=roles,
        target_table="RPEMPLEA", target_key=empleado,
        antes=actual.campos, after=nuevos,
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE [insevig].[dbo].[RPEMPLEA] SET {sets}, [mod_por] = ?, [fecha_mod] = GETDATE() "
            f"WHERE [EMPLEADO] = ? AND {flt}",
            (*nuevos.values(), usuario, empleado),
        )
        conn.commit()


def crear(campos: dict, *, usuario: str, roles: set[str]) -> str:
    nuevos = _normalizar(campos)
    empleado = str(campos.get("EMPLEADO") or "").strip()
    cedula = str(campos.get("CEDULA") or "").strip()
    if not empleado:
        raise ValueError("Falta el código de empleado")
    if not cedula:
        raise ValueError("Falta la cédula")
    flt = get_settings().sqlserver_filter
    dup = sqlserver.filas(
        f"SELECT [EMPLEADO],[CEDULA] FROM [insevig].[dbo].[RPEMPLEA] "
        f"WHERE {flt} AND ([EMPLEADO] = ? OR [CEDULA] = ?)",
        (empleado, cedula),
    )
    for d in dup:
        if str(d.get("EMPLEADO") or "").strip() == empleado:
            raise ValueError(f"Ya existe un empleado con el código {empleado}")
        raise ValueError(f"Ya existe un empleado con la cédula {cedula}")
    cols = ["EMPLEADO", "CODEMP", "CODSUC", *nuevos.keys(), "creado_por", "fecha_crea"]
    vals: list = [empleado, "10", "10", *nuevos.values(), usuario]
    placeholders = ", ".join(["?"] * (len(vals)) + ["GETDATE()"])
    with audit_scope(
        "empleados", "crear", usuario=usuario, roles=roles,
        target_table="RPEMPLEA", target_key=empleado, after=nuevos,
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO [insevig].[dbo].[RPEMPLEA] ({', '.join(cols)}) VALUES ({placeholders})",
            tuple(vals),
        )
        conn.commit()
    return empleado


def eliminar(empleado: str, *, usuario: str, roles: set[str]) -> None:
    actual = obtener(empleado, "sqlserver")
    if actual is None:
        raise LookupError(f"Empleado {empleado} no existe")
    flt = get_settings().sqlserver_filter
    with audit_scope(
        "empleados", "eliminar", usuario=usuario, roles=roles,
        target_table="RPEMPLEA", target_key=empleado, antes=actual.campos,
    ), sqlserver.conexion(write=True) as conn:
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM [insevig].[dbo].[RPEMPLEA] WHERE [EMPLEADO] = ? AND {flt}",
            (empleado,),
        )
        conn.commit()


def job_carga_masiva(ctx, filas: list[dict], *, usuario: str, roles: set[str]) -> None:
    """Aplica una carga masiva fila por fila; audita cada una; deja un xlsx de resultados."""
    from core import storage
    from core.excel.empleados_builders import reporte_resultados

    resultados: list[dict] = []
    total = len(filas)
    for i, fila in enumerate(filas, 1):
        if ctx.cancelado:
            break
        cod = str(fila.get("EMPLEADO") or "").strip()
        try:
            actual = obtener(cod, "sqlserver")
            if actual is None:
                resultados.append({"empleado": cod, "ok": False, "detalle": "no existe"})
            else:
                actualizar(cod, fila, actual.token, usuario=usuario, roles=roles)
                resultados.append({"empleado": cod, "ok": True, "detalle": f"{len(fila) - 1} campos"})
        except Exception as e:  # noqa: BLE001
            resultados.append({"empleado": cod, "ok": False, "detalle": str(e)[:200]})
        ctx.progreso(i, total, f"{i}/{total} · OK {sum(r['ok'] for r in resultados)}")
    ruta = storage.guardar(ctx.job_id, "CARGA_MASIVA_RESULTADO.xlsx", reporte_resultados(resultados))
    ctx.set_resultado(str(ruta))
    ok = sum(r["ok"] for r in resultados)
    ctx.progreso(total, total, f"Terminado: {ok} OK, {len(resultados) - ok} con error")


def catalogos(fuente: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        for tipo in CATALOGOS:
            r = (
                sb.table("dbtablas")
                .select("codigo,nombre")
                .eq("tipo", tipo)
                .eq("codemp", "10")
                .execute()
            )
            out[tipo] = [
                {"codigo": str(x["codigo"]).strip(), "nombre": (x.get("nombre") or "").strip()}
                for x in (r.data or [])
            ]
        return out
    for tipo in CATALOGOS:
        filas = sqlserver.filas(
            "SELECT CODIGO, NOMBRE FROM dbo.DBTABLAS WHERE TIPO = ? AND CODEMP='10'", (tipo,)
        )
        out[tipo] = [{"codigo": str(r["CODIGO"]).strip(), "nombre": (r["NOMBRE"] or "").strip()} for r in filas]
    return out


def nombres_catalogo(fuente: str, pares: list[tuple[str, str]]) -> dict[str, str]:
    """Resuelve [(tipo, codigo)] -> {codigo: nombre}. Para mostrar el nombre del
    departamento/cargo/sección/banco junto al código en la ficha.
    """
    pares = [(t, str(c).strip()) for t, c in pares if str(c).strip()]
    if not pares:
        return {}
    out: dict[str, str] = {}
    if fuente == FUENTE_SUPABASE:
        sb = supabase_client.get_client()
        for tipo, cod in pares:
            r = (
                sb.table("dbtablas").select("nombre")
                .eq("tipo", tipo).eq("codemp", "10").eq("codigo", cod)
                .limit(1).execute()
            )
            if r.data:
                out[cod] = (r.data[0].get("nombre") or "").strip()
        return out
    for tipo, cod in pares:
        filas = sqlserver.filas(
            "SELECT NOMBRE FROM dbo.DBTABLAS WHERE TIPO = ? AND CODIGO = ? AND CODEMP='10'",
            (tipo, cod),
        )
        if filas:
            out[cod] = (filas[0]["NOMBRE"] or "").strip()
    return out
