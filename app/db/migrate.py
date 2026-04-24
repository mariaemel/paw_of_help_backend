import json

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


_LEGACY_TAG_TOKEN: dict[str, tuple[str, str]] = {
    "Стерилизована": ("health_care", "sterilized"),
    "Комплексно привита": ("health_care", "vaccinated_full"),
    "Обработана от паразитов": ("health_care", "dewormed"),
    "Привита": ("health_care", "vaccinated"),
    "Спокойная": ("character", "calm"),
    "Ласковая": ("character", "affectionate"),
    "Боится громких звуков": ("character", "afraid_loud"),
    "Дружелюбная": ("character", "friendly"),
    "Активная": ("character", "active"),
    "Активный": ("character", "active"),
    "Контактный": ("character", "contact"),
}


def _backfill_animal_catalog_assignments_from_legacy_json(conn) -> None:
    acols = _table_columns(conn, "animals")
    if "health_checklist_json" not in acols and "character_tags_json" not in acols:
        return
    if not _has_table(conn, "animal_catalog_items"):
        return
    rows = conn.execute(text("SELECT id, kind, slug FROM animal_catalog_items")).fetchall()
    key_to_id: dict[tuple[str, str], int] = {(r[1], r[2]): int(r[0]) for r in rows}

    def _resolve_token(tok: str) -> int | None:
        t = tok.strip()
        if not t:
            return None
        if t in _LEGACY_TAG_TOKEN:
            k, s = _LEGACY_TAG_TOKEN[t]
            return key_to_id.get((k, s))
        for kind in ("health_care", "character"):
            cid = key_to_id.get((kind, t))
            if cid is not None:
                return cid
        return None

    animals = conn.execute(
        text("SELECT id, health_checklist_json, character_tags_json FROM animals")
    ).fetchall()
    for aid, hraw, craw in animals:
        tokens: list[str] = []
        for raw in (hraw, craw):
            if not raw:
                continue
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    tokens.extend(str(x) for x in data)
            except (json.JSONDecodeError, TypeError):
                continue
        seen: set[int] = set()
        for tok in tokens:
            cid = _resolve_token(tok)
            if cid is None or cid in seen:
                continue
            seen.add(cid)
            conn.execute(
                text(
                    "INSERT OR IGNORE INTO animal_catalog_assignments (animal_id, catalog_item_id) "
                    "VALUES (:aid, :cid)"
                ),
                {"aid": int(aid), "cid": int(cid)},
            )


_VOLUNTEER_COMPETENCY_SEED: tuple[tuple[str, str, int], ...] = (
    ("walk", "Выгул / Уход", 10),
    ("photo_video", "Фото / Видеосъемка", 20),
    ("foster", "Передержка", 30),
    ("texts_social", "Тексты / Соцсети", 40),
    ("manual", "Помощь руками", 50),
    ("auto", "Автопомощь", 60),
    ("medical", "Медицинская помощь", 70),
)


def _ensure_volunteer_competency_schema(conn) -> None:
    if not _has_table(conn, "volunteer_profiles"):
        return
    if not _has_table(conn, "volunteer_competency_items"):
        conn.execute(
            text(
                """
                CREATE TABLE volunteer_competency_items (
                    id INTEGER NOT NULL,
                    slug VARCHAR(64) NOT NULL,
                    label VARCHAR(255) NOT NULL,
                    sort_order INTEGER NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    PRIMARY KEY (id),
                    CONSTRAINT uq_volunteer_competency_slug UNIQUE (slug)
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_volunteer_competency_items_sort "
                "ON volunteer_competency_items (sort_order)"
            )
        )
    if not _has_table(conn, "volunteer_competency_assignments"):
        conn.execute(
            text(
                """
                CREATE TABLE volunteer_competency_assignments (
                    id INTEGER NOT NULL,
                    volunteer_profile_id INTEGER NOT NULL,
                    competency_item_id INTEGER NOT NULL,
                    PRIMARY KEY (id),
                    CONSTRAINT uq_vol_prof_comp_item UNIQUE (volunteer_profile_id, competency_item_id),
                    FOREIGN KEY(volunteer_profile_id) REFERENCES volunteer_profiles (id) ON DELETE CASCADE,
                    FOREIGN KEY(competency_item_id) REFERENCES volunteer_competency_items (id) ON DELETE RESTRICT
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_vol_comp_assign_profile "
                "ON volunteer_competency_assignments (volunteer_profile_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_vol_comp_assign_item "
                "ON volunteer_competency_assignments (competency_item_id)"
            )
        )


def _seed_volunteer_competency_items_if_empty(conn) -> None:
    if not _has_table(conn, "volunteer_competency_items"):
        return
    cnt = conn.execute(text("SELECT COUNT(*) FROM volunteer_competency_items")).scalar()
    if cnt is not None and int(cnt) > 0:
        return
    for slug, label, sort_order in _VOLUNTEER_COMPETENCY_SEED:
        conn.execute(
            text(
                "INSERT INTO volunteer_competency_items (slug, label, sort_order, is_active) "
                "VALUES (:slug, :label, :so, 1)"
            ),
            {"slug": slug, "label": label, "so": sort_order},
        )


def _backfill_volunteer_competency_assignments(conn) -> None:
    if not _has_table(conn, "volunteer_competency_assignments"):
        return
    vp_cols = _table_columns(conn, "volunteer_profiles")
    if "competencies_json" not in vp_cols:
        return
    rows = conn.execute(text("SELECT id, slug FROM volunteer_competency_items")).fetchall()
    if not rows:
        return
    slug_to_id: dict[str, int] = {str(r[1]).lower(): int(r[0]) for r in rows}
    profiles = conn.execute(text("SELECT id, competencies_json FROM volunteer_profiles")).fetchall()
    for pid, craw in profiles:
        if not craw:
            continue
        try:
            data = json.loads(craw)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, list):
            continue
        seen: set[int] = set()
        for tok in data:
            sid = str(tok).strip().lower()
            cid = slug_to_id.get(sid)
            if cid is None or cid in seen:
                continue
            seen.add(cid)
            conn.execute(
                text(
                    "INSERT OR IGNORE INTO volunteer_competency_assignments "
                    "(volunteer_profile_id, competency_item_id) VALUES (:pid, :cid)"
                ),
                {"pid": int(pid), "cid": int(cid)},
            )


def _purge_feature_filter_catalog(conn) -> None:
    if not _has_table(conn, "animal_catalog_items"):
        return
    if _has_table(conn, "animal_catalog_assignments"):
        conn.execute(
            text(
                "DELETE FROM animal_catalog_assignments WHERE catalog_item_id IN "
                "(SELECT id FROM animal_catalog_items WHERE kind = 'feature_filter')"
            )
        )
    conn.execute(text("DELETE FROM animal_catalog_items WHERE kind = 'feature_filter'"))


def _drop_sqlite_columns_if_exist(conn, table: str, columns: list[str]) -> None:
    for col in columns:
        if not col.replace("_", "").isalnum():
            continue
        if col not in _table_columns(conn, table):
            continue
        try:
            conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {col}"))
        except Exception:
            pass


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
                        owner_user_id INTEGER,
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
                        PRIMARY KEY (id),
                        FOREIGN KEY(owner_user_id) REFERENCES users (id)
                    )
                    """
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_organizations_owner_user_id ON organizations (owner_user_id)")
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organizations_name ON organizations (name)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organizations_city ON organizations (city)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organizations_specialization ON organizations (specialization)"))
        else:
            org_cols = _table_columns(conn, "organizations")
            if "owner_user_id" not in org_cols:
                conn.execute(text("ALTER TABLE organizations ADD COLUMN owner_user_id INTEGER"))
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_organizations_owner_user_id ON organizations (owner_user_id)")
            )

        if not _has_table(conn, "knowledge_articles"):
            conn.execute(
                text(
                    """
                    CREATE TABLE knowledge_articles (
                        id INTEGER NOT NULL,
                        author_user_id INTEGER,
                        owner_role VARCHAR(20) NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        summary VARCHAR(500),
                        content TEXT NOT NULL,
                        category VARCHAR(40) NOT NULL,
                        read_minutes INTEGER NOT NULL,
                        is_context_tip BOOLEAN NOT NULL,
                        is_published BOOLEAN NOT NULL,
                        is_archived BOOLEAN NOT NULL,
                        created_at DATETIME,
                        updated_at DATETIME,
                        PRIMARY KEY (id),
                        FOREIGN KEY(author_user_id) REFERENCES users (id)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_knowledge_articles_category "
                    "ON knowledge_articles (category)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_knowledge_articles_is_context_tip "
                    "ON knowledge_articles (is_context_tip)"
                )
            )

        if not _has_table(conn, "events"):
            conn.execute(
                text(
                    """
                    CREATE TABLE events (
                        id INTEGER NOT NULL,
                        organization_id INTEGER,
                        title VARCHAR(255) NOT NULL,
                        summary VARCHAR(500),
                        description TEXT NOT NULL,
                        city VARCHAR(120),
                        address VARCHAR(500),
                        format VARCHAR(20) NOT NULL,
                        help_type VARCHAR(40),
                        starts_at DATETIME NOT NULL,
                        ends_at DATETIME,
                        latitude FLOAT,
                        longitude FLOAT,
                        is_published BOOLEAN NOT NULL,
                        is_archived BOOLEAN NOT NULL,
                        created_at DATETIME,
                        PRIMARY KEY (id),
                        FOREIGN KEY(organization_id) REFERENCES organizations (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_city ON events (city)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_format ON events (format)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_help_type ON events (help_type)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_starts_at ON events (starts_at)"))

        if not _has_table(conn, "help_requests"):
            conn.execute(
                text(
                    """
                    CREATE TABLE help_requests (
                        id INTEGER NOT NULL,
                        organization_id INTEGER NOT NULL,
                        animal_id INTEGER,
                        title VARCHAR(255) NOT NULL,
                        description TEXT NOT NULL,
                        city VARCHAR(120),
                        address VARCHAR(500),
                        latitude FLOAT,
                        longitude FLOAT,
                        help_type VARCHAR(40) NOT NULL,
                        is_urgent BOOLEAN NOT NULL,
                        volunteer_needed BOOLEAN NOT NULL,
                        volunteer_requirements TEXT,
                        volunteer_competencies_json TEXT,
                        target_amount FLOAT,
                        collected_amount FLOAT NOT NULL,
                        deadline_at DATETIME,
                        deadline_note VARCHAR(255),
                        media_path VARCHAR(500),
                        status VARCHAR(20) NOT NULL,
                        is_published BOOLEAN NOT NULL,
                        is_archived BOOLEAN NOT NULL,
                        created_at DATETIME,
                        updated_at DATETIME,
                        PRIMARY KEY (id),
                        FOREIGN KEY(organization_id) REFERENCES organizations (id),
                        FOREIGN KEY(animal_id) REFERENCES animals (id)
                    )
                    """
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_help_requests_organization_id ON help_requests (organization_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_help_requests_animal_id ON help_requests (animal_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_help_requests_city ON help_requests (city)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_help_requests_help_type ON help_requests (help_type)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_help_requests_status ON help_requests (status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_help_requests_is_urgent ON help_requests (is_urgent)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_help_requests_deadline_at ON help_requests (deadline_at)"))
        else:
            _drop_sqlite_columns_if_exist(conn, "help_requests", ["urgency_level"])
            hr_cols = _table_columns(conn, "help_requests")
            if "deadline_note" not in hr_cols:
                conn.execute(text("ALTER TABLE help_requests ADD COLUMN deadline_note VARCHAR(255)"))

        if _has_table(conn, "animals"):
            ac = _table_columns(conn, "animals")
            alters: list[tuple[str, str]] = [
                ("organization_id", "INTEGER"),
                ("species", "VARCHAR(20) DEFAULT 'cat' NOT NULL"),
                ("breed", "VARCHAR(120)"),
                ("full_description", "TEXT"),
                ("health_features", "TEXT"),
                ("treatment_required", "TEXT"),
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
            if "species" in ac2:
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_animals_species ON animals (species)")
                )

            _drop_sqlite_columns_if_exist(
                conn,
                "animals",
                [
                    "is_vaccinated",
                    "is_sterilized",
                    "is_litter_trained",
                    "is_child_friendly",
                    "is_animal_friendly",
                    "has_health_issues",
                ],
            )

        if not _has_table(conn, "animal_catalog_items"):
            conn.execute(
                text(
                    """
                    CREATE TABLE animal_catalog_items (
                        id INTEGER NOT NULL,
                        kind VARCHAR(32) NOT NULL,
                        slug VARCHAR(64) NOT NULL,
                        label VARCHAR(255) NOT NULL,
                        keywords_json TEXT,
                        sort_order INTEGER NOT NULL,
                        is_active BOOLEAN NOT NULL,
                        PRIMARY KEY (id),
                        CONSTRAINT uq_animal_catalog_kind_slug UNIQUE (kind, slug)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_animal_catalog_items_kind "
                    "ON animal_catalog_items (kind)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_animal_catalog_items_sort "
                    "ON animal_catalog_items (sort_order)"
                )
            )
        
        if (
            _has_table(conn, "animals")
            and _has_table(conn, "animal_catalog_items")
            and not _has_table(conn, "animal_catalog_assignments")
        ):
            conn.execute(
                text(
                    """
                    CREATE TABLE animal_catalog_assignments (
                        id INTEGER NOT NULL,
                        animal_id INTEGER NOT NULL,
                        catalog_item_id INTEGER NOT NULL,
                        PRIMARY KEY (id),
                        CONSTRAINT uq_animal_cat_assign_animal_item UNIQUE (animal_id, catalog_item_id),
                        FOREIGN KEY(animal_id) REFERENCES animals (id) ON DELETE CASCADE,
                        FOREIGN KEY(catalog_item_id) REFERENCES animal_catalog_items (id) ON DELETE RESTRICT
                    )
                    """
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_animal_cat_assign_animal_id "
                    "ON animal_catalog_assignments (animal_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_animal_cat_assign_catalog_item_id "
                    "ON animal_catalog_assignments (catalog_item_id)"
                )
            )

        if _has_table(conn, "animals") and _has_table(conn, "animal_catalog_assignments"):
            _backfill_animal_catalog_assignments_from_legacy_json(conn)

        _purge_feature_filter_catalog(conn)

        if _has_table(conn, "animals"):
            _drop_sqlite_columns_if_exist(
                conn,
                "animals",
                ["health_checklist_json", "character_tags_json", "health_info", "character_info"],
            )

        if _has_table(conn, "volunteer_profiles"):
            vp = _table_columns(conn, "volunteer_profiles")
            vp_alters: list[tuple[str, str]] = [
                ("about_me", "TEXT"),
                ("animal_types_json", "TEXT"),
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
            _drop_sqlite_columns_if_exist(
                conn,
                "volunteer_profiles",
                ["skills", "experience", "preferred_help_format", "animal_categories"],
            )
            _ensure_volunteer_competency_schema(conn)
            _seed_volunteer_competency_items_if_empty(conn)
            _backfill_volunteer_competency_assignments(conn)
            _drop_sqlite_columns_if_exist(conn, "volunteer_profiles", ["competencies_json"])

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
