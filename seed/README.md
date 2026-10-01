# Development seed data

The deterministic generator lives in `backend/app/seed/` so it can share the typed ORM model vocabulary, while `backend/scripts/seed_database.py` owns transactional database insertion.

- Random seed: `20261001`
- Dataset reference date: `2026-10-01`
- Size: 500 customers, 50 products, 2,000 orders, roughly 5,900 order items, and roughly 400 refunds
- Safety: a normal run requires empty application tables; `--reset` explicitly deletes application rows in dependency-safe order before recreating the dataset

Run the command from `backend/` as documented in the root README. The generator creates one full-value refund at most per refunded order item; it does not model multiple partial refunds yet.
