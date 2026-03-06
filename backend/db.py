"""
db.py - Oracle Database Connection and Initialization
Uses oracledb with SYS/SYSDBA (matching your working config)
"""

import oracledb

# ── Edit these to match your Oracle setup ──────────────────────────────────────
DB_CONFIG = {
    "user": "SYS",
    "password": "$DRKansara97",
    "dsn": "localhost:1521/XE",
    "mode": oracledb.SYSDBA,
}
# ───────────────────────────────────────────────────────────────────────────────


def get_connection():
    """Return a new Oracle connection."""
    return oracledb.connect(**DB_CONFIG)


def init_db():
    """Create all tables if they do not already exist."""
    conn = get_connection()
    cur = conn.cursor()

    statements = [
        # ── Users (base identity table) ────────────────────────────────────────
        """
        BEGIN
            EXECUTE IMMEDIATE '
                CREATE TABLE users (
                    user_id     NUMBER(5) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    name        VARCHAR2(150)  NOT NULL,
                    email       VARCHAR2(255)  UNIQUE NOT NULL,
                    password    VARCHAR2(255)  NOT NULL,
                    role        VARCHAR2(20)   NOT NULL CHECK (role IN (''NGO'',''DONOR'')),
                    phone       VARCHAR2(15),
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )';
        EXCEPTION WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """,

        # ── NGO profiles ──────────────────────────────────────────────────────
        """
        BEGIN
            EXECUTE IMMEDIATE '
                CREATE TABLE ngo_profiles (
                    ngo_id            NUMBER(5) PRIMARY KEY,
                    organization_name VARCHAR2(150) NOT NULL,
                    address           VARCHAR2(1000),
                    city              VARCHAR2(100),
                    state             VARCHAR2(100),
                    pincode           VARCHAR2(10),
                    description       VARCHAR2(1000),
                    CONSTRAINT fk_ngo_user FOREIGN KEY (ngo_id) REFERENCES users(user_id)
                )';
        EXCEPTION WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """,

        # ── Donor profiles ────────────────────────────────────────────────────
        """
        BEGIN
            EXECUTE IMMEDIATE '
                CREATE TABLE donor_profiles (
                    donor_id          NUMBER(5) PRIMARY KEY,
                    donor_type        VARCHAR2(30)  NOT NULL,
                    organization_name VARCHAR2(150),
                    address           VARCHAR2(1000),
                    CONSTRAINT fk_donor_user FOREIGN KEY (donor_id) REFERENCES users(user_id)
                )';
        EXCEPTION WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """,

        # ── Requirements posted by NGOs ────────────────────────────────────────
        """
        BEGIN
            EXECUTE IMMEDIATE '
                CREATE TABLE requirements (
                    requirement_id NUMBER(5) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    ngo_id         NUMBER(5)      NOT NULL,
                    title          VARCHAR2(150)  NOT NULL,
                    description    VARCHAR2(1000),
                    quantity       NUMBER(5)      NOT NULL,
                    status         VARCHAR2(20)   DEFAULT ''OPEN''
                                   CHECK (status IN (''OPEN'',''PARTIALLY_FULFILLED'',''FULFILLED'')),
                    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_req_ngo FOREIGN KEY (ngo_id) REFERENCES ngo_profiles(ngo_id)
                )';
        EXCEPTION WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """,

        # ── Donations ─────────────────────────────────────────────────────────
        """
        BEGIN
            EXECUTE IMMEDIATE '
                CREATE TABLE donations (
                    donation_id      NUMBER(5) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    requirement_id   NUMBER(5)     NOT NULL,
                    donor_id         NUMBER(5)     NOT NULL,
                    donation_status  VARCHAR2(20)  NOT NULL
                                     CHECK (donation_status IN (''INITIATED'',''CONFIRMED'',''IN_PROGRESS'',''COMPLETED'',''CANCELLED'')),
                    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_don_req   FOREIGN KEY (requirement_id) REFERENCES requirements(requirement_id),
                    CONSTRAINT fk_don_donor FOREIGN KEY (donor_id)       REFERENCES donor_profiles(donor_id)
                )';
        EXCEPTION WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """,

        # ── Delivery orders (weak entity) ─────────────────────────────────────
        """
        BEGIN
            EXECUTE IMMEDIATE '
                CREATE TABLE delivery_orders (
                    order_id        NUMBER(5) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    donation_id     NUMBER(5)       NOT NULL,
                    provider_name   VARCHAR2(50)    NOT NULL,
                    estimated_cost  NUMBER(10,2),
                    tracking_link   VARCHAR2(255),
                    pickup_time     TIMESTAMP,
                    delivery_status VARCHAR2(30)    NOT NULL
                                    CHECK (delivery_status IN (''NOT_DELIVERED'',''DELIVERING'',''DELIVERED'')),
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_del_don FOREIGN KEY (donation_id) REFERENCES donations(donation_id)
                )';
        EXCEPTION WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """,

        # ── Notifications (weak entity) ────────────────────────────────────────
        """
        BEGIN
            EXECUTE IMMEDIATE '
                CREATE TABLE notifications (
                    notification_id NUMBER(5) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    user_id         NUMBER(5)      NOT NULL,
                    message         VARCHAR2(1000) NOT NULL,
                    is_read         NUMBER(1)      DEFAULT 0 CHECK (is_read IN (0,1)),
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(user_id)
                )';
        EXCEPTION WHEN OTHERS THEN
            IF SQLCODE != -955 THEN RAISE; END IF;
        END;
        """,
    ]

    for stmt in statements:
        cur.execute(stmt)

    conn.commit()
    cur.close()
    conn.close()
    print("✅  All tables verified / created.")
