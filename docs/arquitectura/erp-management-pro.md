# El ERP: Management Pro

> Qué es el sistema del que sale toda la data, cómo está construido y qué piezas lo alimentan. Relevante para BI porque explica **por qué el esquema es como es** y dónde vive la lógica de negocio que hay que replicar.
>
> Verificado 2026-08-10 sobre `192.168.117.200`.

## Qué es

**Management Pro** (fabricante mpro/ERIX) es una suite ERP multi-giro vendida como producto. Trivasa la usa para materiales de construcción en Yucatán y Quintana Roo.

Que sea multi-giro explica un rasgo central del esquema: de **1,454 tablas, 632 están vacías (43 %)** — son módulos que el producto trae pero Trivasa no usa (clínica, hotelería, restaurante, Rappi, Shopify, PDA, punto de venta alternativo). Ver [Dominios de negocio](../schema/dominios.md).

## Las tres capas

### 1. Cliente de escritorio — Visual Basic 6

`C:\Program Files (x86)\mproerp\Management Pro\`

Ejecutables + DLLs/OCX COM clásicos: `PRO.exe` (ERP principal), `PROADM.exe` (administración), `RETAIL.exe`, `PosTouch.exe` (punto de venta), `FAE.exe`/`NCE.exe` (facturación electrónica), `Asistencia.exe` (checador biométrico), `REPLICADOR.exe`, `DATASYNC.exe`, `ShopifySync.exe`, `SendWhatsPro.exe`, `MailReports.exe`, `Respaldo.exe`.

- `Core/` — DLLs de dominio (`catalogosPRO.dll`, `AutoPRO.dll`, `adjuntoPro.dll`, `utilPRO`) y biometría (`UFMatcher.dll`, `UFScanner.dll`, Suprema).
- `Servidor/FARLICSVR.exe` — servicio de licencias, instalado vía `AppToService`.
- `LOGS/MproSys_YYYY-MM-DD.log` — **sin valor analítico**: `MproSys.exe` es solo el auto-actualizador; el log es 99 % `"Comprobando actualizaciones / Sin actualizaciones pendientes"` cada minuto.

### 2. Aplicaciones web — IIS

`C:\inetpub\wwwroot\Management Pro\` — unas **35 aplicaciones independientes**, en su mayoría ASP clásico (VBScript), algunas SPAs modernas.

| App | Tipo | Función |
|---|---|---|
| `connect` | ASP clásico | Portal principal (`invoices`, `orders`, `user`, `admin`) |
| `pro` | ASP clásico | Núcleo web del ERP — **aquí viven los ~900 ASP de reportes** |
| `credito` | ASP clásico | Crédito y cobranza |
| `clientes` | ASP clásico | Portal de clientes |
| `ventas`, `inventarios`, `precios`, `proveedores` | SPA | Front-ends modernos |
| `webservicempro`, `wservices`, `wsappmobile`, `wsnetpay`, `mprows` | Servicios web | APIs (móvil, pagos) |
| `crm`, `ecommerce`, `monedero`, `comandaweb`, `cursos`, `evaluacion`, `kb`, `mapsmpro` | Varios | Módulos adicionales |

### 3. Un servicio .NET moderno

La app **`Autenticacion`** (host `trv930`) corre sobre **HangFire** y usa `TRIVASADB3` como staging. Gestiona el módulo de **solicitudes de material**. Ver [Servidores y bases](servidores-y-bases.md#pero-si-recibe-escrituras-propias).

## Cómo se conectan a la base

**No hay cadenas de conexión en los `web.config`** (`<connectionStrings />` vacío). Las apps ASP delegan en un objeto COM del ERP:

```asp
set oUtil = server.CreateObject("utilPRO.Util")
set tConexion = oUtil.GetIniConexion("Config.ini")
scnServer = tConexion.Server : scnDataBase = tConexion.Database ...
```

Es decir, **el sitio IIS lee la misma `CONFIG.ini` del cliente de escritorio**, en `Program Files (x86)\mproerp\Management Pro\`:

```ini
[CONEXION]
SERVER=SVR-DEV
SERVERDB=192.168.117.200
DATABASE=EMPRESAS_2        ; base de CONTROL, no la de negocio
DATABASEWEB=TRIVASADB2
```

Dos consecuencias para BI:

1. **No se puede saber a qué base apunta una app web leyendo su propia config.** Hay que mirar el `.ini` central y contrastarlo con las sesiones activas en SQL Server.
2. **`DATABASE=EMPRESAS_2` no es la base de negocio** — es el catálogo de control. La base de negocio se elige en tiempo de ejecución al iniciar sesión, según la empresa. Y `DATABASEWEB=TRIVASADB2` está desactualizado respecto a lo que se usa (`TRIVASADB3`): es un `.ini` de un equipo de desarrollo, no una autoridad.

## Deuda técnica que afecta la lectura del código

El árbol del IIS está lleno de **copias manuales con fecha**, hechas antes de cada cambio. No son variantes funcionales — son respaldos:

```
pro/RPAG_original/   pro/RPAG_v2/   pro/RPAG_con_equipo/
pro/RPCXC_old/       pro/RPCXP_07.07.25/   pro/RPCXP_22.07.25/
```

Y dentro de cada reporte: `RPAG008_270123.asp`, `RPAG008_Anterior_07.05.25.asp`, `RPAG008_MOD_08.05.25.ERROR`… En `pro/Z/` son **48 de 236 carpetas**. `include/funciones.asp` tiene 5 variantes.

**Regla al leer este código:** el archivo vigente es el que coincide exactamente con la `URL` registrada en `EMPRESAS_2.Menus`. Cualquier otro nombre con sufijo es histórico. Al hacer `grep`:

```bash
grep -rn "MiTabla" pro/ --include=*.asp \
  | grep -viE '_(old|original|origi|anterior|error|v[0-9]|[0-9]{6,8}|[0-9]{2}\.[0-9]{2}\.[0-9]{2})'
```

Además hay **38 entradas de menú muertas**: cinco carpetas referenciadas que no existen en el servidor (`/reporte/`, `/herramienta/`, `/agenda/`, `/vigilante/`, `/desvio/`).

## Nota operativa

`grep -r` recursivo directo sobre los shares CIFS es inviable (tarda minutos, suele agotar el timeout). Para analizar el código, copiar primero a local:

```bash
cd "/mnt/win200_c/inetpub/wwwroot/Management Pro/pro"
tar cf - --exclude='*.zip' --exclude='*.rar' --exclude='*.gif' --exclude='*.jpg' --exclude='*.png' \
    RP* AN* Z include/consultas include/tablero 2>/dev/null | (cd /destino/local && tar xf -)
```
