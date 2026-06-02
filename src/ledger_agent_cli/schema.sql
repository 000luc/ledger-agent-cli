PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS import_batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  source_type TEXT NOT NULL CHECK (source_type IN ('gl', 'tb')),
  source_file TEXT NOT NULL,
  year INTEGER NOT NULL,
  mapping_json TEXT NOT NULL,
  row_count INTEGER NOT NULL DEFAULT 0,
  warning_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  year INTEGER NOT NULL,
  account_code TEXT NOT NULL,
  account_name TEXT NOT NULL,
  account_level INTEGER,
  parent_code TEXT,
  is_leaf INTEGER NOT NULL DEFAULT 1,
  UNIQUE(company_id, year, account_code)
);

CREATE TABLE IF NOT EXISTS journal_headers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  import_batch_id INTEGER NOT NULL REFERENCES import_batches(id),
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  voucher_date TEXT NOT NULL,
  voucher_no TEXT NOT NULL,
  voucher_type TEXT,
  preparer TEXT,
  reviewer TEXT,
  bookkeeper TEXT,
  raw_json TEXT NOT NULL,
  UNIQUE(company_id, year, month, voucher_no)
);

CREATE TABLE IF NOT EXISTS journal_lines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  header_id INTEGER NOT NULL REFERENCES journal_headers(id),
  company_id INTEGER NOT NULL REFERENCES companies(id),
  import_batch_id INTEGER NOT NULL REFERENCES import_batches(id),
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  voucher_date TEXT NOT NULL,
  voucher_no TEXT NOT NULL,
  line_no INTEGER NOT NULL,
  summary TEXT,
  account_code TEXT NOT NULL,
  account_name TEXT NOT NULL,
  debit_cents INTEGER NOT NULL DEFAULT 0,
  credit_cents INTEGER NOT NULL DEFAULT 0,
  currency TEXT,
  auxiliary TEXT,
  counterparty_account_code TEXT,
  counterparty_account_name TEXT,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trial_balance (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  import_batch_id INTEGER NOT NULL REFERENCES import_batches(id),
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  account_code TEXT NOT NULL,
  account_name TEXT NOT NULL,
  account_level INTEGER,
  opening_balance_cents INTEGER NOT NULL DEFAULT 0,
  current_debit_cents INTEGER NOT NULL DEFAULT 0,
  current_credit_cents INTEGER NOT NULL DEFAULT 0,
  ytd_debit_cents INTEGER NOT NULL DEFAULT 0,
  ytd_credit_cents INTEGER NOT NULL DEFAULT 0,
  ending_balance_cents INTEGER NOT NULL DEFAULT 0,
  balance_direction TEXT,
  auxiliary TEXT,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS saved_queries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL,
  query TEXT NOT NULL,
  parameters_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_accounts_company_year_name
  ON accounts(company_id, year, account_name);

CREATE INDEX IF NOT EXISTS idx_journal_lines_company_year_account
  ON journal_lines(company_id, year, account_code, account_name);

CREATE INDEX IF NOT EXISTS idx_journal_lines_company_year_month
  ON journal_lines(company_id, year, month);

CREATE INDEX IF NOT EXISTS idx_trial_balance_company_year_account
  ON trial_balance(company_id, year, account_code, account_name);

CREATE UNIQUE INDEX IF NOT EXISTS idx_journal_lines_unique_line
  ON journal_lines(company_id, year, month, voucher_no, line_no);

CREATE UNIQUE INDEX IF NOT EXISTS idx_trial_balance_unique_row
  ON trial_balance(company_id, year, month, account_code, COALESCE(auxiliary, ''));
