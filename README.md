<div align="center">

# 🚀 InsightPilot

### AI-Powered Business Intelligence Platform

Transform raw datasets into actionable business insights using AI.

Upload → Clean → Analyze → Visualize → Ask AI → Generate Reports

---

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-red)
![Plotly](https://img.shields.io/badge/Plotly-Visualization-blueviolet)
![Pandas](https://img.shields.io/badge/Pandas-Data%20Analysis-black)
![License](https://img.shields.io/badge/License-MIT-success)

</div>

---

# 📖 Overview

InsightPilot is an AI-powered Business Intelligence platform that enables users to upload structured datasets and instantly generate business insights through automated data preparation, KPI analysis, interactive visualizations, AI-powered conversations, and professional reports.

Instead of requiring users to write SQL queries or manually create dashboards, InsightPilot provides an end-to-end analytics workflow with an integrated AI Copilot capable of answering natural-language questions about uploaded datasets.

The platform combines traditional data analytics with modern Large Language Models (OpenAI/Ollama) to make business intelligence accessible to both technical and non-technical users.

---

# ✨ Features

## 📂 Data Management

- Upload CSV, Excel, and SQL datasets
- Automatic dataset validation
- Dataset catalog
- Data preview
- Metadata extraction

---

## 🧹 Data Preparation

- Missing value detection
- Duplicate removal
- Data type correction
- Cleaning quality score
- Automatic preprocessing pipeline

---

## 📊 Analytics

Generate descriptive statistics automatically.

Includes:

- Count
- Mean
- Median
- Standard Deviation
- Min / Max
- Distribution Analysis
- Correlation Analysis
- Outlier Detection
- KPI Generation

---

## 📈 Visualization

Automatically generates interactive dashboards using Plotly.

Supports:

- Bar Charts
- Line Charts
- Scatter Plots
- Histograms
- Pie Charts
- Heatmaps
- Box Plots
- Correlation Matrix

---

## 🤖 AI Copilot

Ask questions in natural language.

Examples:

> Which department has the highest average salary?

> What anomalies exist in this dataset?

> Summarize the sales performance.

> Explain this visualization.

The AI understands:

- Dataset
- KPIs
- Charts
- Reports
- Workflow outputs

---

## 📑 Reports

Generate professional business reports including:

- Executive Summary
- Dataset Overview
- KPI Summary
- Visualizations
- Business Insights

---

## 🔄 Workflow Engine

Plan and execute complete analytics workflows.

Workflow stages include:

```
Upload
    ↓
Cleaning
    ↓
Analysis
    ↓
Visualization
    ↓
Report Generation
```

---

# 🏗 Architecture

```
                    +--------------------+
                    |    Streamlit UI    |
                    +--------------------+
                              |
                              |
                    REST API Requests
                              |
                              ▼
                    +--------------------+
                    |   FastAPI Backend  |
                    +--------------------+
                              |
        --------------------------------------------------
        |        |          |         |         |         |
        ▼        ▼          ▼         ▼         ▼         ▼
   Upload   Cleaning   Analysis   Charts   Reports   AI Copilot
        |        |          |         |         |         |
        -------------------------------
                      |
                      ▼
              Business Logic Layer
                      |
          --------------------------
          |                        |
          ▼                        ▼
     Pandas Engine          Plotly Engine
          |
          ▼
      AI Provider
(OpenAI / Ollama)

```

---

# 🖥 Application Modules

```
🏠 Dashboard

📂 Data
    ├── Upload
    ├── Datasets
    └── SQL

🧹 Prepare

📊 Analyze

📈 Visualize

🤖 AI Copilot

📑 Reports

⚙️ Workflows

🔧 Settings
```

---

# 🛠 Technology Stack

### Backend

- FastAPI
- Pydantic
- Uvicorn

### Frontend

- Streamlit

### Data Processing

- Pandas
- NumPy

### Visualization

- Plotly

### AI

- OpenAI
- Ollama

### Reports

- HTML Reports
- Executive Summary Generator

### Development

- Pytest
- Ruff
- MyPy

---

# 🚀 Getting Started

Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/InsightPilot.git

cd InsightPilot
```

Create virtual environment

```bash
python -m venv .venv
```

Activate environment

Windows

```bash
.venv\Scripts\activate
```

Mac/Linux

```bash
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Start Backend

```bash
uvicorn app.main:app --reload
```

Start Frontend

```bash
streamlit run app/Home.py
```

---

# 📊 Example Workflow

```
Upload Dataset
        │
        ▼
Automatic Cleaning
        │
        ▼
Generate KPIs
        │
        ▼
Generate Visualizations
        │
        ▼
Ask AI Questions
        │
        ▼
Generate Report
```

---

# 📸 Screenshots

## Dashboard

<img src="assets/dashboard.png" width="900"/>

---

## Upload

<img src="assets/upload.png" width="900"/>

---

## Analysis

<img src="assets/analysis.png" width="900"/>

---

## Visualization

<img src="assets/visualization.png" width="900"/>

---

## AI Copilot

<img src="assets/chat.png" width="900"/>

---

## Reports

<img src="assets/report.png" width="900"/>

---

# 📂 Project Structure

```
InsightPilot/

├── app/
├── backend/
├── frontend/
├── services/
├── agents/
├── reports/
├── assets/
├── docs/
├── tests/
├── requirements.txt
└── README.md
```

---

# 🎯 Roadmap

- [x] Dataset Upload
- [x] Automated Cleaning
- [x] KPI Generation
- [x] Interactive Charts
- [x] AI Copilot
- [x] Report Generation
- [x] Workflow Execution
- [ ] Multi-dataset Analysis
- [ ] Dashboard Templates
- [ ] Cloud Deployment
- [ ] Authentication & User Management

---

# 🧪 Testing

The project includes automated testing using:

- Pytest
- Ruff
- MyPy

Run tests

```bash
pytest
```

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository

2. Create a feature branch

3. Commit your changes

4. Open a Pull Request

---

# 📄 License

This project is licensed under the MIT License.

---

# 👨‍💻 Author

**Muhammed Nasimudheen**

M.Tech — Artificial Intelligence

IIT Bombay

GitHub:
https://github.com/mhdnasim6-boop

LinkedIn:
(Add your LinkedIn URL)

---

<div align="center">

⭐ If you found this project useful, please consider giving it a star!

</div>
