# सेवा Connect – NGO Resource & Donation Management System
**CSE 408 Software Engineering | Group 4 | Ahmedabad University**

---

## Tech Stack

| Layer        | Technology                        |
|-------------|-----------------------------------|
| Backend      | Python 3.10+ · Flask 3.x          |
| Database     | Oracle XE (oracledb driver)       |
| Frontend     | HTML5 · CSS3 · Vanilla JavaScript |
| Templating   | Jinja2 (via Flask)                |
| Auth         | SHA-256 hashed passwords (session)|
| API Style    | RESTful JSON APIs                 |

---

## Project Structure

```
seva-connect/
├── backend/
│   ├── app.py                  ← Flask entry point (run this)
│   ├── db.py                   ← Oracle connection + table init
│   └── routes/
│       ├── auth.py             ← Register / Login / Logout
│       ├── ngo.py              ← NGO profile management
│       ├── donor.py            ← Donor profile + history
│       ├── requirements.py     ← CRUD for NGO requirements
│       ├── donations.py        ← Donation lifecycle
│       ├── delivery.py         ← Delivery orders + cost estimation
│       ├── notifications.py    ← Notification read/write
│       └── search.py           ← Search & filter module
├── frontend/
│   ├── templates/
│   │   ├── base.html           ← Shared navbar/footer layout
│   │   ├── index.html          ← Landing page
│   │   ├── login.html          ← Login page
│   │   ├── register.html       ← Registration (NGO + Donor)
│   │   ├── ngo_dashboard.html  ← NGO dashboard
│   │   ├── ngo_requirements.html ← Requirement management
│   │   ├── donor_dashboard.html  ← Donor dashboard
│   │   ├── donor_search.html   ← Search & filter requirements
│   │   ├── donate.html         ← Donation + delivery booking
│   │   ├── tracking.html       ← Live tracking page
│   │   └── notifications.html  ← Notification centre
│   └── static/
│       ├── css/style.css       ← Main stylesheet (earthy palette)
│       └── js/api.js           ← Shared JS utilities & API helpers
└── requirements.txt
```

---

## Setup Instructions

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

Or individually:
```bash
pip install flask flask-cors oracledb
```

### 2. Configure your Oracle credentials

Open `backend/db.py` and update the `DB_CONFIG` block:

```python
DB_CONFIG = {
    "user":     "SYS",
    "password": "$DRKansara97",   # ← your password
    "dsn":      "localhost:1521/XE",
    "mode":     oracledb.SYSDBA,
}
```

> **Tip:** If you prefer to use a regular schema (not SYSDBA), create a user:
> ```sql
> CREATE USER seva_user IDENTIFIED BY YourPassword123#;
> GRANT CONNECT, RESOURCE, DBA TO seva_user;
> ```
> Then change `user`, `password`, and remove `mode`.

### 3. Run the application

```bash
cd backend
python app.py
```

The server starts at **http://localhost:5000**

- On first run, all 7 Oracle tables are created automatically.

---

## Database Tables Created

| Table              | Type   | Description                          |
|--------------------|--------|--------------------------------------|
| `users`            | Strong | All users (NGO + Donor base record)  |
| `ngo_profiles`     | Strong | NGO-specific info (FK → users)       |
| `donor_profiles`   | Strong | Donor-specific info (FK → users)     |
| `requirements`     | Strong | Items NGOs need                      |
| `donations`        | Strong | Donor commits to a requirement       |
| `delivery_orders`  | Weak   | Delivery booking per donation        |
| `notifications`    | Weak   | System notifications per user        |

---

## API Endpoints Reference

### Auth (`/api/auth`)
| Method | Path        | Description       |
|--------|-------------|-------------------|
| POST   | `/register` | Register user     |
| POST   | `/login`    | Login             |
| POST   | `/logout`   | Logout            |
| GET    | `/me`       | Get user info     |

### NGO (`/api/ngo`)
| Method | Path      | Description          |
|--------|-----------|----------------------|
| GET    | `/profile`| Get NGO profile      |
| PUT    | `/profile`| Update NGO profile   |
| GET    | `/all`    | List all NGOs        |

### Requirements (`/api/requirements`)
| Method | Path          | Description              |
|--------|---------------|--------------------------|
| POST   | `/add`        | Post new requirement     |
| GET    | `/ngo`        | Get NGO's requirements   |
| GET    | `/all`        | Get all open requirements|
| PUT    | `/update`     | Update requirement       |
| DELETE | `/delete`     | Delete requirement       |
| GET    | `/<id>`       | Get single requirement   |

### Donations (`/api/donations`)
| Method | Path      | Description            |
|--------|-----------|------------------------|
| POST   | `/create` | Create donation        |
| PUT    | `/status` | Update status          |
| GET    | `/<id>`   | Get donation details   |

### Delivery (`/api/delivery`)
| Method | Path               | Description                  |
|--------|--------------------|------------------------------|
| GET    | `/estimate`        | Mock cost estimates (INR)    |
| POST   | `/create`          | Create delivery order        |
| GET    | `/<order_id>`      | Get order details            |
| PUT    | `/status`          | Update delivery status       |
| GET    | `/donation/<id>`   | Get order by donation ID     |

### Search (`/api/search`)
| Method | Path             | Description                       |
|--------|------------------|-----------------------------------|
| GET    | `/requirements`  | Filter by title, status, city, qty|

### Notifications (`/api/notifications`)
| Method | Path            | Description               |
|--------|-----------------|---------------------------|
| GET    | `/`             | Get user notifications    |
| PUT    | `/mark-read`    | Mark one or all as read   |
| GET    | `/unread-count` | Count of unread           |

---

## Functional Requirements Mapping

| FR   | Description                                     | Implemented In                     |
|------|-------------------------------------------------|------------------------------------|
| FR-1 | NGO registration and login                      | routes/auth.py                     |
| FR-2 | NGO customised requirements                     | routes/requirements.py             |
| FR-3 | NGO notification for fulfilled requirements     | routes/donations.py + notifications|
| FR-4 | NGO pickup time selection                       | routes/delivery.py                 |
| FR-5 | NGO live tracking of donations                  | routes/delivery.py + tracking.html |
| FR-6 | NGO responsive UI                               | frontend CSS (mobile-first)        |
| FR-7 | Donor registration and login                    | routes/auth.py                     |
| FR-8 | Donor search by requirements                    | routes/search.py + donor_search    |
| FR-9 | Delivery cost calculation                       | routes/delivery.py (estimate)      |
| FR-10| Responsive donor UI                             | frontend CSS                       |
| FR-11| Acknowledgement proof for donor                 | donate.html (confirmation step)    |
| FR-12| Service provider transport notification         | routes/delivery.py + notifications |
| FR-13| Provider contact details                        | routes/delivery.py                 |
| FR-14| Provider pickup/dropoff time                    | routes/delivery.py                 |
| FR-15| Provider live updates                           | tracking.html + delivery.py        |

---

## Notes / Customisations

- **Passwords** use SHA-256. To upgrade to bcrypt: `pip install flask-bcrypt` and update `hash_password()` in `routes/auth.py`.
- **Delivery cost estimation** is mocked. Replace `routes/delivery.py → estimate_cost()` with real Porter/Rapido/Uber API calls.
- **Live tracking** uses a mock URL. Integrate Google Maps JS SDK in `tracking.html` for real GPS tracking.
- **Email notifications** (EmailJS) – add EmailJS calls in `routes/notifications.py → _notify()` or call from the frontend JS.
- **Session storage**: Flask sessions are used server-side; user info is also stored in `localStorage` for frontend state.

---

*Seva Connect – Bridging NGOs and Donors | Group 4, CSE 408*
