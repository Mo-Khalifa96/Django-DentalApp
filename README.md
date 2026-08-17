# DentalTech

A comprehensive, multi-branch dental clinic management platform built with **Django**, designed to run the full day-to-day operations of a dental practice — from the moment a patient walks in, through treatment, billing, and insurance claims. The system supports clinics operating across one or several branches, with each staff member seeing only the information relevant to their role and location.

---

## Overview

Running a dental clinic involves juggling a lot of moving pieces at once: patient records, appointment calendars, treatment histories, billing, insurance paperwork, lab work, inventory, and staff schedules — often spread across spreadsheets, paper charts, and disconnected tools. DentalTech brings all of this into a single system, so that:

- Receptionists can book appointments without double-booking a doctor or a room.
- Dentists can see a patient's full treatment and visit history the moment they open a chart.
- Front-desk and billing staff can generate accurate invoices and track what's been paid, what's outstanding, and what insurance has covered — automatically.
- Clinic owners get a live dashboard of patient volume, appointments, and revenue across every branch.
- Every action is scoped to the right branch and the right role, so staff only see what they need to.

---

## Key Features

### Patient Records & Dental Charts
- Full patient profiles with contact details, allergies, blood type, and insurance information.
- An interactive dental chart (using standard international tooth numbering) that tracks the condition of every tooth — healthy, filled, cracked, missing, and more — created automatically the moment a patient is registered.
- Patient visit history, including notes, procedures performed, costs, and uploaded X-rays.

### Smart Appointment Scheduling
- Book appointments for existing patients or register a brand-new patient on the spot, all in one step.
- Automatic conflict detection — the system will never let two appointments overlap for the same doctor.
- Automated WhatsApp reminders sent to patients ahead of their appointment.
- A live "today's appointments" view for front-desk staff and doctors.

### Treatment Planning
- Build multi-step treatment plans with itemised procedures, cost breakdowns, and instalment payment options.
- Track the progress of each treatment item individually — pending, in progress, or completed.

### Billing, Invoicing & Payments
- Generate bills directly from patient visits, with costs calculated automatically.
- Turn any bill into a fully formatted, tax-compliant invoice with one click.
- Record payments by cash, card, bank transfer, mobile wallet, or insurance — with running totals updated instantly.
- Automatic tracking of what's been paid and what's still outstanding, per patient and clinic-wide.

### Insurance Management
- Maintain a directory of insurance providers with their coverage terms, annual limits, and deductibles.
- Every patient automatically gets an insurance coverage profile, ready to be filled in with their provider, member ID, and policy dates.
- Insurance usage is tracked automatically as claims are processed throughout the year.

### Lab Work & Sterilization Tracking
- Send and track lab orders for crowns, dentures, and other lab-fabricated work.
- Maintain sterilization logs for instrument sets, supporting clinic hygiene and compliance records.

### Inventory & Supplies
- Track stock levels for consumables and equipment, with low-stock alerts and supplier information.

### Patient Recall & Follow-Up
- Schedule follow-up reminders for checkups, post-procedure care, or overdue treatments, with status tracking from "pending" through "confirmed" or "declined."

### Multi-Branch Support
- Every piece of data — patients, appointments, bills, inventory — is tied to a specific branch.
- Staff only ever see and act on the branch (or branches) they're assigned to, keeping multi-location clinics organised and secure.

### Live Dashboard
- A real-time overview of patient counts, today's appointments, monthly revenue, and outstanding balances — tailored to what each role is permitted to see.

---

## Modules Overview

| Module | What it does |
|---|---|
| **Patients** | Patient records, dental charts, contact and medical information |
| **Appointments** | Scheduling, conflict checking, WhatsApp reminders |
| **Visit History** | Record of every patient visit, procedures performed, and X-rays |
| **Treatment Plans** | Multi-step treatment planning with cost tracking |
| **Billing** | Bill generation tied to patient visits |
| **Invoices** | Tax-compliant, sequentially numbered invoices |
| **Transactions** | Payment recording across all payment methods |
| **Insurance** | Insurance provider directory and per-patient coverage tracking |
| **Patient Recalls** | Follow-up and recall scheduling |
| **Labs & Lab Orders** | Outsourced lab work tracking |
| **Sterilization Logs** | Instrument sterilization records |
| **Doctor Schedules** | Weekly doctor availability and exceptions |
| **Waiting Room** | Live patient waiting queue per branch |
| **Procedures & Inventory** | Clinic procedure catalogue and their standard prices |
| **Inventory** | Clinic supply stock |
| **Dashboard** | Clinic-wide statistics and financial overview |

---

## Roles & Permissions

Every staff member is assigned a role, and every role comes with a sensible default set of permissions — though individual permissions can also be fine-tuned per staff member if needed.

| Role | What they can typically do |
|---|---|
| **Admin** | Full access to everything across all branches |
| **Dentist** | Manage their own patients, appointments, treatment plans, and visit records |
| **Receptionist** | Book appointments, manage patient records, handle recalls, create bills and invoices |
| **Assistant** | Manage inventory, lab orders, and sterilization logs |
| **Accountant** | Manage billing, invoices, transactions, and insurance records, with full financial reporting access |

As mentioned, these are the default roles and permissions across the system, however the admin is also granted the ability to add or remove certain permissions for certain users as they see fit. 

Access is also scoped by branch — a staff member assigned to one branch will not see patients, appointments, or financial data belonging to another branch, unless they hold clinic-wide (admin) access.

---

## Technology Stack

| Type | Stack |
|---|---|
| Backend | Python, Django, Django REST Framework |
| Database | PostgreSQL |
| Background Jobs | Django-Q2 |
| Messaging | WhatsApp Business Cloud API |
| Backup Storage | Oracle's Object Storage |
| Deployment | Docker, Docker Compose, Nginx, Gunicorn |
| Hosting | Oracle Cloud Infrastructure |
| API Documentation | Swagger / OpenAPI |

---

## Deployment

DentalTech runs in Docker containers and is deployed on Oracle Cloud Infrastructure, with automated deployment and rollback through GitHub Actions. Daily data backups are uploaded stored securely in oracle object storage, separate from the server itself, and storing up to 7 separate copies taken for the last 7 days from any given date, ensuring therefore that patient and clinic data are never at risk of loss or corruption.

### Production

- Full container orchestration via **Docker Compose**
- HTTPS-secured **Nginx + Gunicorn** stack
- Production environment hosted on **Oracle Cloud Infrastructure**
- Daily database backup to **Oracle's Object Storage**
- SSL certificates via Certbot

### Development (local)

- Separate development environment for building and testing
- Twilio sandbox for testing whatsapp messages and appointment reminders
- SMTP4Dev for local email previews
- Automatic data seeding upon running
- Employs **pytest** for testing, with around 900 tests covering the entire application
- Employs Django **silk** and **locust** for profiling and performance testing

Start locally with:

```bash
git clone https://github.com/Mo-Khalifa96/Django-DentalApp.git
cd Django-DentalApp
docker compose --profile dev up --build
```

Or use the deploy script:

```bash
git clone https://github.com/Mo-Khalifa96/Django-DentalApp.git
cd Django-DentalApp
chmod +x deploy.local.sh
./deploy.local.sh
```

---

## Author

**Mohamed Khalifa**
Data Scientist | Backend Developer
[GitHub](https://github.com/Mo-Khalifa96) | [LinkedIn](https://www.linkedin.com/in/mohamed-khalifa-182015175/)

---

## License

This project is licensed under the [MIT License](LICENSE).