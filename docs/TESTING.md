# Testing Principles

## Unit Tests vs. Integration Tests

Kondooit distinguishes two levels of automated testing:

### Unit Tests

- **Database:** In-memory SQLite is acceptable.
- **Purpose:** Validate repository mapping logic, domain entity
  construction, application-layer use case behavior, and API request/
  response handling.
- **What they prove:** The code logic is correct — ORM models map to
  domain entities, repository methods return the right shapes, use
  cases orchestrate correctly.
- **What they do NOT prove:** PostgreSQL-specific behavior, constraint
  enforcement, query semantics that differ between databases.

### Integration Tests

- **Database:** PostgreSQL is required. No substitutions.
- **Purpose:** Validate schema correctness, PostgreSQL-specific query
  behavior (ILIKE, UUID types, constraints, cascading deletes),
  migration correctness, and end-to-end server-to-database operation.
- **What they prove:** The system works against the real production
  database engine.

### Production

- **Database:** PostgreSQL only. No alternate databases are supported.

## Rule

A test that depends on database behavior (query semantics, constraints,
types, cascades) MUST be an integration test running against PostgreSQL.
A test that only validates code-level mapping or orchestration logic MAY
use SQLite as a lightweight stand-in.

If a repository method uses PostgreSQL-specific features (e.g., ILIKE for
case-insensitive search), the unit test validates the method's structure
and the integration test validates the actual query behavior.
