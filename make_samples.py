"""Generate fictional rate confirmation PDFs for the demo (all names and numbers are made up)."""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent / "samples"

SAMPLES = [
    {
        "file": "RC_NorthRiver_88231.pdf",
        "broker": "North River Freight Brokerage LLC",
        "mc": "MC# 000001 (demo)",
        "title": "RATE AND LOAD CONFIRMATION",
        "fields": [
            ("Load #", "NRF-88231"),
            ("Date issued", "10/28/2026"),
            ("Carrier", "Demo Carrier Inc."),
            ("Equipment", "53' Dry Van"),
            ("Commodity", "Packaged food, 38,500 lbs"),
        ],
        "stops": [
            ("PICKUP", "Midwest Foods DC, 1200 Industrial Pkwy, Joliet, IL 60431", "10/30/2026 08:00-12:00"),
            ("DELIVERY", "Southern Grocers Warehouse, 455 Commerce Dr, Atlanta, GA 30336", "11/01/2026 06:00"),
        ],
        "charges": [("Line haul", "2,150.00"), ("Fuel surcharge", "310.00"), ("Detention (est.)", "0.00")],
        "total": "2,460.00",
        "notes": "Payment terms: Net 30. Quick pay 2% available. Driver must call 1 hr before arrival.",
    },
    {
        "file": "RC_BlueMesa_5512.pdf",
        "broker": "Blue Mesa Logistics",
        "mc": "MC# 000002 (demo)",
        "title": "Carrier Rate Confirmation",
        "fields": [
            ("Reference / PO", "BML-5512 / PO 7731"),
            ("Issued", "Oct 29, 2026"),
            ("Trailer", "Reefer 53ft, set temp 34F"),
            ("Weight", "41,200 lb"),
        ],
        "stops": [
            ("Shipper", "Valley Produce Co., 88 Orchard Rd, Fresno, CA 93725", "Nov 2, 2026 at 14:00"),
            ("Stop 2 (drop)", "Coastal Market, 19 Bay St, Reno, NV 89502", "Nov 3, 2026 by 09:00"),
            ("Consignee", "Mountain Fresh DC, 700 W 52nd Ave, Denver, CO 80221", "Nov 4, 2026 by 07:00"),
        ],
        "charges": [("Flat rate", "3,900.00"), ("Extra stop", "150.00"), ("Lumper (reimbursable)", "120.00")],
        "total": "4,170.00",
        "notes": "Temperature log required at delivery. Send POD + invoice to ap@bluemesa.example within 24h.",
    },
    {
        "file": "RC_Granite_K-7710.pdf",
        "broker": "Granite Line Transport Brokers",
        "mc": "MC# 000003 (demo)",
        "title": "LOAD TENDER / RATE CONFIRMATION",
        "fields": [
            ("Load", "K-7710"),
            ("Date", "2026-10-30"),
            ("Equipment", "Flatbed 48', tarps required"),
            ("Commodity", "Steel coils, 44,000 lbs"),
        ],
        "stops": [
            ("PU", "Lakeshore Steel, 3 Mill Rd, Gary, IN 46402", "2026-11-03 07:00"),
            ("DEL", "Ozark Fabrication, 950 Rail Spur Ln, Springfield, MO 65803", "2026-11-02 15:00"),
        ],
        # Intentional problems for the validator: totals do not add up and delivery is before pickup
        "charges": [("Linehaul", "1,800.00"), ("Tarp fee", "100.00")],
        "total": "2,000.00",
        "notes": "Rate includes all accessorials unless approved in writing.",
    },
]


def draw(sample: dict) -> None:
    path = OUT / sample["file"]
    c = canvas.Canvas(str(path), pagesize=letter)
    w, h = letter
    y = h - 0.8 * inch
    c.setFont("Helvetica-Bold", 15)
    c.drawString(0.8 * inch, y, sample["broker"])
    c.setFont("Helvetica", 9)
    c.drawString(0.8 * inch, y - 14, sample["mc"] + " - FICTIONAL SAMPLE FOR DEMO PURPOSES")
    y -= 48
    c.setFont("Helvetica-Bold", 13)
    c.drawString(0.8 * inch, y, sample["title"])
    y -= 26
    c.setFont("Helvetica", 10)
    for label, value in sample["fields"]:
        c.drawString(0.8 * inch, y, f"{label}:")
        c.drawString(2.4 * inch, y, value)
        y -= 15
    y -= 12
    for label, addr, when in sample["stops"]:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0.8 * inch, y, label)
        c.setFont("Helvetica", 10)
        c.drawString(2.0 * inch, y, addr)
        c.drawString(2.0 * inch, y - 13, f"Appointment: {when}")
        y -= 34
    y -= 6
    c.setFont("Helvetica-Bold", 10)
    c.drawString(0.8 * inch, y, "Charges (USD)")
    y -= 16
    c.setFont("Helvetica", 10)
    for label, amount in sample["charges"]:
        c.drawString(1.0 * inch, y, label)
        c.drawRightString(5.5 * inch, y, amount)
        y -= 14
    c.line(1.0 * inch, y + 4, 5.5 * inch, y + 4)
    y -= 10
    c.setFont("Helvetica-Bold", 10)
    c.drawString(1.0 * inch, y, "TOTAL")
    c.drawRightString(5.5 * inch, y, sample["total"])
    y -= 30
    c.setFont("Helvetica", 9)
    c.drawString(0.8 * inch, y, sample["notes"])
    c.save()


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for s in SAMPLES:
        draw(s)
        print("wrote", OUT / s["file"])
