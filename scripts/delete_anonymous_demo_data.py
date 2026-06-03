"""Delete anonymous/demo app data without touching textbook or vector rows."""

from __future__ import annotations

from curriculum_engine.database import repository_from_env


def main() -> int:
    repository = repository_from_env()
    if repository is None:
        raise SystemExit("DATABASE_URL or SUPABASE_DB_URL is required")

    with repository._connect() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from learners where learner_id = %s", ("anonymous",))
            deleted = cur.rowcount
    print(f"deleted anonymous learner rows: {deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
