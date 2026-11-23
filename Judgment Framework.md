# Judgment Framework — Placement Eligibility Checker

## 1. Purpose
This framework defines how the Placement Eligibility Checker makes conservative, auditable, and accountable decisions when job descriptions or student records are incomplete, ambiguous, or contested.

---

## 2. Wrongful Exclusion vs. Wrongful Inclusion

In campus placement screening, errors fall into two asymmetric categories:

| Dimension | Wrongful Inclusion (False Positive) | Wrongful Exclusion (False Negative) |
| :--- | :--- | :--- |
| **What It Means** | Marking an ineligible student as eligible, or treating an incomplete/ambiguous job post as `matched`. | Marking an eligible student as ineligible, or pushing a clear/valid job post into `needs_review` unnecessarily. |
| **Practical Impact** | Corrupts shortlists, wastes recruiter and student time, and undermines trust in automated screening. | Deprives a deserving student of an opportunity or delays processing of valid job postings. |
| **System Priority** | **Strict prevention first** on eligibility rules and fact verification (`check_facts`). | **Controlled mitigation** via branch normalization, clear failure reasons, and human review visibility (`review.csv`). |

### Design Stance
* **Eligibility & Fact Verification:** Prioritizes avoiding wrongful inclusion. If a job post lacks verifiable criteria (such as missing branch rules, unstated cutoffs, or percentage-only figures with no CGPA), the system routes the job to `needs_review` rather than guessing.
* **Student Evaluation & Explanations:** Once a job is `matched`, deterministic rules (`is_eligible` and `explain_eligibility`) evaluate students consistently and record exact failure reasons so edge cases can be audited.

---

## 3. Human-in-the-Loop Checkpoints

Automation assists with extraction, filtering, and reporting, while humans remain accountable at explicit checkpoints:

1. **Ambiguous or Incomplete Job Postings (`review.csv`):**
   * Any job marked `needs_review` is excluded from automatic eligibility shortlisting until a placement coordinator inspects the original job description and confirms the missing or unclear criteria.
2. **Grading Scale, Branch, or Policy Ambiguities:**
   * Cases involving percentages instead of CGPA, unconventional grading scales, dual/unlisted degree branches, or special exceptions require human judgment rather than silent rule assumptions.
3. **Duplicate Resumes & Contested Outcomes (`Arun_Copy.txt` vs. `Arun.txt` / appeals):**
   * Duplicate resume detections and student eligibility queries should be reviewed by placement staff before final shortlist lock-in.

---

## 4. Cost, Latency, and Reliability Balance

* **Minimize Redundant Model Calls:** Extract structured job fields via `system_prompt.txt` and reuse cached criteria (`criteria_cache`) when job inputs have not changed, lowering API cost and response latency.
* **Keep Decisions Deterministic:** Execute `check_facts`, eligibility checks, priority ranking, duplicate resume hashing, and skill-gap analysis (`skill_gap_report.csv`) in deterministic Python code for fast, repeatable, and explainable results.
* **Escalate Instead of Over-Prompting:** Rather than adding complex multi-step model reasoning to force an answer out of unclear text, route uncertain cases to `needs_review` for clear human sign-off.

---

## 5. Escalation & Sign-Off Rule Before Final Shortlist
No automated output should be treated as final without:
1. Checking `review.csv` and resolving all `needs_review` job postings.
2. Verifying `job_summary.csv`, `eligible.csv`, `priority_report.csv`, and `skill_gap_report.csv` against source data.
3. Obtaining placement coordinator sign-off on any flagged duplicates or exception cases.