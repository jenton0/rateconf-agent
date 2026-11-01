# Rate Confirmation Intake Agent

Turns broker rate confirmation PDFs into clean rows in a spreadsheet and flags the ones a human should look at.

**The problem.** Every load starts with a rate confirmation PDF from a broker. Each broker uses a different layout, and someone in the office retypes load number, stops, appointment times and pay into the TMS or a Google Sheet. That costs a few minutes per load, and typos (wrong date, wrong total) turn into missed appointments and billing disputes.

**What this does.**

```
PDF (any broker layout)
   │
   ▼
Claude reads the PDF ──► structured output (Pydantic schema, guaranteed valid JSON)
   │
   ▼
Deterministic checks in Python (no AI):
   • line items add up to the printed total
   • there is a pickup and a delivery
   • appointments are in chronological order
   • every stop has an appointment time
   │
   ▼
loads.csv / Google Sheets  — status OK or REVIEW with the reason
```

The AI only *reads*; arithmetic and business rules are plain code with unit tests, so a model mistake can't silently change money or dates. Duplicate loads (same broker + load number) are skipped.

## Example run

The `samples/` folder holds three fictional rate confirmations with different layouts (dry van, multi-stop reefer, flatbed). The Granite one contains two deliberate errors. Real run (claude-opus-5-5, about $0.06 for all three):

```
$ python rateconf.py samples/
[OK    ] RC_BlueMesa_5512.pdf: BML-5512 Fresno, CA -> Denver, CO  $4170.00
[REVIEW] RC_Granite_K-7710.pdf: K-7710 Gary, IN -> Springfield, MO  $2000.00
           ! charges add up to 1900.00 but total says 2000.00
           ! Springfield, MO appointment (11/02 15:00) is before Gary, IN (11/03 07:00)
[OK    ] RC_NorthRiver_88231.pdf: NRF-88231 Joliet, IL -> Atlanta, GA  $2460.00

3 file(s), 1 need review. Tokens: 10304 in / 1082 out. Output: loads.csv
```

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-..."
python make_samples.py                   # regenerate the sample PDFs
python rateconf.py samples/
python -m pytest                         # validation tests, no API key needed
```

Settings (environment variables):

| Variable | Default | Purpose |
|---|---|---|
| `RATECONF_MODEL` | `claude-opus-5-5` | Model; a cheaper one such as `claude-haiku-5-5` is enough for clean PDFs |
| `RATECONF_CSV` | `loads.csv` | Output file |
| `GOOGLE_SHEET_ID`, `GOOGLE_APPLICATION_CREDENTIALS` | — | For `--sheet`: sheet ID and a service-account JSON that has edit access to the sheet (`pip install gspread`) |

## Where this goes next

- Watch a Gmail label (Apps Script or Gmail API) so PDFs are processed the moment a broker sends them.
- Post REVIEW items to the dispatch channel instead of a CSV column.
- Push OK loads straight into the TMS/CRM through its API.
- Same pattern works for BOLs, PODs, lumper receipts and fuel invoices.

## Files

| File | |
|---|---|
| `rateconf.py` | Extraction, validation, CSV/Sheets output, CLI |
| `test_validate.py` | Unit tests for the checks |
| `make_samples.py` | Generates the fictional sample PDFs |
