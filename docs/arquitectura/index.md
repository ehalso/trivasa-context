# Arquitectura

El entorno completo: de dónde sale la data, por dónde pasa y dónde termina.

## Documentos

- **[Servidores y bases](servidores-y-bases.md)** — topología de SQL Server, qué base es cuál, `EMPRESAS_2` como catálogo de control, respaldos. **Leer antes de escribir cualquier query.**
- **[El ERP: Management Pro](erp-management-pro.md)** — qué es el sistema origen, sus tres capas (escritorio VB6, IIS, servicio .NET), cómo se conecta a la base, y la deuda técnica que afecta leer su código.
- **[Stack de BI en ctunlinux](stack-bi.md)** — servicios, puertos, repos, extracción con dlt, transformación con dbt, orquestación, observabilidad, `torep` (captura de output de scripts/SQL a HTML) y el DuckDB CLI + conector `mssql`.
- **[Hosting de la wiki](wiki-hosting.md)** — cómo se publica este sitio.

## El recorrido de un dato

```mermaid
flowchart LR
    subgraph ORIGEN["Origen — ERP Management Pro"]
        P[(".207/TRIVASADB<br/>producción")]
        C[(".200/TRIVASADB3<br/>copia restaurada")]
        X["//.211/SincronizarXml<br/>XMLs CFDI del SAT"]
    end

    subgraph CTUN["ctunlinux — stack de BI"]
        DLT["dlt<br/>ingesta"]
        PG[("PostgreSQL :5433<br/>trivasa_dw")]
        DBT["dbt Core<br/>staging → marts"]
        BI["Lightdash :8090<br/>Metabase :3000"]
        OBS["Loki :3100<br/>Perses :8080"]
    end

    P -->|incrementales diarios| DLT
    C -.->|backfills históricos| DLT
    X --> DLT
    DLT --> PG --> DBT --> BI
    PG --> OBS

    P -->|restauración manual| C

    style P fill:#d4edda,stroke:#155724
    style C fill:#fff3cd,stroke:#856404
    style PG fill:#cce5ff,stroke:#004085
```

## Lo esencial

| Pregunta | Respuesta corta |
|---|---|
| ¿Dónde están los números oficiales? | `192.168.117.207/TRIVASADB` |
| ¿Dónde exploro sin arriesgar producción? | `192.168.117.200/TRIVASADB3` |
| ¿Con qué se extrae? | **dlt** (no Meltano) |
| ¿Dónde vive el warehouse? | PostgreSQL en `ctunlinux:5433`, base `trivasa_dw` |
| ¿Con qué se transforma? | dbt Core, proyecto `trivasa_dbt` |
| ¿Qué orquesta? | Cron hoy; la convención declarada es systemd timers |
| ¿Dónde está la config de los servicios? | `~/stack/`, fuera de git |
