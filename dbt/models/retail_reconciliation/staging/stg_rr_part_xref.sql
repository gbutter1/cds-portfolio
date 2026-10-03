-- Auto vendor part number -> store SKU. part_key strips everything but letters and digits so
-- hand-typed variants ("tr22555r17as", " TR 22555R17 AS") still match.
select
    trim(vendor_part_no)                                          as vendor_part_no,
    upper(regexp_replace(vendor_part_no, '[^A-Za-z0-9]', '', 'g')) as part_key,
    lpad(trim(store_sku), 8, '0')                                  as sku
from {{ source('raw_retail_reconciliation', 'auto_part_xref') }}
