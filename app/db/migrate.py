from sqlalchemy import text
from sqlalchemy.engine import Engine


def _has_table(conn, name: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).fetchone()
    return row is not None


def _table_columns(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
    return {row[1] for row in rows}


def ensure_sqlite_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info('users')")).fetchall()
        columns = {row[1] for row in rows}

        if "phone" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(32)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone)"))

        if "is_email_verified" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_email_verified BOOLEAN DEFAULT 0 NOT NULL"))

        if "is_phone_verified" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_phone_verified BOOLEAN DEFAULT 0 NOT NULL"))

        if not _has_table(conn, "organizations"):
            conn.execute(
                text(
                    """
                    CREATE TABLE organizations (
                        id INTEGER NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        city VARCHAR(120),
                        address VARCHAR(500),
                        latitude FLOAT,
                        longitude FLOAT,
                        specialization VARCHAR(20) NOT NULL,
                        needs_json TEXT,
                        wards_count INTEGER NOT NULL,
                        adopted_yearly_count INTEGER NOT NULL,
                        description TEXT,
                        created_at DATETIME,
                        PRIMARY KEY (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organizations_name ON organizations (name)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organizations_city ON organizations (city)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organizations_specialization ON organizations (specialization)"))

        if _has_table(conn, "animals"):
            ac = _table_columns(conn, "animals")
            alters: list[tuple[str, str]] = [
                ("organization_id", "INTEGER"),
                ("species", "VARCHAR(20) DEFAULT 'cat' NOT NULL"),
                ("breed", "VARCHAR(120)"),
                ("full_description", "TEXT"),
                ("health_checklist_json", "TEXT"),
                ("health_features", "TEXT"),
                ("treatment_required", "TEXT"),
                ("character_tags_json", "TEXT"),
                ("is_vaccinated", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("is_sterilized", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("is_litter_trained", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("is_child_friendly", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("is_animal_friendly", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("has_health_issues", "BOOLEAN DEFAULT 0 NOT NULL"),
                ("urgent_needs_text", "TEXT"),
            ]
            for col, ddl in alters:
                if col not in ac:
                    conn.execute(text(f"ALTER TABLE animals ADD COLUMN {col} {ddl}"))

            ac2 = _table_columns(conn, "animals")
            if "organization_id" in ac2:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_animals_organization_id ON animals (organization_id)"
                    )
                )
            for idx_col in ("species", "is_vaccinated", "is_sterilized", "has_health_issues"):
                if idx_col in ac2:
                    conn.execute(
                        text(f"CREATE INDEX IF NOT EXISTS ix_animals_{idx_col} ON animals ({idx_col})")
                    )

        if _has_table(conn, "volunteer_profiles"):
            vp = _table_columns(conn, "volunteer_profiles")
            vp_alters: list[tuple[str, str]] = [
                ("about_me", "TEXT"),
                ("animal_types_json", "TEXT"),
                ("competencies_json", "TEXT"),
                ("experience_level", "VARCHAR(40)"),
                ("avatar_path", "VARCHAR(500)"),
                ("rating", "FLOAT DEFAULT 0 NOT NULL"),
                ("completed_tasks_count", "INTEGER DEFAULT 0 NOT NULL"),
                ("is_available", "BOOLEAN DEFAULT 1 NOT NULL"),
                ("latitude", "FLOAT"),
                ("longitude", "FLOAT"),
            ]
            for col, ddl in vp_alters:
                if col not in vp:
                    conn.execute(text(f"ALTER TABLE volunteer_profiles ADD COLUMN {col} {ddl}"))
            vp2 = _table_columns(conn, "volunteer_profiles")
            if "experience_level" in vp2:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_volunteer_profiles_experience_level "
                        "ON volunteer_profiles (experience_level)"
                    )
                )
            if "rating" in vp2:
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_volunteer_profiles_rating ON volunteer_profiles (rating)")
                )
            if "is_available" in vp2:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_volunteer_profiles_is_available "
                        "ON volunteer_profiles (is_available)"
                    )
                )

        if not _has_table(conn, "volunteer_reviews"):
            conn.execute(
                text(
                    """
                    CREATE TABLE volunteer_reviews (
                        id INTEGER NOT NULL,
                        volunteer_user_id INTEGER NOT NULL,
                        author_name VARCHAR(255) NOT NULL,
                        author_avatar_path VARCHAR(500),
                        review_date DATETIME NOT NULL,
                        rating INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        created_at DATETIME,
                        PRIMARY KEY (id),
                        FOREIGN KEY(volunteer_user_id) REFERENCES users (id)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_volunteer_reviews_volunteer_user_id "
                    "ON volunteer_reviews (volunteer_user_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_volunteer_reviews_review_date ON volunteer_reviews (review_date)"
                )
            )
