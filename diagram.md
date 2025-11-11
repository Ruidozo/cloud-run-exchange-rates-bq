┌─────────────────────────────────────────────────────────────────────┐
│                    EXCHANGE RATES PIPELINE                          │
└─────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────────┐
   │                   TRIGGER                                   │
   ├──────────────────────────────────────────────────────────────┤
   │ • Cloud Scheduler (daily 6 AM UTC)                          │
   │ • Manual HTTP POST curl -X POST {SERVICE_URL}/ingest        │
   └─────────────────┬──────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────────────────────┐
   │          PHASE 1: FETCH (30 days)                           │
   ├──────────────────────────────────────────────────────────────┤
   │ Open Exchange Rates API                                     │
   │   ├─ Loop: date -30 to today                               │
   │   ├─ Each call: /api/historical/{YYYY-MM-DD}.json         │
   │   └─ Handle errors gracefully (skip date, continue)        │
   └─────────────────┬──────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────────────────────┐
   │       PHASE 2: TRANSFORM (USD → EUR base)                  │
   ├──────────────────────────────────────────────────────────────┤
   │ For each date with rates:                                   │
   │   ├─ Get EUR rate from API (e.g., 0.92)                    │
   │   ├─ Calculate: usd_to_eur = 1 / 0.92 = 1.087             │
   │   ├─ For each currency (USD, GBP, JPY, CHF):              │
   │   │   └─ rate_eur = api_rate × 1.087                      │
   │   └─ Result: ~120 records (30 days × 4 currencies)         │
   └─────────────────┬──────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────────────────────┐
   │   PHASE 3: LOAD TO STAGING (BigQuery)                      │
   ├──────────────────────────────────────────────────────────────┤
   │ • TRUNCATE staging table                                    │
   │ • Load JSON records (LoadJob)                              │
   │ • Status: Ready for MERGE                                  │
   └─────────────────┬──────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────────────────────┐
   │          PHASE 4: MERGE (Idempotent Upsert)               │
   ├──────────────────────────────────────────────────────────────┤
   │ MERGE INTO rates T                                          │
   │ USING staging S                                             │
   │ ON T.date = S.date AND T.currency = S.currency            │
   │   WHEN MATCHED → UPDATE                                     │
   │   WHEN NOT MATCHED → INSERT                                │
   │                                                              │
   │ Result:                                                     │
   │  • New (date, currency) pairs → INSERT                     │
   │  • Existing pairs → UPDATE (handles corrections)           │
   │  • Idempotent: Run 1x or 10x = same result                │
   └─────────────────┬──────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────────────────────┐
   │              RESPONSE & LOGGING                              │
   ├──────────────────────────────────────────────────────────────┤
   │ • {"status": "success", "records": 120}                      │
   │ • Structured logs → Cloud Logging                           │
   │ • Optional: Slack alert on failure                          │
   └─────────────────┬──────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────────────────────┐
   │          BIGQUERY (Main Table)                              │
   ├──────────────────────────────────────────────────────────────┤
   │ rates (time-partitioned on date, clustered by currency)    │
   │                                                              │
   │ Columns:                                                    │
   │  • date (DATE) - partition key                             │
   │  • currency (STRING) - cluster key                         │
   │  • rate_to_eur (FLOAT64) - exchange rate                   │
   │  • timestamp (TIMESTAMP) - fetch time (ISO 8601)           │
   │                                                              │
   │ Sample data:                                                │
   │  2025-11-11 │ USD │ 1.087 │ 2025-11-11T00:00:00Z         │
   │  2025-11-11 │ GBP │ 0.880 │ 2025-11-11T00:00:00Z         │
   │  2025-11-10 │ USD │ 1.086 │ 2025-11-10T00:00:00Z         │
   └──────────────────────────────────────────────────────────────┘
                     │
                     ▼
   ┌──────────────────────────────────────────────────────────────┐
   │         LOOKER STUDIO (Dashboards & Reports)               │
   ├──────────────────────────────────────────────────────────────┤
   │ • Exchange rate trends (30-day history)                     │
   │ • Currency volatility (min/max/avg per currency)            │
   │ • Revenue conversion calculator                             │
   │ • Data freshness indicator                                  │
   └──────────────────────────────────────────────────────────────┘