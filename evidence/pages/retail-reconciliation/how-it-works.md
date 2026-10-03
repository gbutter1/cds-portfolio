---
title: How It Was Built · Store-to-Bank Reconciliation
---

This project is about **data integration**: taking six systems that
were never designed to talk to each other, translating them into one shared
language, and proving they agree. The output is the report a controller or
store operations lead would want on their desk every Monday: what doesn't
match, how much it's worth, which system is most likely wrong, and what to do
about it. The full source is in the
[public repository on GitHub](https://github.com/gbutter1/cds-portfolio).

<LinkButton url="/reports/retail-reconciliation/index.html">Open the latest weekly report →</LinkButton>

## 1. The business

Peachtree Supply Club is a fictional warehouse club with three Atlanta-area
stores (Duluth, Kennesaw, McDonough). Each store runs three businesses under
one roof: a **retail floor**, a **café** and an **auto center** that sells and
installs tires, batteries and oil changes. The data covers 26 weeks, from
March 30 to September 27, 2026: about 435,000 records and $16.6 million in
sales.

## 2. Six systems, six dialects

```sql systems
select 'Retail registers' as system, 'One row per item scanned' as grain, 'Store "101", 8-digit SKUs with leading zeros, ISO timestamps' as how_it_speaks
union all select 'Café registers', 'Items sold and card/cash totals per shift', 'Location "cafe-dul" (sometimes upper case), MM/DD/YYYY dates, its own menu codes'
union all select 'Auto center shop system', 'One row per labor, part or fee line on a work order', 'Shop "DUL1", the tire vendor''s part numbers, "$1,234.50" amounts, "4/12/2026 3:42 PM" times'
union all select 'Merchandising & inventory', 'Product master, price history, and stock movements (sales, receipts, auto center issues)', 'SKUs with leading zeros in the product master but without them in inventory, work orders as references'
union all select 'Accounting', 'Daily journal lines by account', 'Entity "1101", YYYYMMDD dates, debit and credit columns, GL account numbers'
union all select 'Bank statement', 'One line per deposit', 'Everything (processor, merchant ID, batch date) packed into a free-text description'
```

<DataTable data={systems} rows=6>
  <Column id=system />
  <Column id=grain wrap=true />
  <Column id=how_it_speaks title="How it identifies things" wrap=true />
</DataTable>

The raw layer loads all of it as text, exactly as delivered. Staging then
translates every system into the same vocabulary using three small
**reference tables** (dbt seeds): a store crosswalk that ties each system's
store code to one `store_id`, the chart of accounts with the department each
revenue account belongs to, and the card processors with their contract fee
rates. The auto center's part numbers are matched to store SKUs through the
shop's own crosswalk after stripping spaces, dashes and case, so a hand-typed
`tr22565r17as` still finds `TR-22565R17-AS`. Bank descriptions are parsed
with regular expressions, including working out the year for processor
batches that only print the month and day.

## 3. Five reconciliation checks

```sql checks
select 1 as n, 'Sales vs. accounting' as check_name, 'Register sales per store, day and department vs. revenue booked in the ledger' as compares, 'Posted a day late (timing), posted under the wrong store, posted to the wrong department, unexplained' as finds
union all select 2, 'Card sales vs. bank', 'Each card batch vs. the processor deposit, less the contract fee', 'Missing deposits, late deposits, chargebacks, a processor charging more than the contract rate'
union all select 3, 'Cash vs. bank', 'Cash taken in by all three departments vs. the armored-car deposit', 'Bags that are over or short'
union all select 4, 'Auto parts vs. inventory', 'Every part billed on a work order vs. the part issued from store stock', 'Part numbers that match no SKU, installed parts never taken out of inventory, wrong quantities'
union all select 5, 'Registers vs. product master', 'Items and prices rung up vs. the product master and price book', 'Items sold that were never set up, registers still charging an old price'
```

<DataTable data={checks} rows=5>
  <Column id=n title="#" align=center />
  <Column id=check_name title="Check" />
  <Column id=compares title="Compares" wrap=true />
  <Column id=finds title="What it finds" wrap=true />
</DataTable>

**Explaining differences, not just finding them.** A difference between
the registers and the ledger is only useful if someone knows what to do
about it. So the sales check looks for the pattern behind each one: if the
same amount shows up the next day, it's a **timing** difference (a café shift
batch closed late) that clears itself; if it shows up under a sister store
the same day, it was **posted to the wrong store**; if it shows up under
another department in the same store, the **account mapping** is wrong. Only
what's left is reported as unexplained. The card check does the same with
fees: one short deposit is probably a chargeback, but the same extra half
percent on several days in a row is the **processor charging above contract**.

The auto center check is the cross-department one. When the shop installs
four tires, those tires come off the retail floor's stock. A part that was
billed but never issued means the shelves hold less than inventory says, the
kind of gap that otherwise only surfaces at the annual physical count.

## 4. One list of exceptions

All five checks feed a single `rr_exceptions` table, one row per problem,
with the amount at risk, a severity, the system where the fix belongs and a
plain-language next step, so the report can be read by someone who has never
opened any of the six systems. Timing differences are kept but not counted as
unmatched dollars.

```sql models
select 'rr_daily_department_sales' as model, 'store x day x department' as grain, 'net sales, cost and volume from the three point-of-sale systems' as contents
union all select 'rr_recon_sales_vs_gl', 'store x day x department', 'register vs. ledger, with the explanation for each difference'
union all select 'rr_recon_card_vs_bank', 'processor x store x batch date', 'expected vs. actual deposit, implied fee rate, days to deposit'
union all select 'rr_recon_cash_vs_bank', 'store x day', 'cash recorded vs. cash deposited'
union all select 'rr_recon_auto_parts_vs_inventory', 'work order line', 'part billed vs. part issued'
union all select 'rr_recon_product_master', 'store x SKU x week', 'item setup and price vs. the price book'
union all select 'rr_exceptions', 'one row per problem', 'everything above that needs attention, ready to act on'
union all select 'rr_check_summary / rr_weekly_scorecard', 'week x check / week x store x department', 'what the weekly report is built from'
```

<DataTable data={models} rows=8>
  <Column id=model />
  <Column id=grain wrap=true />
  <Column id=contents wrap=true />
</DataTable>

## 5. Tests

60 tests run on this project. Every system's store code must map to a store,
every key must be unique at its stated grain, and every status must be one of
the documented values. Three project-specific tests guard the integration
itself: every dollar sold in the three point-of-sale systems must land in the
sales mart exactly once, every card and cash deposit on the bank statement
must be traced to a store and batch date (this catches a processor quietly
changing its description format), and no exception can carry a negative or
missing amount. If any test fails, nothing is published.

## 6. The weekly report

The report is a printable document, not a dashboard: one page per week,
rendered by `pipeline/build_recon_report.py` as plain HTML, with a summary
in words, a scorecard by store and department, a 26-week trend and the
exception list. Each week can be downloaded as a CSV for whoever is fixing
the items, or saved as a PDF.

The trend tells the story a real engagement would: in mid-July the auto
center started scanning parts instead of typing part numbers, and the cafés
switched to automatic batch close. Average unmatched dollars per week fell
from about $9,400 before the change to about $2,000 after.

<LinkButton url="/reports/retail-reconciliation/index.html">Open the latest weekly report →</LinkButton>
