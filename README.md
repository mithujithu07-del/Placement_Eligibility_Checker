# Placement Eligibility Checker

An automated, auditable campus placement screening pipeline that extracts structured eligibility criteria from job descriptions using Gemini (`system_prompt.txt`) and evaluates student records using deterministic Python verification rules.

## Features
- **Structured Criteria Extraction:** Parses job descriptions (`jobs.csv`) into a 5-field JSON schema (`branches`, `min_cgpa`, `max_backlogs`, `batch`, `summary`) with local caching.
- **Factual Verification (`check_facts`):** Validates extracted branch, CGPA, backlog, and batch rules against source job posts before matching; routes ambiguous postings to `needs_review`.
- **Deterministic Eligibility & Explanations:** Evaluates students (`students.csv`) and records clear reasons for exclusions.
- **Additional Reports:** Generates priority rankings (`priority_report.csv`), skill-gap analysis (`skill_gap_report.csv`), and duplicate resume detection.

## Project Structure
- `main.py` — End-to-end pipeline execution
- `system_prompt.txt` — Extraction prompt constraints
- `requirements.txt` — Python dependencies (`google-genai`, `python-dotenv`)
- `jobs.csv`, `students.csv`, `company_skills.csv` — Input datasets
- `resumes/` — Student resume files
- `reflection.md`, `ai_decision_journal.md`, `judgment_framework.md`, `test_red_team_report.md` — Checkpoint 7 documentation

## Setup & Usage
1. Install dependencies:
   ```bash
   pip install -r requirements.txt