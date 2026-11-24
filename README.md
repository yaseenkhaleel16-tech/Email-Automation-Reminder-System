# Email Automation & Reminder System

A modular, zero-dependency-ready Python automation project that reads contact and reminder CSV files, personalizes email templates, simulates or sends emails over SMTP, schedules recurring checks, provides a local web dashboard, and exports execution logs and CSV audit reports.

## Features
- **CSV-Driven Workflow**: Manage contacts (`data/contacts.csv`) and reminders (`data/reminders.csv`).
- **Dynamic Template Personalization**: Replace `{{variable}}` placeholders across subject and body (`templates/reminder_email.txt`).
- **Safe Dry-Run Mode**: Validate inputs, test error handling, and generate reports without sending real emails.
- **SMTP Delivery**: Send real emails via `smtplib` and `email.message.EmailMessage` using `.env` credentials.
- **Local Web Dashboard (`dashboard.py`)**: Manage contacts, reminders, templates, and runs at `http://127.0.0.1:8000` with zero third-party packages required.
- **Audit Logs & CSV Reports**: Saves `logs/automation.log` and timestamped `outputs/reminder_report_*.csv`.

## Folder Structure
```text
Email-Automation-Reminder-System/
├── data/
│   ├── contacts.csv
│   └── reminders.csv
├── templates/
│   └── reminder_email.txt
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── loader.py
│   ├── personalizer.py
│   ├── mailer.py
│   ├── scheduler.py
│   └── reporter.py
├── outputs/
├── logs/
├── images/
├── docs/
│   └── architecture.md
├── .env.example
├── .gitignore
├── requirements.txt
├── dashboard.py
├── main.py
└── README.md
```

## Quick Start in VS Code
1. Extract the ZIP and open the `Email-Automation-Reminder-System` folder in **VS Code**.
2. Run a safe dry-run simulation immediately (works out of the box with built-in Python libraries):
   ```bash
   python main.py --dry-run
   ```
3. Launch the interactive local web dashboard:
   ```bash
   ```
   Open `http://127.0.0.1:8000` in your browser.
4. *(Optional)* Configure `.env` from `.env.example` with a Gmail App Password and run live sends:
   ```bash
   python main.py --send
   ```
<img width="1917" height="953" alt="pic 2" src="https://github.com/user-attachments/assets/f3ab9ab5-8600-41cf-9f7a-c2220a355af7" />
