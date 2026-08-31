# Repository Structure Decision

## Context

v0.0.1 introduces the first implementation code. The repository must support a
Python/Litestar server, a React/TypeScript web client, Docker Compose
deployment, and the existing documentation/research directories.

The prior state was a Node.js starter template (`index.js`, `package.json`).
That template is disposable.

## Decision

Adopt a monorepo layout with server and client as top-level directories:

```
kondooit/
├── server/                 Python backend (Litestar)
│   ├── pyproject.toml
│   ├── kondooit/            Application package
│   │   ├── domain/          Pure domain layer
│   │   ├── application/     Application/use-case layer
│   │   ├── api/             Litestar HTTP layer
│   │   ├── infrastructure/  Database, providers, iroh
│   │   ├── config.py        Configuration
│   │   └── app.py           App factory
│   ├── alembic/             Migrations
│   ├── tests/               Server tests
│   └── Dockerfile
├── client/                 React + TypeScript frontend (future slice)
├── docker-compose.yml      Orchestration
├── docs/                   Existing documentation
├── architecture/           Existing architecture docs
├── decisions/              Existing ADRs
├── research/               Existing research scaffolding
├── roadmap/                Existing roadmap
├── vision/                 Existing vision
├── CLAUDE.md               Governing instructions
└── .env                    Environment configuration
```

## Rationale

- **Top-level `server/` and `client/`** keep the two technology stacks isolated.
  Python tooling (pyproject.toml, pytest, alembic) does not interfere with
  Node tooling (package.json, vite, eslint) and vice versa.
- **`docker-compose.yml` at the root** matches the canonical developer
  experience: `git clone && cd kondooit && docker compose up --build`.
- **Existing documentation directories stay at the root** — they are
  project-level, not server-specific or client-specific.
- **`tests/` lives inside `server/`** rather than at the root because tests
  are server-specific. The root-level `tests/` placeholder from the
  documentation phase is superseded.

## What was removed

- `index.js` — Node.js hello-world placeholder.
- `package.json` / `package-lock.json` — Node.js starter metadata. The web
  client will get its own `package.json` inside `client/`.
