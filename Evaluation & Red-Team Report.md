# Evaluation & Red-Team Report — Placement Eligibility Checker

## 1. Overview & Testing Scope
This report documents functional verification and red-team (adversarial / edge-case) analysis for the Placement Eligibility Checker pipeline, covering structured job extraction (`system_prompt.txt`), deterministic fact checking (`check_facts`), eligibility evaluation (`is_eligible`, `explain_eligibility`), report generation (`job_summary.csv`, `eligible.csv`, `review.csv`, `eligibility_explanations.csv`, `summary.txt`), priority ranking (`priority_report.csv`), skill-gap analysis (`skill_gap_report.csv`), and duplicate resume detection.

---

## 2. Standard Functional Evaluation (`J01`–`J08` & Student Cohort)

### Test Dataset & Inputs
* **Jobs:** `J01` through `J08` (`Zentrix Software`, `Bluepeak Systems`, `Kovai Motors`, `Medilink Health`, `Aster Electronics`, `Northstar Analytics`, `GreenGrid Infrastructure`, `Orbit Services`) in `jobs.csv`.
* **Students:** 24 student records in `students.csv` (all validated cleanly).
* **Supporting Inputs:** `company_skills.csv` and 3 resume files under `resumes/`.

### Verified Live Run Outputs
* **Status:** **Verified — All outputs accurate (`PROJECT EXECUTION COMPLETED`).**
* **Criteria Extraction & Caching:** All 8 jobs (`J01`–`J08`) loaded from saved criteria cache (`Using saved criteria for J01`–`J08`) and verified as `matched`.
* **Generated Reports:** `job_summary.csv`, `eligible.csv`, `review.csv`, `eligibility_explanations.csv`, `summary.txt`, `priority_report.csv`, and `skill_gap_report.csv` generated cleanly.
* **Duplicate Resume Detection:** Scanned 3 resumes and detected 1 duplicate (`Arun_Copy.txt matches Arun.txt`).

---

## 3. Red-Team / Adversarial Edge-Case Analysis

| Case ID | Adversarial / Edge Scenario | Expected System Behavior | Verified Design & Mitigation |
| :--- | :--- | :--- | :--- |
| **RT-01** | **Percentage Instead of CGPA** (e.g., job post specifies `"75% required"` without an explicit CGPA cutoff) | Do **not** silently convert `75%` into `7.5` CGPA; keep CGPA unverified or route to `needs_review`. | Explicit CGPA verification avoids silent percentage-to-CGPA conversion and prevents false scale equivalence. |
| **RT-02** | **Ambiguous "All Branches" Wording** (e.g., `"Open to all"` without explicit `"any branch"` or `"all branches"` phrasing) | Do **not** assume `"ALL"` branches without explicit wording; clear unverified branch claims and log a review reason. | `check_facts` checks explicit branch / all-branch wording and records review reasons when ambiguous. |
| **RT-03** | **Unstated or Conflicting Backlog / Batch Values** (e.g., backlog limit or graduation batch not supported by the post) | Clear/null unverified fields (`max_backlogs`, `batch`), append a reason, and mark the job `needs_review`. | Factual verification cross-checks extracted limits and batch years against the source text before matching. |
| **RT-04** | **Branch Aliases & Skill Delimiter/Case Noise** (e.g., `AI&DS` vs. `AIDS`, mixed casing, semicolon/comma-separated skills) | Normalize branch aliases and skill lists cleanly without crashing or miscalculating percentages. | Branch normalization and skill-gap logic handle formatting differences consistently. |
| **RT-05** | **Duplicate Resume Variants** (copied/renamed resume files in `resumes/`) | Detect duplicate resume content and surface it clearly for review. | Normalized content hashing detects duplicate resumes (`Arun_Copy.txt` / `Arun.txt`). |

---

## 4. Limitations & Submission Readiness
* Rule and regex checks depend on clear phrasing in job descriptions; unusually worded exceptions or multi-clause conditions should be checked manually in `review.csv`.
* Cached criteria should be refreshed if `jobs.csv` or `system_prompt.txt` changes.
* `.env` and API keys remain excluded via `.gitignore`, and all Checkpoint 7 documents (`reflection.md`, `ai_decision_journal.md`, `judgment_framework.md`, `test_red_team_report.md`) plus `README.md` are stored in the project repository.