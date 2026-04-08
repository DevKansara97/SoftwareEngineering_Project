"""
db.py - Oracle Database Connection and Initialization
Uses oracledb with SYS/SYSDBA (matching your working config)
"""

import os
import sys

import oracledb


DB_CONFIG = {
    "user": os.getenv("DB_USER", ""),
    "password": os.getenv("DB_PASSWORD", ""),
    "dsn": os.getenv("DB_DSN", "localhost:1521/XE"),
    # "mode": oracledb.SYSDBA,
}

# Fail fast if DB credentials are missing
if not DB_CONFIG["user"] or not DB_CONFIG["password"]:
    print("=" * 60)
    print("  ERROR: DB_USER and DB_PASSWORD not set!")
    print("  Copy .env.example → .env and fill in your credentials.")
    print("=" * 60)
    sys.exit(1)


def get_connection():
    """Return a new Oracle connection."""
    return oracledb.connect(**DB_CONFIG)


def _create_table(cur, ddl: str):
    """Execute a CREATE TABLE inside BEGIN/EXCEPTION so it is idempotent."""
    stmt = f"""
BEGIN
    EXECUTE IMMEDIATE '{ddl}';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -955 THEN RAISE; END IF;
END;
"""
    cur.execute(stmt)


def _table_exists(cur, table_name: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM user_tables WHERE table_name = :1",
        (table_name.upper(),),
    )
    return cur.fetchone()[0] > 0


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*)
        FROM user_tab_columns
        WHERE table_name = :1 AND column_name = :2
        """,
        (table_name.upper(), column_name.upper()),
    )
    return cur.fetchone()[0] > 0


def _constraint_exists(cur, constraint_name: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM user_constraints WHERE constraint_name = :1",
        (constraint_name.upper(),),
    )
    return cur.fetchone()[0] > 0


def _unique_exists_on_column(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*)
        FROM user_cons_columns ucc
        JOIN user_constraints uc
          ON uc.constraint_name = ucc.constraint_name
        WHERE ucc.table_name = :1
          AND ucc.column_name = :2
          AND uc.constraint_type IN ('U', 'P')
        """,
        (table_name.upper(), column_name.upper()),
    )
    return cur.fetchone()[0] > 0


def _add_constraint(cur, constraint_name: str, ddl: str):
    if _constraint_exists(cur, constraint_name):
        return

    try:
        cur.execute(ddl)
    except oracledb.DatabaseError as exc:
        message = str(exc)
        if "ORA-02299" in message:
            print(f"Warning: could not add {constraint_name} because duplicate legacy values already exist.")
            return
        raise


def _has_duplicate_values(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT {column_name}
            FROM {table_name}
            WHERE {column_name} IS NOT NULL
            GROUP BY {column_name}
            HAVING COUNT(*) > 1
        )
        """
    )
    return cur.fetchone()[0] > 0


def init_db():
    """Create all tables if they do not already exist."""
    conn = get_connection()
    cur = conn.cursor()

    _create_table(
        cur,
        """
        CREATE TABLE users (
            user_id    NUMBER(5) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name       VARCHAR2(150)  NOT NULL,
            email      VARCHAR2(255)  UNIQUE NOT NULL,
            password   VARCHAR2(255)  NOT NULL,
            role       VARCHAR2(20)   NOT NULL
                           CHECK (role IN (''NGO'',''DONOR'')),
            phone      VARCHAR2(15)   UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )

    _create_table(
        cur,
        """
        CREATE TABLE ngo_profiles (
            ngo_id            NUMBER(5) PRIMARY KEY,
            organization_name VARCHAR2(150) NOT NULL,
            address           VARCHAR2(1000),
            city              VARCHAR2(100),
            state             VARCHAR2(100),
            pincode           VARCHAR2(10),
            description       VARCHAR2(1000),
            CONSTRAINT fk_ngo_user FOREIGN KEY (ngo_id)
                REFERENCES users(user_id)
        )
        """,
    )

    _create_table(
        cur,
        """
        CREATE TABLE donor_profiles (
            donor_id          NUMBER(5) PRIMARY KEY,
            donor_type        VARCHAR2(30) NOT NULL,
            organization_name VARCHAR2(150),
            address           VARCHAR2(1000),
            CONSTRAINT fk_donor_user FOREIGN KEY (donor_id)
                REFERENCES users(user_id)
        )
        """,
    )

    _create_table(
        cur,
        """
        CREATE TABLE requirements (
            requirement_id NUMBER(5) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            ngo_id         NUMBER(5)     NOT NULL,
            title          VARCHAR2(150) NOT NULL,
            description    VARCHAR2(1000),
            quantity       NUMBER(5)     NOT NULL,
            status         VARCHAR2(30)  DEFAULT ''OPEN''
                               CHECK (status IN
                                   (''OPEN'',''PARTIALLY_FULFILLED'',''FULFILLED'')),
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_req_ngo FOREIGN KEY (ngo_id)
                REFERENCES ngo_profiles(ngo_id)
        )
        """,
    )

    _create_table(
        cur,
        """
        CREATE TABLE donations (
            donation_id     NUMBER(5) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            requirement_id  NUMBER(5)    NOT NULL,
            donor_id        NUMBER(5)    NOT NULL,
            donation_status VARCHAR2(20) NOT NULL
                                CHECK (donation_status IN
                                    (''INITIATED'',''CONFIRMED'',
                                     ''IN_PROGRESS'',''COMPLETED'',''CANCELLED'')),
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_don_req   FOREIGN KEY (requirement_id)
                REFERENCES requirements(requirement_id),
            CONSTRAINT fk_don_donor FOREIGN KEY (donor_id)
                REFERENCES donor_profiles(donor_id)
        )
        """,
    )

    _create_table(
        cur,
        """
        CREATE TABLE drivers (
            driver_id  NUMBER(5) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name       VARCHAR2(150) NOT NULL,
            phone      VARCHAR2(15) UNIQUE NOT NULL,
            vehicle    VARCHAR2(50),
            status     VARCHAR2(20) DEFAULT ''AVAILABLE''
                           CHECK (status IN (''AVAILABLE'',''ON_DELIVERY'',''OFFLINE'')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )

    _create_table(
        cur,
        """
        CREATE TABLE delivery_orders (
            order_id        NUMBER(5) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            donation_id     NUMBER(5)      NOT NULL,
            provider_name   VARCHAR2(50)   NOT NULL,
            driver_id       NUMBER(5),
            estimated_cost  NUMBER(10,2),
            tracking_link   VARCHAR2(255),
            pickup_time     TIMESTAMP,
            delivery_status VARCHAR2(30)   NOT NULL
                                CHECK (delivery_status IN
                                    (''NOT_DELIVERED'',''DELIVERING'',''DELIVERED'')),
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_del_don FOREIGN KEY (donation_id)
                REFERENCES donations(donation_id),
            CONSTRAINT fk_del_driver FOREIGN KEY (driver_id)
                REFERENCES drivers(driver_id)
        )
        """,
    )

    _create_table(
        cur,
        """
        CREATE TABLE notifications (
            notification_id NUMBER(5) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id         NUMBER(5)      NOT NULL,
            message         VARCHAR2(1000) NOT NULL,
            is_read         NUMBER(1)      DEFAULT 0
                                CHECK (is_read IN (0,1)),
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_notif_user FOREIGN KEY (user_id)
                REFERENCES users(user_id)
        )
        """,
    )

    _create_table(
        cur,
        """
        CREATE TABLE login_otp (
            email      VARCHAR2(255) PRIMARY KEY,
            otp_code   VARCHAR2(6)   NOT NULL,
            expires_at TIMESTAMP     NOT NULL,
            attempts   NUMBER(1)     DEFAULT 0
        )
        """,
    )

    _create_table(
        cur,
        """
        CREATE TABLE tracking_locations (
            order_id   NUMBER(5)    PRIMARY KEY,
            lat        NUMBER(10,6) NOT NULL,
            lng        NUMBER(10,6) NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_track_order FOREIGN KEY (order_id)
                REFERENCES delivery_orders(order_id)
        )
        """,
    )

    if _table_exists(cur, "delivery_orders") and not _column_exists(cur, "delivery_orders", "driver_id"):
        cur.execute("ALTER TABLE delivery_orders ADD driver_id NUMBER(5)")

    if _table_exists(cur, "delivery_orders"):
        _add_constraint(
            cur,
            "FK_DEL_DRIVER",
            "ALTER TABLE delivery_orders ADD CONSTRAINT fk_del_driver FOREIGN KEY (driver_id) REFERENCES drivers(driver_id)",
        )

    if (
        _table_exists(cur, "users")
        and not _unique_exists_on_column(cur, "users", "phone")
        and not _has_duplicate_values(cur, "users", "phone")
    ):
        _add_constraint(
            cur,
            "UQ_USERS_PHONE",
            "ALTER TABLE users ADD CONSTRAINT uq_users_phone UNIQUE (phone)",
        )
    elif _table_exists(cur, "users") and _has_duplicate_values(cur, "users", "phone"):
        print("Warning: users.phone contains duplicate legacy values; skipping DB unique constraint.")

    if (
        _table_exists(cur, "drivers")
        and not _unique_exists_on_column(cur, "drivers", "phone")
        and not _has_duplicate_values(cur, "drivers", "phone")
    ):
        _add_constraint(
            cur,
            "UQ_DRIVERS_PHONE",
            "ALTER TABLE drivers ADD CONSTRAINT uq_drivers_phone UNIQUE (phone)",
        )
    elif _table_exists(cur, "drivers") and _has_duplicate_values(cur, "drivers", "phone"):
        print("Warning: drivers.phone contains duplicate legacy values; skipping DB unique constraint.")

    conn.commit()
    cur.close()
    conn.close()
    print("All tables verified / created.")
