# सेवा-Connect 
# An NGO Resource and Donation Management System

A web-based platform designed to connect **NGOs**, **Donors**, and **third-party delivery service providers** (such as Uber, Rapido, Porter, etc.) to enable transparent, efficient, and real-world donation pickup and delivery.

This project is developed as part of the **CSE408 – Software Engineering Lab**.

---

## 📌 Project Overview

In many real-world scenarios, NGOs and donors face challenges in coordinating donations, arranging logistics, and tracking deliveries. This platform addresses these issues by acting as an **orchestration layer** that:

- Allows NGOs to post customized requirements
- Enables donors to search NGOs and commit donations
- Integrates third-party delivery services for cost estimation and tracking
- Provides transparency through notifications and delivery status updates

⚠️ **Note:**  
The platform itself does **not** perform deliveries. It integrates with existing third-party logistics providers.

---

## 🎯 Key Features

### NGO
- Secure registration and login
- Add and manage donation requirements
- Receive notifications on donor activity
- Track delivery status

### Donor
- Secure registration and login
- Search NGOs by requirements and location
- Confirm donations
- View delivery options and estimated costs from third-party providers
- Track delivery and receive acknowledgements

### Delivery Integration
- Third-party delivery service selection (Uber / Rapido / Porter – mocked)
- Cost estimation and provider comparison
- Live delivery tracking (simulated for prototype)

---

## 🧱 System Architecture (High-Level)

- **Frontend:** Web-based UI (React / HTML / CSS / JS)
- **Backend:** RESTful API (Java / Node.js / Python)
- **Database:** Relational Database (MySQL / PostgreSQL)
- **External Services:** Third-party delivery APIs (mocked for academic prototype)

---

## 🗂️ Database Schema (Entities)

- User
- NGO
- Donor
- Requirement
- Donation
- Delivery Order
- Notification

The schema is fully normalized and supports role-based access and third-party integration.

---

## 🧭 Application Flow

1. NGO registers and posts requirements
2. Donor searches NGOs and selects a requirement
3. Donor confirms donation
4. System fetches delivery options from third-party services
5. Donor selects delivery provider
6. Delivery order is created
7. NGO and donor track delivery status

---

## 📐 UML Diagrams Included

- Use Case Diagram
- ER Diagram
- (Optional) Sequence Diagram

---

## 🧪 Development Status

- [x] Requirement Analysis
- [x] Database Design
- [x] UML Diagrams
- [ ] Frontend Implementation
- [ ] Backend API Development
- [ ] Third-Party API Mocking
- [ ] Testing & Validation

---

## ⚙️ Tech Stack (Proposed)

- **Frontend:** React.js, HTML5, CSS3, Tailwind
- **Backend:** Node.js / Java Spring Boot
- **Database:** MySQL / PostgreSQL
- **Version Control:** Git & GitHub
- **APIs:** Mocked Third-Party Delivery APIs

---

## 🚧 Assumptions & Limitations

- Third-party delivery APIs are mocked for academic purposes
- Real integration requires business partnerships and API credentials
- No real payment gateway is implemented in the prototype

---

## 🔮 Future Enhancements

- Real-time API integration with delivery partners
- Payment gateway integration
- Mobile application
- Analytics dashboard for NGOs and donors
- Admin panel for platform monitoring

---

## 👥 Project Team

- **Project Leader:** Name (Roll No)
- Team Member 2
- Team Member 3
- Team Member 4
- Team Member 5

---

## 📄 License

This project is developed for **academic purposes only** under the Software Engineering course.

---

## 🙌 Acknowledgement

This project is developed as part of **CSE408 – Software Engineering Lab**, under the guidance of the course instructor.

