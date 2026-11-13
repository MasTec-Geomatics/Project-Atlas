-- One-time setup for the reference database (ADR 0019).
-- Roles belong to the whole server, so they're created here, not in a migration.
-- Safe to run more than once.

DO $$
  BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'reference_reader') THEN
      CREATE ROLE reference_reader NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'reference_maintainer') THEN
      CREATE ROLE reference_maintainer NOLOGIN;
    END IF;
  END
$$;

GRANT reference_reader TO reference_maintainer;

-- CREATE DATABASE has no IF NOT EXISTS; \gexec runs it only when missing.
SELECT 'CREATE DATABASE reference'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'reference')\gexec
