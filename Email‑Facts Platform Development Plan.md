# Email‑Facts Platform Development Plan

This document outlines a **step‑by‑step plan** for co‑developing, with an AI agent, a robust multi‑tenant Email‑Facts platform on top of Apache Iceberg and Nessie, integrated into Jarvis via MCP tools.

---

## Environment Configuration

Ensure the following environment variables are set in your MCP server, Spark jobs, and any client connecting to Iceberg:

```bash
# Apache Iceberg & Nessie configuration\NICE
ICEBERG_NESSIE_URL=https://nessie-ca2.agreeablewater-7670027e.westus2.azurecontainerapps.io/
ICEBERG_NESSIE_STORE_JDBC_URL=jdbc:postgresql://pg-nessie.postgres.database.azure.com:5432/nessie?sslmode=require
ICEBERG_NESSIE_STORE_JDBC_USERNAME=nessie
ICEBERG_NESSIE_STORE_JDBC_PASSWORD=W0ngk1anw00n
NESSIE_WAREHOUSE=abfs://kb-lake@kblake.dfs.core.windows.net/

# JVM properties secret (java-props)
java-props=-Dnessie.version.store.type=JDBC \
  -Dnessie.version.store.jdbc.jdbcUrl=$ICEBERG_NESSIE_STORE_JDBC_URL \
  -Dnessie.version.store.jdbc.username=$ICEBERG_NESSIE_STORE_JDBC_USERNAME \
  -Dnessie.version.store.jdbc.password=$ICEBERG_NESSIE_STORE_JDBC_PASSWORD \
  -Dnessie.catalog.warehouses.warehouse.location=$NESSIE_WAREHOUSE
```

Store sensitive values (`ICEBERG_NESSIE_STORE_JDBC_PASSWORD`) as secrets in Azure Container Apps or Koyeb.

---

## 1. Foundations

1. **Provision Iceberg Catalog & Warehouse**
   - Ensure the **Nessie REST catalog** (see `ICEBERG_NESSIE_URL`) and **ADLS Gen2 warehouse** (`NESSIE_WAREHOUSE`) are Healthy.
   - Verify you can create and query an empty table `kb.email_sales` via Spark or DuckDB using the JDBC and env vars above.

2. **Vector DB Preparation (Future Phase)**
   - Confirm your Milvus/Qdrant cluster and `search_knowledge` MCP tool are operational.

---

## 2. Ingestion Pipeline

1. **Delta‑Sync from Mail API**
   - Build a micro‑service to pull mail deltas every 15 min via MS Graph. Persist `deltaLink`.

2. **Normalization & Chunking**
   - Parse MIME → strip noise → chunk into 400 tokens → embed → upsert into vector DB.

3. **Schema‑Driven Facts Extraction**
   - Load tenant rule‑packs (regex, spaCy, zero‑shot) from the facts catalog.
   - Emit structured records only when required fields (e.g., `amount` and `client`) appear.

4. **Write to Iceberg**
   - Use PyIceberg or Spark Structured Streaming with env vars=`ICEBERG_NESSIE_*` → `append()` Parquet files into `kb.email_sales`.
   - Commit to Nessie branch; merge hourly.

5. **Backfill & Idempotency**
   - Backfill the last 12 months before go‑live.
   - Use upsert semantics on `message_id` to avoid duplicates.

---

## 3. Facts Catalog

Maintain a central **`facts_catalog`** table to track all extractors:

```sql
CREATE TABLE facts_catalog (
  tenant_id    STRING,
  fact_set_id  STRING,
  schema_json  JSON,
  table_name   STRING,
  created_at   TIMESTAMP,
  ttl_at       TIMESTAMP,
  PRIMARY KEY (tenant_id, fact_set_id)
);
```

- On new extractor: generate `fact_set_id`, persist `schema_json` + `table_name`, and backfill.
- Ingestion workers read this catalog to route records.

---

## 4. MCP Tool: `query_facts`

Expose a **generic MCP tool** for analytics on any `fact_set`:

```json
{ "fact_set": "sales-revenue-v1.0", "period": "2025-03", "group_by": ["sales_rep"] }
```

Resolver snippet (Python + DuckDB):

```python
@tool.query_facts
async def _(inp):
    # env vars ICEBERG_NESSIE_* already set
    con = duckdb.connect()
    con.sql("INSTALL 'iceberg'; LOAD 'iceberg';")
    con.sql(f"SET s3_endpoint='https://{os.environ['AZURE_STORAGE_ACCOUNT']}.dfs.core.windows.net{os.environ['AZURE_STORAGE_SAS']}';")
    con.sql(f"SET nessie_endpoint='{os.environ['ICEBERG_NESSIE_URL']}api/v1';")
    q = f"""
      SELECT {','.join(inp['group_by'])}, SUM(value) AS value
      FROM {lookup_table(inp['tenant_id'], inp['fact_set'])}
      WHERE period = '{inp['period']}'
      GROUP BY {','.join(inp['group_by'])}
    """
    rows = con.sql(q).to_df().to_dict('records')
    return {"period": inp['period'], "data": rows}
```

Deploy this on Container Apps/Koyeb; register in Jarvis config.

---

## 5. Onboarding New Variants

1. Tenant UI/CLI: define domain/purpose or upload JSON schema.
2. System suggests `fact_set_id`; write to `facts_catalog`.
3. Backfill job triggers ingestion workers.

No code changes required—just metadata updates.

---

## 6. Governance & Housekeeping

| Concern               | Mechanism                               |
|-----------------------|-----------------------------------------|
| Schema changes        | Version bump → new `fact_set_id`       |
| Data retention        | `ttl_at`; Iceberg `expireSnapshots`     |
| File compaction       | `rewrite_data_files` nightly            |
| Orphaned sets         | Soft‑delete after inactivity            |
| Usage quotas          | Monitor row counts; enforce limits      |

Automate via Spark jobs or Iceberg actions.

---

## 7. Jarvis Integration

1. **System prompt**:
   > "For structured metrics, call `query_facts(fact_set, period, group_by)`."
2. **Tool policy**: up to 2 calls/turn; fallback to semantic search if empty.
3. **Test**: "Show March revenue by sales rep" → correct JSON + narrative.

---

## 8. Future Roadmap

- **Phase A**: Iceberg facts only.  
- **Phase B**: Reintroduce vector RAG.  
- **Phase C**: Hybrid orchestration (analytics + context).  
- **Phase D**: Excel export via `generate_excel`.

---

_End of plan_

