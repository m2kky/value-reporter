# Monthly Social Media Reports

Python MVP for monthly client social media reporting. The first connector is
Meta Ads; TikTok, Google Ads, and organic social can be added on the same
pipeline shape.

## What it does now

- Pulls Meta Ads Insights for a full calendar month across one or more ad accounts.
- Pulls Facebook Page and Instagram organic content for format/theme analysis.
- Pulls previous-month account summary for month-over-month comparison.
- Pulls previous-month organic content so the AI report can compare content volume, reach, and engagement month over month.
- Stores raw API responses and normalized CSV files.
- Generates a Markdown monthly report per client.
- Keeps credentials out of source files via `.env`.

## Setup

1. Copy `.env.example` to `.env`.
2. Fill `META_ADS_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`, and `META_AD_ACCOUNT_ID_2`.
3. Fill `META_PAGE_ID` and optionally `META_ORGANIC_ACCESS_TOKEN` for Facebook organic reporting.
   If Instagram is not linked through the Page response, fill `META_INSTAGRAM_ACCOUNT_ID`.
4. Adjust `clients.json` with the real client name, timezone, and currency.
5. Run a dry check:

```powershell
python -m social_reports.cli --client client_demo --month 2026-04 --dry-run
```

6. Run the report:

```powershell
python -m social_reports.cli --client client_demo --month 2026-04
```

If `--month` is omitted, the pipeline uses the last completed calendar month
in the client's timezone.

## Output

```text
outputs/
  client_demo/
    2026-04/
      raw/
      processed/
      monthly_social_report.md
      ai_monthly_report.md
```

## Dashboard

Run the local dashboard:

```powershell
python dashboard\server.py --port 8765
```

Open `http://127.0.0.1:8765`, choose the ad accounts, Page, Instagram account,
and metrics, then save the config or run the monthly report.

## AI report

Every run writes `ai_monthly_report.md` beside the standard Markdown report.
By default this uses local deterministic narrative rules. To use OpenAI for a
more polished strategic narrative, set:

```env
AI_REPORT_ENABLED=true
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.4
```

When enabled, the report KPIs, campaign rows, and organic content rows are sent
to the OpenAI API to generate the narrative.

## Multi-client env pattern

For each client, create separate environment variables:

```env
META_ADS_ACCESS_TOKEN_CLIENT_A=...
META_AD_ACCOUNT_ID_CLIENT_A_MAIN=act_...
META_AD_ACCOUNT_ID_CLIENT_A_SECONDARY=act_...
```

Then point each client config at the right variable names:

```json
{
  "id": "client_a",
  "platforms": {
    "meta": {
      "access_token_env": "META_ADS_ACCESS_TOKEN_CLIENT_A",
      "accounts": [
        {
          "id": "main",
          "name": "Main Ad Account",
          "ad_account_id_env": "META_AD_ACCOUNT_ID_CLIENT_A_MAIN"
        },
        {
          "id": "secondary",
          "name": "Secondary Ad Account",
          "ad_account_id_env": "META_AD_ACCOUNT_ID_CLIENT_A_SECONDARY"
        }
      ]
    }
  }
}
```
