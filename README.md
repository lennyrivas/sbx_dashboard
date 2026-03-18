# Warehouse Dashboard Module

## Project Description

This project is a comprehensive **Warehouse Analytics Dashboard** built with [Streamlit](https://streamlit.io/). It is designed to streamline the management of pallet data, reconcile orders against shipments, and provide deep insights into stock levels and warehouse operations.

### Key Features

- **Orders vs. Pallets Analysis**: Automatically compares loaded order files (CSV/XLSX) with removed pallets to detect discrepancies in quantities or pallet counts.
- **Stock Level Monitoring**: Real-time view of current stock with advanced filtering (by article, date, packaging type). Includes historical stock level charts.
- **Pallet Removal Tool (PID Generator)**: Intelligent assistant for selecting specific pallets (PIDs) for removal orders, optimizing for FIFO and location priority (e.g., prioritizing specific storage zones).
- **Automated Data Retrieval**: Integrated Selenium-based downloader that logs into the `ihka.schaeflein.de` portal to fetch the latest stock and movement reports automatically.
- **Statistics & Reporting**: Monthly performance reports, "Top 5" rankings for sent/received goods, and stagnant stock analysis (aging inventory).
- **Multi-language Support**: Fully localized User Interface in Polish (PL) and English (EN).

---

## Configuration

### 1. Secrets Setup (`secrets.toml`)

To secure sensitive information such as the admin password for settings and credentials for the external data portal, this application uses Streamlit's secrets management.

**Local Development:**
Create a file named `secrets.toml` inside the `.streamlit` folder in your project root directory (create the folder if it doesn't exist).

**File Path:** `.streamlit/secrets.toml`

**Content:**

```toml
# Password required to access the "Settings" tab within the dashboard
ADMIN_PASSWORD = "your_secure_admin_password"

# Credentials for the IHKA portal (used by the auto-downloader)
IHKA_USER = "your_ihka_username"
IHKA_PASSWORD = "your_ihka_password"
```

> **Warning:** Never commit `secrets.toml` to your Git repository. Ensure it is added to your `.gitignore`.

**Streamlit Cloud Deployment:**
If deploying to Streamlit Cloud, do not create the file. Instead, go to your App Settings -> **Secrets** and paste the TOML content there.

### 2. Running the Application

Ensure you have Python installed and the required dependencies (pandas, streamlit, selenium, plotly, openpyxl, etc.).

```bash
pip install -r requirements.txt
streamlit run main.py
```
