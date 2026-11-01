"""Rate confirmation intake: PDF -> Claude (structured output) -> validation -> CSV / Google Sheets.

Usage:
    python rateconf.py samples/              # process every PDF in a folder
    python rateconf.py samples/RC_x.pdf      # process one file
    python rateconf.py inbox/ --sheet        # also append rows to Google Sheets
"""
from __future__ import annotations

import argparse
import base64
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

MODEL = os.environ.get("RATECONF_MODEL", "claude-opus-5-5")
CSV_PATH = Path(os.environ.get("RATECONF_CSV", "loads.csv"))
CSV_COLUMNS = [
    "processed_at", "source_file", "load_number", "broker", "equipment", "commodity", "weight_lbs",
    "pickup_city", "pickup_time", "delivery_city", "delivery_time", "stops", "total_usd",
    "payment_terms", "status", "issues",
]


# ---------- Schema Claude must fill ----------

class Stop(BaseModel):
    kind: Literal["pickup", "delivery", "intermediate"]
    company: str
    address: str
    city: str
    state: str = Field(description="Two-letter US state code")
    appointment: str | None = Field(
        description="Appointment start as ISO 8601 'YYYY-MM-DDTHH:MM'; earliest time if a window is given; null if absent"
    )


class Charge(BaseModel):
    description: str
    amount_usd: float


class RateConfirmation(BaseModel):
    broker_name: str
    load_number: str = Field(description="Broker's primary load / reference number")
    equipment: str | None
    commodity: str | None
    weight_lbs: float | None
    stops: list[Stop] = Field(description="All stops in the order listed on the document")
    charges: list[Charge] = Field(description="Every line item, including zero amounts")
    total_usd: float = Field(description="Total carrier pay exactly as printed on the document")
    payment_terms: str | None
    special_instructions: list[str]


SYSTEM = (
    "You extract data from trucking rate confirmations for a carrier's back office. "
    "Copy numbers exactly as printed; never compute or correct totals yourself, because a separate "
    "check compares them. Classify the first loading stop as pickup, the final unloading stop as "
    "delivery and anything in between as intermediate. Use null for fields the document does not contain."
)


# ---------- Extraction ----------

def extract(client: anthropic.Anthropic, pdf_path: Path) -> tuple[RateConfirmation, anthropic.types.Usage]:
    pdf_b64 = base64.standard_b64encode(pdf_path.read_bytes()).decode()
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        output_config={"effort": "low"},  # simple extraction; raise for messy scans
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}},
                {"type": "text", "text": "Extract this rate confirmation."},
            ],
        }],
        output_format=RateConfirmation,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"model declined: {response.stop_details}")
    return response.parsed_output, response.usage


# ---------- Deterministic checks (no AI here, on purpose) ----------

def validate(rc: RateConfirmation) -> list[str]:
    issues: list[str] = []

    charges_sum = round(sum(c.amount_usd for c in rc.charges), 2)
    if abs(charges_sum - rc.total_usd) > 0.01:
        issues.append(f"charges add up to {charges_sum:.2f} but total says {rc.total_usd:.2f}")

    kinds = [s.kind for s in rc.stops]
    if "pickup" not in kinds:
        issues.append("no pickup stop")
    if "delivery" not in kinds:
        issues.append("no delivery stop")

    times: list[tuple[str, datetime]] = []
    for s in rc.stops:
        if s.appointment is None:
            issues.append(f"missing appointment at {s.city}, {s.state}")
            continue
        try:
            times.append((f"{s.city}, {s.state}", datetime.fromisoformat(s.appointment)))
        except ValueError:
            issues.append(f"unreadable appointment '{s.appointment}' at {s.city}")
    for (prev_city, prev_t), (city, t) in zip(times, times[1:]):
        if t < prev_t:
            issues.append(f"{city} appointment ({t:%m/%d %H:%M}) is before {prev_city} ({prev_t:%m/%d %H:%M})")

    if rc.total_usd <= 0:
        issues.append("total pay is zero or negative")
    return issues


def to_row(rc: RateConfirmation, source: Path, issues: list[str]) -> dict:
    pickup = next((s for s in rc.stops if s.kind == "pickup"), None)
    delivery = next((s for s in reversed(rc.stops) if s.kind == "delivery"), None)
    return {
        "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source_file": source.name,
        "load_number": rc.load_number,
        "broker": rc.broker_name,
        "equipment": rc.equipment or "",
        "commodity": rc.commodity or "",
        "weight_lbs": rc.weight_lbs or "",
        "pickup_city": f"{pickup.city}, {pickup.state}" if pickup else "",
        "pickup_time": (pickup.appointment or "") if pickup else "",
        "delivery_city": f"{delivery.city}, {delivery.state}" if delivery else "",
        "delivery_time": (delivery.appointment or "") if delivery else "",
        "stops": len(rc.stops),
        "total_usd": f"{rc.total_usd:.2f}",
        "payment_terms": rc.payment_terms or "",
        "status": "REVIEW" if issues else "OK",
        "issues": "; ".join(issues),
    }


# ---------- Output ----------

def known_loads() -> set[str]:
    if not CSV_PATH.exists():
        return set()
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        return {(r["broker"], r["load_number"]) for r in csv.DictReader(f)}


def append_csv(row: dict) -> None:
    new = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)


def append_sheet(row: dict) -> None:
    """Needs GOOGLE_SHEET_ID and a service-account JSON at GOOGLE_APPLICATION_CREDENTIALS (see README)."""
    import gspread  # optional dependency

    gc = gspread.service_account(filename=os.environ["GOOGLE_APPLICATION_CREDENTIALS"])
    ws = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1
    if not ws.row_values(1):
        ws.append_row(CSV_COLUMNS)
    ws.append_row([row[c] for c in CSV_COLUMNS], value_input_option="USER_ENTERED")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path, help="PDF file or folder of PDFs")
    ap.add_argument("--sheet", action="store_true", help="also append to Google Sheets")
    args = ap.parse_args()

    pdfs = sorted(args.path.glob("*.pdf")) if args.path.is_dir() else [args.path]
    if not pdfs:
        print("no PDFs found", file=sys.stderr)
        return 1

    client = anthropic.Anthropic()
    seen = known_loads()
    in_tok = out_tok = 0
    review = 0

    for pdf in pdfs:
        try:
            rc, usage = extract(client, pdf)
        except (anthropic.APIError, RuntimeError) as e:
            print(f"[FAIL]   {pdf.name}: {e}")
            continue
        in_tok += usage.input_tokens
        out_tok += usage.output_tokens

        if (rc.broker_name, rc.load_number) in seen:
            print(f"[SKIP]   {pdf.name}: load {rc.load_number} already recorded")
            continue
        seen.add((rc.broker_name, rc.load_number))

        issues = validate(rc)
        row = to_row(rc, pdf, issues)
        append_csv(row)
        if args.sheet:
            append_sheet(row)

        review += bool(issues)
        print(f"[{row['status']:<6}] {pdf.name}: {rc.load_number} {row['pickup_city']} -> "
              f"{row['delivery_city']}  ${row['total_usd']}")
        for i in issues:
            print(f"           ! {i}")

    print(f"\n{len(pdfs)} file(s), {review} need review. Tokens: {in_tok} in / {out_tok} out. Output: {CSV_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
