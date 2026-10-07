# ADR-0019: Database schema owned by ORM models and initialized at startup; Alembic only for alterations

- **Status:** Accepted
- **Date:** 2026-10-07
- **Supersedes:** —
- **Superseded by:** —

## Context

The server's schema was defined in three places that had drifted apart: the SQLAlchemy models, an Alembic chain (0001–0007), and a parallel set of SQL migrations under `supabase/` that no Kondooit deployment used.

The Alembic chain could not run on a fresh database. 0001 had been rewritten to contain most of the current schema, so 0002 then tried to create a table that already existed. 0001 also lacked the `profiles` table, which 0007 alters. Because the entire upgrade ran in one transaction, the failure rolled back everything, and the entrypoint silently fell back to `Base.metadata.create_all`. Every deployment was therefore built by `create_all` with no recorded Alembic revision. Because `create_all` never alters existing tables, any future column change would never have reached existing deployments.

Kondooit is deployed with Docker Compose against its own PostgreSQL (ADR-0008). Hosted-database tooling plays no part in this.

## Decision

1. **The ORM models are the complete definition of the schema.** A new table or column is always added to the models. Nothing exists only in a migration.
2. **One startup routine owns schema initialization** (`kondooit.infrastructure.schema.initialize_schema`, called from the application lifespan). In a single transaction it:
   1. creates any missing tables from the models (existing tables are skipped);
   2. if the database has no Alembic revision recorded, stamps it at `head`, because the tables just created already reflect every revision;
   3. otherwise, runs `alembic upgrade head`.
   Any failure aborts startup. There is no fallback.
3. **Alembic revisions only alter existing tables**, for example adding, removing, or renaming columns, changing constraints, or backfilling data. Each revision checks the current state before acting (for example, it adds a column only if the column is missing). This makes it a no-op on a database freshly created from the models.
4. **History restarts from a baseline.** Revisions 0001–0007 are replaced by an empty `0001_baseline` representing the schema as of this ADR. No deployment carried a recorded revision, so none needs to be carried forward.
5. **The `supabase/` migrations are removed.** They are not part of Kondooit's deployment.

Running table creation before migrations means a table added and later altered in the same release is created in its final form; the guarded alteration then skips itself.

## Alternatives considered

- **Migrations as the only source (no `create_all`).** This is conventional, but every new table must be written twice (model and migration), and history must be replayed on fresh installs. That is the drift this ADR removes.
- **`create_all` only.** It cannot alter existing tables, so existing deployments would never receive column changes.
- **Keep an "initial schema" migration mirroring the models.** This keeps three representations in sync by hand, which is what failed.

## Consequences

- Fresh installs and upgraded installs converge on the models.
- Every alteration needs both a model change and a guarded revision. A test that compares a fresh database and a migrated database against the models is deferred until there are revisions to test.
- Indexes and constraints that existed only in the removed migrations (for example, unique constraints on `user_content_state` and `watch_progress`) are not part of the schema unless added to the models.
- The startup script no longer runs migrations; the server does.
