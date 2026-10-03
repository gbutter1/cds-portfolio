"""
Synthetic extracts from the five systems behind a fictional warehouse club,
Peachtree Supply Club: three Atlanta-area stores, each with a retail floor, a
cafe and an auto center. 26 weeks, Monday 30 March to Sunday 27 September 2026.

Every system exports in its own format, the way real ones do:

  retail point of sale   retail_pos_lines.csv        ISO timestamps, 8-digit SKUs with leading zeros
  merchandising          products.csv, price_book.csv the product master and its price history
  cafe point of sale     cafe_menu.csv, cafe_shift_sales.csv, cafe_shift_tenders.csv
                                                     MM/DD/YYYY dates, lower-case location codes, shift batches
  auto center system     auto_work_order_lines.csv   "4/12/2026 3:42 PM" timestamps, "$1,234.50" amounts,
                         auto_part_xref.csv          the auto vendor's own part numbers + a crosswalk to SKUs
  inventory              inventory_movements.csv     SKUs without leading zeros
  accounting             gl_journal.csv              YYYYMMDD dates, debit/credit columns, GL account numbers
  bank                   bank_transactions.csv       one line per deposit, details buried in a free-text description

The businesses are consistent with each other except for a set of deliberate,
realistic mismatches that the reconciliation has to find: a café shift batch
left open (posted a day late), register sales posted to the wrong store, auto
labor posted to the retail account, a duplicated manual journal entry, card
settlements that are short (chargebacks), missing or late, a processor charging
more than the contract rate, cash bags that are over or short, auto parts
installed but never relieved from inventory, auto part numbers that cannot be
matched to a store SKU, registers still charging an old price after a price
change, and items sold that were never set up in the product master.

In mid-July two process fixes go in (barcode scanning in the auto center and
automatic batch close in the cafes), so several exception types fall off in
the second half of the period, the kind of trend a weekly report should show.

Usage:
    python projects/retail_reconciliation/generate.py
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 20261004
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "retail_reconciliation"
START = date(2026, 3, 30)   # a Monday
END = date(2026, 9, 27)     # a Sunday: 26 full weeks
PROCESS_FIX = date(2026, 7, 13)

# retail store no, size factor (stores are described in dbt/seeds/rr_store_xref.csv)
STORES = [("101", 1.00), ("102", 0.86), ("103", 0.72)]
CAFE_LOC = {"101": "cafe-dul", "102": "cafe-ken", "103": "cafe-mcd"}
AUTO_SHOP = {"101": "DUL1", "102": "KEN1", "103": "MCD1"}
GL_ENTITY = {"101": "1101", "102": "1102", "103": "1103"}
CARD_MID = {"101": "884100101", "102": "884100102", "103": "884100103"}
CAFE_MID = {"101": "CB-7701", "102": "CB-7702", "103": "CB-7703"}
BANK_HOLIDAYS = {date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7)}

CARD_FEE = 0.0185        # PeachPay contract rate, retail + auto
CAFE_FEE = 0.026         # TableSide Pay contract rate, cafe
TAX_RATE = 0.07

# ---------------------------------------------------------------- products
# (description, category, list price) - generic names, no real brands
CATALOG = {
    "Grocery": [
        ("Ground Coffee, Medium Roast, 3 lb", 16.99), ("Organic Eggs, 24 ct", 9.49), ("Whole Milk, 2 x 1 gal", 7.29),
        ("Sparkling Water, 35 pk", 13.99), ("Bananas, 3 lb", 1.99), ("Rotisserie Chicken", 4.99),
        ("Frozen Berry Blend, 4 lb", 13.49), ("Extra Virgin Olive Oil, 2 L", 21.99), ("Basmati Rice, 25 lb", 24.99),
        ("Mixed Nuts, 2.5 lb", 17.99), ("Chicken Breasts, 6.5 lb", 22.49), ("Ground Beef 88/12, 4 lb", 21.96),
        ("Salmon Fillets, 3 lb", 29.99), ("Bagels, 12 ct", 6.99), ("Cheddar Cheese, 2.5 lb", 11.99),
        ("Greek Yogurt, 48 oz", 6.79), ("Avocados, 6 ct", 6.99), ("Strawberries, 2 lb", 5.99),
        ("Bottled Water, 40 pk", 4.99), ("Paper Plates, 300 ct", 14.99), ("Granola Bars, 48 ct", 15.49),
        ("Peanut Butter, 2 x 40 oz", 11.79), ("Pasta Sauce, 3 pk", 9.99), ("Frozen Pizza, 4 pk", 15.99),
    ],
    "Household": [
        ("Paper Towels, 12 rolls", 22.99), ("Bath Tissue, 30 rolls", 24.99), ("Laundry Detergent, 200 loads", 21.99),
        ("Dish Soap, 3 pk", 9.99), ("Trash Bags, 13 gal, 200 ct", 19.99), ("Dishwasher Pods, 115 ct", 18.49),
        ("Disinfecting Wipes, 5 pk", 15.99), ("Aluminum Foil, 2 rolls", 17.99), ("Facial Tissue, 12 boxes", 19.49),
        ("Storage Bags, 4 pk", 13.99), ("AA Batteries, 48 pk", 17.99), ("Light Bulbs LED, 16 pk", 18.99),
    ],
    "Health & Beauty": [
        ("Multivitamin, 365 ct", 15.99), ("Pain Reliever, 500 ct", 11.49), ("Allergy Relief, 365 ct", 17.99),
        ("Shampoo & Conditioner Set", 14.99), ("Body Wash, 3 pk", 16.99), ("Toothpaste, 5 pk", 13.49),
        ("Sunscreen SPF 50, 2 pk", 18.99), ("Contact Solution, 3 pk", 21.99),
    ],
    "Apparel": [
        ("Men's Performance Polo", 16.99), ("Women's Leggings, 2 pk", 19.99), ("Kids' Graphic Tees, 3 pk", 14.99),
        ("Athletic Socks, 8 pk", 15.99), ("Rain Jacket", 29.99), ("Slippers", 17.99),
    ],
    "Home & Garden": [
        ("Patio Umbrella, 9 ft", 89.99), ("Garden Hose, 100 ft", 39.99), ("Potting Mix, 2 bags", 19.99),
        ("Bath Towels, 6 pc", 34.99), ("Queen Sheet Set", 44.99), ("Cookware Set, 10 pc", 129.99),
        ("Outdoor Lounge Chair", 149.99), ("Storage Bins, 6 pk", 39.99), ("Mulch, 3 bags", 14.99),
        ("Cooler, 60 qt", 59.99),
    ],
    "Electronics": [
        ("55-inch 4K TV", 379.99), ("Wireless Earbuds", 129.99), ("10-inch Tablet", 249.99),
        ("Laptop, 15-inch", 599.99), ("Smart Speaker", 49.99), ("Video Doorbell", 99.99),
        ("Phone Charger, 3 pk", 24.99), ("Printer Ink Combo", 54.99),
    ],
    "Automotive": [  # also used by the auto center; mapped through auto_part_xref.csv
        ("All-Season Tire 205/55R16", 119.99), ("All-Season Tire 225/65R17", 149.99),
        ("All-Season Tire 235/60R18", 169.99), ("All-Terrain Tire 265/70R17", 209.99),
        ("Touring Tire 215/60R16", 129.99), ("Performance Tire 245/40R18", 189.99),
        ("Car Battery Group 24F", 129.99), ("Car Battery Group 35", 139.99), ("Car Battery Group H6", 169.99),
        ("Full Synthetic Motor Oil 5W-30, 5 qt", 27.99), ("Full Synthetic Motor Oil 0W-20, 5 qt", 28.99),
        ("Oil Filter, Standard", 7.99), ("Wiper Blades, 2 pk", 24.99), ("Windshield Washer Fluid, 3 gal", 8.99),
        ("Jumper Cables", 29.99),
    ],
}
CAT_WEIGHT = {"Grocery": 0.43, "Household": 0.20, "Health & Beauty": 0.10, "Apparel": 0.07,
              "Home & Garden": 0.09, "Electronics": 0.05, "Automotive": 0.06}
COST_RATIO = {"Grocery": 0.86, "Household": 0.85, "Health & Beauty": 0.80, "Apparel": 0.70,
              "Home & Garden": 0.72, "Electronics": 0.88, "Automotive": 0.78}

# auto vendor part number for each Automotive SKU description used in the shop
VENDOR_PART = {
    "All-Season Tire 205/55R16": "TR-20555R16-AS", "All-Season Tire 225/65R17": "TR-22565R17-AS",
    "All-Season Tire 235/60R18": "TR-23560R18-AS", "All-Terrain Tire 265/70R17": "TR-26570R17-AT",
    "Touring Tire 215/60R16": "TR-21560R16-TR", "Performance Tire 245/40R18": "TR-24540R18-PF",
    "Car Battery Group 24F": "BT-24F-750", "Car Battery Group 35": "BT-35-640", "Car Battery Group H6": "BT-H6-760",
    "Full Synthetic Motor Oil 5W-30, 5 qt": "OL-5W30-FS5", "Full Synthetic Motor Oil 0W-20, 5 qt": "OL-0W20-FS5",
    "Oil Filter, Standard": "FL-OIL-STD", "Wiper Blades, 2 pk": "WP-PAIR-STD",
}
UNKNOWN_SKUS = [("00987001", "Seasonal Fire Pit", 129.99), ("00987002", "Back-to-School Backpack", 24.99),
                ("00987003", "Pool Float, 2 pk", 19.99), ("00987004", "Tailgate Canopy, 10x10", 99.99)]

CAFE_MENU = [  # code, name, price, food cost %
    ("HD01", "Hot Dog & Soda Combo", 1.50, 0.78), ("PZ01", "Pizza Slice", 1.99, 0.42),
    ("PZ02", "Whole Pizza", 9.95, 0.38), ("CB01", "Chicken Bake", 3.99, 0.45),
    ("SL01", "Caesar Salad", 4.99, 0.40), ("CH01", "Churro", 1.49, 0.30),
    ("FY01", "Frozen Yogurt", 1.79, 0.32), ("SM01", "Berry Smoothie", 2.99, 0.36),
    ("CF01", "Iced Coffee", 2.49, 0.25), ("SD01", "Fountain Soda", 0.79, 0.20),
]
CAFE_WEIGHT = [0.26, 0.20, 0.06, 0.10, 0.05, 0.07, 0.08, 0.05, 0.05, 0.08]

AUTO_LABOR = {  # code: (description, price)
    "LAB-TIREPKG": ("Tire installation package (per tire)", 24.99), "LAB-BATTINST": ("Battery installation", 19.99),
    "LAB-OILSVC": ("Oil change service", 34.99), "LAB-ROTBAL": ("Tire rotation & balance", 29.99),
    "LAB-ALIGN": ("Four-wheel alignment", 99.99), "LAB-WIPER": ("Wiper installation", 5.00),
}
AUTO_FEE = ("FEE-TIREDISP", "Tire disposal fee (per tire)", 3.00)
LABOR_COST_RATIO = 0.45


def next_business_day(d: date, n: int = 1) -> date:
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in BANK_HOLIDAYS:
            n -= 1
    return d


def shop_time(t: datetime) -> str:
    """The auto center's export format, e.g. 4/12/2026 3:42 PM (portable, no %-m)."""
    h = t.hour % 12 or 12
    return f"{t.month}/{t.day}/{t.year} {h}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def money(x: float) -> float:
    return round(x + 1e-9, 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(SEED)

    # ------------------------------------------------------------ product master + price book
    products, sku_by_desc = [], {}
    n = 100100
    for cat, items in CATALOG.items():
        for desc, price in items:
            n += rnd.randint(7, 40)
            sku = f"{n:08d}"
            cost = money(price * COST_RATIO[cat] * rnd.uniform(0.96, 1.04))
            products.append({"sku": sku, "description": desc, "category": cat, "unit_cost": cost, "list_price": price})
            sku_by_desc[desc] = sku
    prod = {p["sku"]: p for p in products}

    # price history: one opening price, then ~16 price changes during the period
    price_book = [{"sku": p["sku"], "effective_date": "2026-01-01", "price": p["list_price"]} for p in products]
    changes = []
    change_skus = rnd.sample([p["sku"] for p in products if p["category"] != "Automotive"], 16)
    for sku in change_skus:
        eff = START + timedelta(days=rnd.randint(10, 165))
        new = money(prod[sku]["list_price"] * rnd.choice([0.9, 0.92, 0.95, 1.05, 1.06, 1.08, 1.1]))
        new = money(int(new) + 0.99) if new > 5 else new
        changes.append((sku, eff, new))
        price_book.append({"sku": sku, "effective_date": eff.isoformat(), "price": new})
    # registers at one store that missed a price-change push, for N days
    missed_push = {}
    for sku, eff, new in rnd.sample(changes, 4):
        store = rnd.choice(["101", "102", "103"])
        missed_push[(store, sku)] = (eff, eff + timedelta(days=rnd.randint(3, 9)))

    def book_price(sku: str, d: date) -> float:
        p = prod[sku]["list_price"]
        for s, eff, new in changes:
            if s == sku and d >= eff:
                p = new
        return p

    def pos_price(store: str, sku: str, d: date) -> float:
        if (store, sku) in missed_push:
            a, b = missed_push[(store, sku)]
            if a <= d < b:
                return book_price(sku, a - timedelta(days=1))   # registers still on the old price
        return book_price(sku, d)

    cats = list(CAT_WEIGHT)
    cat_skus = {c: [p["sku"] for p in products if p["category"] == c] for c in cats}

    # aggregates the other systems are built from
    retail_day = defaultdict(lambda: {"sales": 0.0, "card": 0.0, "cash": 0.0, "tax": 0.0, "reg": defaultdict(float)})
    auto_day = defaultdict(lambda: {"parts": 0.0, "labor": 0.0, "card": 0.0, "cash": 0.0, "tax": 0.0})
    cafe_shift = {}
    inv_sales = defaultdict(int)
    inv_rows = []

    # ------------------------------------------------------------ retail POS
    f_pos = (out / "retail_pos_lines.csv").open("w", newline="", encoding="utf-8")
    w_pos = csv.writer(f_pos)
    w_pos.writerow(["txn_id", "store_no", "register_no", "txn_ts", "sku", "item_description", "qty",
                    "unit_price", "line_discount", "line_amount", "tender_type"])
    unknown_windows = {}
    for code, desc, price in UNKNOWN_SKUS:
        a = START + timedelta(days=rnd.randint(20, 150))
        unknown_windows[code] = (a, a + timedelta(days=rnd.randint(6, 16)), desc, price)

    d = START
    txn_seq = 0
    while d <= END:
        dow = d.weekday()
        dow_f = [0.88, 0.85, 0.9, 0.95, 1.1, 1.45, 1.25][dow]
        doy = (d - date(2026, 1, 1)).days
        garden = 1.6 if 90 <= doy <= 200 else 1.0
        for store, size in STORES:
            n_txn = int(rnd.gauss(235 * size * dow_f, 12))
            for _ in range(max(n_txn, 50)):
                txn_seq += 1
                reg = rnd.randint(1, 10)
                ts = datetime(d.year, d.month, d.day, 10) + timedelta(minutes=rnd.randint(0, 600))
                tender = "CARD" if rnd.random() < 0.9 else "CASH"
                n_lines = min(9, max(1, int(rnd.expovariate(1 / 2.4)) + 1))
                txn_total = 0.0
                rows = []
                for _ in range(n_lines):
                    wts = [CAT_WEIGHT[c] * (garden if c == "Home & Garden" else 1) for c in cats]
                    cat = rnd.choices(cats, wts)[0]
                    sku = rnd.choice(cat_skus[cat])
                    desc = prod[sku]["description"]
                    price = pos_price(store, sku, d)
                    # items never set up in the product master, sold during their season window
                    for code, (a, b, udesc, uprice) in unknown_windows.items():
                        if a <= d <= b and rnd.random() < 0.004:
                            sku, desc, price = code, udesc, uprice
                    qty = 1 if price > 40 else rnd.choices([1, 2, 3], [0.8, 0.15, 0.05])[0]
                    ext = money(price * qty)
                    disc = money(ext * rnd.uniform(0.1, 0.2)) if rnd.random() < 0.08 else 0.0
                    amt = money(ext - disc)
                    rows.append((sku, desc, qty, price, disc, amt))
                    txn_total += amt
                for sku, desc, qty, price, disc, amt in rows:
                    w_pos.writerow([f"R{store}-{txn_seq:07d}", store, reg, ts.isoformat(timespec="seconds"), sku,
                                    desc, qty, f"{price:.2f}", f"{disc:.2f}", f"{amt:.2f}", tender])
                    if sku in prod:
                        inv_sales[(store, sku, d)] += qty
                agg = retail_day[(store, d)]
                agg["sales"] += txn_total
                agg[tender.lower()] += txn_total * (1 + TAX_RATE)
                agg["tax"] += txn_total * TAX_RATE
                agg["reg"][reg] += txn_total
        d += timedelta(days=1)
    f_pos.close()

    # ------------------------------------------------------------ cafe POS (shift batches)
    with (out / "cafe_menu.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item_code", "item_name", "menu_price", "food_cost_pct"])
        for code, name, price, fc in CAFE_MENU:
            w.writerow([code, name, f"{price:.2f}", fc])

    f_cs = (out / "cafe_shift_sales.csv").open("w", newline="", encoding="utf-8")
    w_cs = csv.writer(f_cs)
    w_cs.writerow(["location", "business_date", "shift", "item_code", "item_name", "qty_sold", "gross_sales"])
    f_ct = (out / "cafe_shift_tenders.csv").open("w", newline="", encoding="utf-8")
    w_ct = csv.writer(f_ct)
    w_ct.writerow(["location", "business_date", "shift", "card_total", "cash_total", "batch_date", "closed_by"])
    d = START
    while d <= END:
        dow_f = [0.85, 0.82, 0.88, 0.92, 1.1, 1.5, 1.3][d.weekday()]
        for store, size in STORES:
            loc = CAFE_LOC[store]
            for shift, share in (("AM", 0.44), ("PM", 0.56)):
                items = int(rnd.gauss(820 * size * dow_f * share, 25))
                counts = defaultdict(int)
                for code in rnd.choices([m[0] for m in CAFE_MENU], CAFE_WEIGHT, k=items):
                    counts[code] += 1
                total = 0.0
                for code, name, price, _fc in CAFE_MENU:
                    q = counts[code]
                    if not q:
                        continue
                    g = money(q * price)
                    total += g
                    shown = code.lower() if rnd.random() < 0.15 else code   # the export is not consistent
                    w_cs.writerow([loc.upper() if rnd.random() < 0.3 else loc, d.strftime("%m/%d/%Y"), shift,
                                   shown, name, q, f"{g:.2f}"])
                gross = money(total * (1 + TAX_RATE))
                card = money(gross * rnd.uniform(0.82, 0.88))
                cash = money(gross - card)
                # PM batch occasionally left open: it closes with the next morning's batch
                open_rate = 0.05 if d < PROCESS_FIX else 0.006
                prev = cafe_shift.get((store, d - timedelta(days=1), "PM"))
                prev_late = prev is not None and prev["batch"] != d - timedelta(days=1)
                late = shift == "PM" and d < END and not prev_late and rnd.random() < open_rate
                batch = d + timedelta(days=1) if late else d
                closer = "AUTO" if d >= PROCESS_FIX else rnd.choice(["MGR01", "MGR02", "MGR03"])
                w_ct.writerow([loc, d.strftime("%m/%d/%Y"), shift, f"{card:.2f}", f"{cash:.2f}",
                               batch.strftime("%m/%d/%Y"), closer if not late else "MGR-NEXTDAY"])
                cafe_shift[(store, d, shift)] = {"sales": money(total), "tax": money(gross - total),
                                                 "card": card, "cash": cash, "batch": batch}
        d += timedelta(days=1)
    f_cs.close()
    f_ct.close()

    # ------------------------------------------------------------ auto center work orders
    tires = [k for k in VENDOR_PART if "Tire" in k]
    batteries = [k for k in VENDOR_PART if "Battery" in k]
    oils = [k for k in VENDOR_PART if "Motor Oil" in k]
    with (out / "auto_part_xref.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["vendor_part_no", "store_sku", "last_updated_by"])
        for desc, vp in VENDOR_PART.items():
            w.writerow([vp, sku_by_desc[desc], rnd.choice(["auto.mgr.dul", "auto.mgr.ken", "merch.team"])])

    f_wo = (out / "auto_work_order_lines.csv").open("w", newline="", encoding="utf-8")
    w_wo = csv.writer(f_wo)
    w_wo.writerow(["wo_number", "shop_code", "closed_at", "line_no", "line_type", "item_code", "description",
                   "qty", "amount", "payment_method"])
    wo_seq = 0
    d = START
    while d <= END:
        dow_f = [0.95, 0.9, 0.9, 0.95, 1.05, 1.4, 0.8][d.weekday()]
        before = d < PROCESS_FIX
        for store, size in STORES:
            shop = AUTO_SHOP[store]
            for _ in range(max(5, int(rnd.gauss(22 * size * dow_f, 3)))):
                wo_seq += 1
                wo = f"WO{shop}-{wo_seq:06d}"
                closed = datetime(d.year, d.month, d.day, 8) + timedelta(minutes=rnd.randint(30, 660))
                svc = rnd.choices(["tires", "battery", "oil", "rotate", "align", "wipers"],
                                  [0.34, 0.14, 0.26, 0.12, 0.08, 0.06])[0]
                lines = []
                if svc == "tires":
                    t = rnd.choice(tires); q = rnd.choices([4, 2, 1], [0.75, 0.2, 0.05])[0]
                    lines += [("PART", t, q), ("LABOR", "LAB-TIREPKG", q), ("FEE", AUTO_FEE[0], q)]
                elif svc == "battery":
                    lines += [("PART", rnd.choice(batteries), 1), ("LABOR", "LAB-BATTINST", 1)]
                elif svc == "oil":
                    lines += [("LABOR", "LAB-OILSVC", 1), ("PART", rnd.choice(oils), 1),
                              ("PART", "Oil Filter, Standard", 1)]
                elif svc == "rotate":
                    lines += [("LABOR", "LAB-ROTBAL", 1)]
                elif svc == "align":
                    lines += [("LABOR", "LAB-ALIGN", 1)]
                else:
                    lines += [("PART", "Wiper Blades, 2 pk", 1), ("LABOR", "LAB-WIPER", 1)]
                pay = rnd.choices(["VISA", "MC", "AMEX", "DEBIT", "CASH"], [0.38, 0.27, 0.1, 0.13, 0.12])[0]
                wo_total = 0.0
                for i, (lt, item, q) in enumerate(lines, 1):
                    if lt == "PART":
                        sku = sku_by_desc[item]
                        amt = money(book_price(sku, d) * q)
                        code = VENDOR_PART[item]
                        r = rnd.random()
                        typo_rate, misc_rate = (0.07, 0.025) if before else (0.012, 0.003)
                        if r < misc_rate:
                            code = rnd.choice(["MISC PART", "MISC-TIRE", "SEE NOTES"])
                            mapped = False
                        else:
                            if r < misc_rate + typo_rate:   # typed by hand: lower case, no dashes, stray spaces
                                code = rnd.choice([code.lower(), code.replace("-", ""), " " + code.replace("-", " ")])
                            mapped = True
                        desc = item
                        # inventory: the part should be issued out of store stock against the work order
                        if mapped:
                            miss = rnd.random() < (0.02 if before else 0.004)
                            wrong_qty = (not miss) and q > 1 and rnd.random() < (0.02 if before else 0.004)
                            if not miss:
                                iq = q - rnd.randint(1, q - 1) if wrong_qty else q
                                inv_rows.append([sku.lstrip("0"), store, "AUTO_ISSUE", (d + timedelta(
                                    days=1 if closed.hour >= 18 and rnd.random() < 0.5 else 0)).isoformat(), -iq, wo])
                        auto_day[(store, d)]["parts"] += amt
                    elif lt == "LABOR":
                        desc, price = AUTO_LABOR[item]
                        code, amt = item, money(price * q)
                        auto_day[(store, d)]["labor"] += amt
                    else:
                        code, desc, amt = AUTO_FEE[0], AUTO_FEE[1], money(AUTO_FEE[2] * q)
                        auto_day[(store, d)]["parts"] += amt
                    wo_total += amt
                    w_wo.writerow([wo, shop, shop_time(closed), i, lt, code, desc, q,
                                   f"${amt:,.2f}", pay])
                gross = money(wo_total * (1 + TAX_RATE))
                auto_day[(store, d)]["cash" if pay == "CASH" else "card"] += gross
                auto_day[(store, d)]["tax"] += gross - wo_total
        d += timedelta(days=1)
    f_wo.close()

    # ------------------------------------------------------------ inventory movements
    for (store, sku, day), q in inv_sales.items():
        inv_rows.append([sku.lstrip("0"), store, "SALE", day.isoformat(), -q, f"POS-{store}-{day:%Y%m%d}"])
    weekly = defaultdict(int)
    for (store, sku, day), q in inv_sales.items():
        weekly[(store, sku, day - timedelta(days=day.weekday()))] += q
    for (store, sku, wk), q in weekly.items():
        inv_rows.append([sku.lstrip("0"), store, "RECEIPT", (wk + timedelta(days=2)).isoformat(),
                         int(q * rnd.uniform(0.9, 1.15)) + 1, f"PO-{store}-{wk:%Y%m%d}"])
    inv_rows.sort(key=lambda r: (r[3], r[1], r[0]))
    with (out / "inventory_movements.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item_no", "location", "movement_type", "movement_date", "qty", "reference"])
        w.writerows(inv_rows)

    # ------------------------------------------------------------ products + price book files
    with (out / "products.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sku", "description", "category", "unit_cost", "list_price"])
        w.writeheader()
        for p in products:
            w.writerow({**p, "list_price": f"{book_price(p['sku'], END):.2f}", "unit_cost": f"{p['unit_cost']:.2f}"})
    with (out / "price_book.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sku", "effective_date", "price"])
        w.writeheader()
        for r in sorted(price_book, key=lambda r: (r["sku"], r["effective_date"])):
            w.writerow({**r, "price": f"{r['price']:.2f}"})

    # ------------------------------------------------------------ general ledger
    gl = []

    def post(entity, day, acct, name, desc, debit=0.0, credit=0.0, source="RTL-POS"):
        gl.append([entity, day.strftime("%Y%m%d"), acct, name, desc, f"{debit:.2f}", f"{credit:.2f}", source])

    days = [START + timedelta(days=i) for i in range((END - START).days + 1)]
    misposts = {(dd, rnd.choice(["101", "102", "103"])) for dd in rnd.sample(days[7:-7], 6)}
    wrong_dept = {(rnd.choice(days[7:-7]), rnd.choice(["101", "102", "103"])) for _ in range(5)}
    dup_manual = {(rnd.choice(days[7:-7]), rnd.choice(["101", "102", "103"])) for _ in range(4)}
    cafe_post = defaultdict(lambda: {"sales": 0.0, "tax": 0.0})
    for (store, day, shift), s in cafe_shift.items():
        cafe_post[(store, s["batch"])]["sales"] += s["sales"]
        cafe_post[(store, s["batch"])]["tax"] += s["tax"]
    others = {"101": ["102", "103"], "102": ["101", "103"], "103": ["101", "102"]}
    for day in days:
        for store, _ in STORES:
            ent = GL_ENTITY[store]
            r = retail_day[(store, day)]
            sales = money(r["sales"])
            if (day, store) in misposts:   # one register's day posted under a sister store's entity
                reg = max(r["reg"], key=r["reg"].get)
                moved = money(r["reg"][reg])
                post(ent, day, "4010", "Merchandise sales", f"Daily sales summary {store}", credit=money(sales - moved))
                post(GL_ENTITY[rnd.choice(others[store])], day, "4010", "Merchandise sales",
                     f"Daily sales summary {store} reg {reg:02d}", credit=moved)
            else:
                post(ent, day, "4010", "Merchandise sales", f"Daily sales summary {store}", credit=sales)
            post(ent, day, "2100", "Sales tax payable", "Sales tax collected", credit=money(r["tax"]))
            post(ent, day, "1210", "Card clearing", "Card sales", debit=money(r["card"]))
            post(ent, day, "1010", "Cash on hand", "Cash sales", debit=money(r["cash"]))

            a = auto_day[(store, day)]
            post(ent, day, "4030", "Auto service - parts & fees", "Shop daily close", credit=money(a["parts"]), source="AUTO-SMS")
            labor = money(a["labor"])
            if (day, store) in wrong_dept:   # labor mapped to the merchandise account
                post(ent, day, "4010", "Merchandise sales", "Shop daily close - labor", credit=labor, source="AUTO-SMS")
            else:
                post(ent, day, "4031", "Auto service - labor", "Shop daily close", credit=labor, source="AUTO-SMS")
            post(ent, day, "2100", "Sales tax payable", "Sales tax collected", credit=money(a["tax"]), source="AUTO-SMS")

            c = cafe_post.get((store, day))
            if c:
                post(ent, day, "4020", "Food service sales", "Cafe batch", credit=money(c["sales"]), source="CAFE-POS")
                post(ent, day, "2100", "Sales tax payable", "Sales tax collected", credit=money(c["tax"]), source="CAFE-POS")
            if (day, store) in dup_manual:
                amt = money(rnd.uniform(180, 1400))
                post(ent, day, "4010", "Merchandise sales", "Manual adj - member refund reversal", credit=amt, source="MANUAL")
    with (out / "gl_journal.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["entity", "posting_date", "account", "account_name", "description", "debit", "credit", "source"])
        w.writerows(gl)

    # ------------------------------------------------------------ bank
    bank = []
    missing = {(rnd.choice(days[5:-10]), rnd.choice(["101", "102", "103"])) for _ in range(2)}
    late = {(rnd.choice(days[5:-10]), rnd.choice(["101", "102", "103"])): rnd.randint(5, 8) for _ in range(3)}
    for day in days:
        for store, _ in STORES:
            # PeachPay: retail + auto card sales, next business day, contract fee
            gross = money(retail_day[(store, day)]["card"] + auto_day[(store, day)]["card"])
            rate = CARD_FEE
            if store == "102" and date(2026, 6, 1) <= day <= date(2026, 6, 21):
                rate = 0.0235   # processor applied a higher tier for three weeks
            net = money(gross - money(gross * rate))
            if rnd.random() < 0.012:
                net = money(net - rnd.uniform(40, 450))   # chargeback netted from the settlement
            if (day, store) not in missing:
                pd = next_business_day(day, 1 + late.get((day, store), 0))
                bank.append([pd.isoformat(), f"PEACHPAY MERCH SETTLE MID {CARD_MID[store]} BATCH {day:%m%d}", f"{net:.2f}", "CREDIT"])
            # cash: retail + auto + cafe, armored pickup next business day
            cash = retail_day[(store, day)]["cash"] + auto_day[(store, day)]["cash"] + sum(
                cafe_shift[(store, day, s)]["cash"] for s in ("AM", "PM"))
            cash = money(cash)
            r = rnd.random()
            short_rate = 0.04 if day < PROCESS_FIX else 0.02
            if r < short_rate:
                cash = money(cash - rnd.choice([5, 10, 20, 20, 40, 50, 100, rnd.uniform(5, 150)]))
            elif r < short_rate + 0.006:
                cash = money(cash + rnd.choice([10, 20, 50]))
            bank.append([next_business_day(day).isoformat(), f"ARMORED CAR DEP LOC {store} BAG {day:%Y%m%d}", f"{cash:.2f}", "CREDIT"])
    # TableSide Pay: cafe card batches, two business days after the batch date
    batches = defaultdict(float)
    for (store, day, shift), s in cafe_shift.items():
        batches[(store, s["batch"])] += s["card"]
    for (store, bd), gross in sorted(batches.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        gross = money(gross)
        net = money(gross - money(gross * CAFE_FEE))
        bank.append([next_business_day(bd, 2).isoformat(), f"TABLESIDE PAY DEP {CAFE_MID[store]} BD {bd:%Y%m%d}", f"{net:.2f}", "CREDIT"])
    # a few unrelated credits a real statement has
    for _ in range(8):
        dd = rnd.choice(days)
        bank.append([next_business_day(dd).isoformat(), rnd.choice(["INTEREST PAYMENT", "VENDOR REBATE ACH", "INSURANCE REFUND"]),
                     f"{rnd.uniform(25, 900):.2f}", "CREDIT"])
    bank = [b for b in bank if b[0] <= (END + timedelta(days=9)).isoformat()]
    bank.sort()
    with (out / "bank_transactions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["post_date", "description", "amount", "type"])
        w.writerows(bank)

    for p in sorted(out.glob("*.csv")):
        with p.open(encoding="utf-8") as f:
            print(f"wrote {sum(1 for _ in f) - 1:>9,} rows -> {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
