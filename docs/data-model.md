# Data Model

Money is stored as integer cents to avoid floating point errors.

Core tables:

- `companies`: one row per company.
- `import_batches`: one row per imported source file.
- `accounts`: normalized account list by company and year.
- `journal_headers`: voucher-level information.
- `journal_lines`: entry-line information with debit and credit cents.
- `trial_balance`: balance table rows with current and cumulative movement.
- `saved_queries`: reviewed read-only query templates.

Every imported GL/TB row keeps `raw_json`, so original source columns can be inspected later.
