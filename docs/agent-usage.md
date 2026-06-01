# Agent Usage

Agents should prefer controlled commands before raw SQL.

Recommended order:

1. Run `schema` if the database is unfamiliar.
2. Run `companies`.
3. Run `accounts search` to confirm account naming.
4. Use fixed commands for common audit questions:
   - `variance tb`
   - `variance gl`
   - `trace depreciation`
   - `reconcile gl-tb`
5. Use `sql select` only for exploratory read-only queries.
6. Promote reviewed exploratory SQL with `saved-query add`, then reuse it with `saved-query run --value key=value`.

When answering a user, include:

- database path
- company
- year/month scope
- command used
- query caveats
