"""Generate a deterministic, synthetic retail transaction dataset (demo data).

Schema mirrors the UCI Online Retail dataset:
    InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country

The generator intentionally injects real-world data-quality issues so the
validation stage has genuine work to do:
    - exact duplicate rows
    - rows with a missing CustomerID
    - unparseable invoice dates
    - cancellation invoices (InvoiceNo prefixed with 'C', negative quantity)
    - non-positive unit prices (zero-price adjustments)
    - zero-quantity lines

Customer behaviour is drawn from six archetypes that mirror the RFM segment
ladder, so the K-Means stage has separable structure to recover. The output is
fully reproducible (random seed = 42).
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "demo_online_retail.csv"

START = datetime(2025, 1, 2, 8, 0, 0)
END = datetime(2025, 12, 30, 18, 0, 0)

PRODUCTS = [
    ("85123A", "WHITE HANGING HEART T-LIGHT HOLDER", 2.55),
    ("71053", "WHITE METAL LANTERN", 3.39),
    ("84406B", "CREAM CUPID HEARTS COAT HANGER", 2.75),
    ("84029G", "KNITTED UNION FLAG HOT WATER BOTTLE", 3.39),
    ("84029E", "RED WOOLLY HOTTIE WHITE HEART.", 3.39),
    ("22633", "HAND WARMER UNION JACK", 1.85),
    ("22632", "HAND WARMER RED POLKA DOT", 1.85),
    ("48187", "DOORMAT DOORMAT BLACK", 7.95),
    ("22910", "PAPER CHAIN KIT VINTAGE CHRISTMAS", 2.95),
    ("22912", "PAPER CHAIN KIT SKULLS", 2.95),
    ("21754", "HOME BUILDING BLOCK WORD", 5.95),
    ("21755", "LOVE BUILDING BLOCK WORD", 5.95),
    ("21733", "HANGING WOOD AND GLASS PLANET", 4.25),
    ("84879", "ASSORTED COLOUR BIRD ORNAMENT", 1.69),
    ("84949", "SILVER HANGING T-LIGHT HOLDER", 1.25),
    ("22423", "REGENCY CAKESTAND 3 TIER", 12.75),
    ("22720", "SET OF 3 CAKE TINS PANTRY DESIGN", 4.95),
    ("22726", "ALARM CLOCK BAKELIKE GREEN", 3.75),
    ("22727", "ALARM CLOCK BAKELIKE RED", 3.75),
    ("22728", "ALARM CLOCK BAKELIKE PINK", 3.75),
    ("22960", "JAM MAKING SET WITH JARS", 4.25),
    ("22961", "JAM MAKING SET PRINTED", 2.55),
    ("21871", "SAVE THE PLANET MUG", 1.65),
    ("21068", "VINTAGE HEADS AND TAILS CARD GAME", 1.25),
    ("21034", "REX CASH+CARRY SHOPPER", 0.85),
    ("22086", "PAPER CHAIN KIT 50'S CHRISTMAS", 2.95),
    ("22457", "NATURAL SLATE HEART CHALKBOARD", 3.75),
    ("22551", "PLASTERS IN TIN CIRCUS PARADE", 1.65),
    ("22552", "PLASTERS IN TIN SKULLS", 1.65),
    ("22554", "PLASTERS IN TIN DINOSAURS", 1.65),
    ("22620", "12 COLOURED PARTY BALLOONS", 0.85),
    ("22624", "BLUE FRINGE HOT WATER BOTTLE", 3.39),
    ("22913", "RED COAT RACK PARIS FASHION", 4.95),
    ("22914", "BLUE COAT RACK PARIS FASHION", 4.95),
    ("22927", "PURPLE FRINGE HOT WATER BOTTLE", 3.39),
    ("22980", "PANTRY SCRUBBING BRUSH", 1.45),
    ("22982", "PANTRY WHITE SCISSORS", 1.65),
    ("23084", "RABBIT NIGHT LIGHT", 2.15),
    ("23086", "ZINC PLANT POT WITH CHICKENS", 1.95),
    ("84509A", "SET OF 4 ENGLISH ROSE PLACEMATS", 4.25),
    ("84510A", "SET OF 4 POLKADOT PLACEMATS", 3.25),
    ("84535B", "FRENCH FLORAL CUSHION COVER", 4.95),
    ("84970L", "S/4 HOBBIEmetal heart DOORKNOB", 2.55),
    ("85099B", "JUMBO BAG RED RETROSPOT", 1.95),
    ("85099C", "JUMBO BAG VINTAGE DOILY", 1.95),
    ("84050", "PINK HEART CONFETTI IN TUBE", 0.85),
    ("84077", "WORLD WAR 2 GLIDERS ASSTD DESIGNS", 0.85),
    ("84507A", "ENAMEL PINK JEWELLERY BOX", 2.95),
]

COUNTRIES = [
    ("United Kingdom", 0.78), ("Germany", 0.05), ("France", 0.05),
    ("EIRE", 0.03), ("Spain", 0.02), ("Netherlands", 0.02),
    ("Belgium", 0.015), ("Switzerland", 0.015), ("Portugal", 0.01),
    ("Italy", 0.01),
]

# archetype: (n_customers, (min,max) invoices, (min,max) recency days,
#             (min,max) avg order value, (min,max) qty per line)
ARCHETYPES = {
    "champions":           (60, (10, 30), (3, 40),  (30, 140), (2, 18)),
    "loyal":               (85, (6, 14),  (8, 90),  (20, 85),  (1, 10)),
    "potential_loyalists": (90, (3, 7),   (4, 55),  (12, 60),  (1, 8)),
    "new_customers":       (45, (1, 3),   (2, 26),  (10, 55),  (1, 6)),
    "at_risk":             (70, (4, 12),  (100, 215), (12, 60), (1, 8)),
    "hibernating":         (80, (1, 5),   (225, 358), (6, 38), (1, 5)),
}


def pick_country(rng: random.Random) -> str:
    r = rng.random()
    acc = 0.0
    for name, p in COUNTRIES:
        acc += p
        if r <= acc:
            return name
    return "United Kingdom"


def main() -> None:
    import os

    scale = int(os.getenv("DEMO_SCALE", "10"))  # DEMO_SCALE=1 -> ~10k rows
    rng = random.Random(SEED)
    rows: list[dict] = []
    invoice_counter = 536000

    scaled = {
        name: (max(1, int(n * scale)), inv, rec, aov, qty)
        for name, (n, inv, rec, aov, qty) in ARCHETYPES.items()
    }
    customer_ids = rng.sample(range(12000, 990000), sum(v[0] for v in scaled.values()))

    cid_iter = iter(customer_ids)
    for archetype, (n_cust, inv_range, rec_range, aov_range, qty_range) in scaled.items():
        for _ in range(n_cust):
            customer_id = str(next(cid_iter))
            country = "United Kingdom" if rng.random() < 0.82 else pick_country(rng)
            n_invoices = rng.randint(*inv_range)
            last_recency = rng.randint(*rec_range)
            last_date = END - timedelta(days=last_recency, hours=rng.randint(0, 20))

            # spread earlier invoices between START and the last purchase
            offsets = sorted(rng.randint(0, max((last_date - START).days, 1)) for _ in range(n_invoices - 1))
            invoice_dates = [START + timedelta(days=o, hours=rng.randint(0, 10), minutes=rng.randint(0, 59)) for o in offsets]
            invoice_dates.append(last_date)
            invoice_dates = [d for d in invoice_dates if START <= d <= END]

            for inv_date in invoice_dates:
                invoice_no = str(invoice_counter)
                invoice_counter += 1
                target_aov = rng.uniform(*aov_range)
                n_lines = rng.randint(1, 5)
                chosen = rng.sample(PRODUCTS, n_lines)
                for code, desc, base_price in chosen:
                    qty = rng.randint(*qty_range)
                    unit_price = round(base_price * rng.uniform(0.92, 1.15), 2)
                    rows.append({
                        "InvoiceNo": invoice_no,
                        "StockCode": code,
                        "Description": desc,
                        "Quantity": str(qty),
                        "InvoiceDate": inv_date.strftime("%d/%m/%Y %H:%M"),
                        "UnitPrice": f"{unit_price:.2f}",
                        "CustomerID": customer_id,
                        "Country": country,
                    })

                # occasional cancellation/return of the invoice (7% chance)
                if rng.random() < 0.07 and chosen:
                    code, desc, base_price = chosen[0]
                    cancel_date = inv_date + timedelta(days=rng.randint(1, 8), hours=rng.randint(1, 6))
                    if cancel_date <= END:
                        rows.append({
                            "InvoiceNo": "C" + invoice_no,
                            "StockCode": code,
                            "Description": desc,
                            "Quantity": str(-rng.randint(1, 6)),
                            "InvoiceDate": cancel_date.strftime("%d/%m/%Y %H:%M"),
                            "UnitPrice": f"{base_price:.2f}",
                            "CustomerID": customer_id,
                            "Country": country,
                        })

    # ---- injected data-quality issues -------------------------------------
    # rows with a missing customer id (walk-in / guest checkout behaviour)
    for _ in range(180):
        code, desc, base_price = rng.choice(PRODUCTS)
        inv_date = START + timedelta(days=rng.randint(0, (END - START).days), hours=rng.randint(0, 10))
        rows.append({
            "InvoiceNo": str(invoice_counter + rng.randint(0, 400)),
            "StockCode": code,
            "Description": desc,
            "Quantity": str(rng.randint(1, 12)),
            "InvoiceDate": inv_date.strftime("%d/%m/%Y %H:%M"),
            "UnitPrice": f"{base_price:.2f}",
            "CustomerID": "",
            "Country": pick_country(rng),
        })

    # zero-price promotional adjustment lines
    for _ in range(15):
        r = rng.choice(rows)
        adj = dict(r)
        adj["UnitPrice"] = "0.00"
        adj["Quantity"] = str(rng.randint(1, 4))
        rows.append(adj)

    # zero-quantity lines (invalid)
    for _ in range(3):
        r = rng.choice(rows)
        bad = dict(r)
        bad["Quantity"] = "0"
        rows.append(bad)

    # unparseable invoice dates
    for bad_date in ["31/02/2025 10:00", "not-a-date", "2025-13-45 99:99", "", "13/45/2025 10:30"]:
        r = rng.choice(rows)
        bad = dict(r)
        bad["InvoiceDate"] = bad_date
        rows.append(bad)

    # exact duplicate rows
    for _ in range(12):
        rows.append(dict(rng.choice(rows)))

    rows.sort(key=lambda x: x["InvoiceDate"])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows -> {OUT_PATH}")
    print(f"Distinct customers (non-blank): {len({r['CustomerID'] for r in rows if r['CustomerID']})}")


if __name__ == "__main__":
    main()
