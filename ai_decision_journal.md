Decision 1: Enforcing a Fixed 5-Field JSON Schema via system_prompt.txt
Context: Job posts are written in natural language with varying structure and phrasing (J01–J08).

Choice: Constrain Gemini extraction to branches, min_cgpa, max_backlogs, batch, and summary.

Trade-Off: Reduces schema drift and makes downstream Python code predictable, at the cost of ignoring nuanced clauses outside those five fields (which are handled separately in review.csv, skill-gap checks, or human review).

Decision 2: Post-Extraction Fact Verification (check_facts)
Context: LLMs can infer or hallucinate eligibility limits when a job description is vague or incomplete.

Choice: Verify extracted branches (including strict checks for "ALL"), CGPA numbers, backlog limits, and batch years against the raw job post text, clearing unsupported fields and recording reasons.

Trade-Off: Slightly more conservative—ambiguous posts get pushed to needs_review instead of auto-matching—but prevents unsupported criteria from silently determining student eligibility.

Decision 3: No Automatic Percentage-to-CGPA Conversion
Context: Job posts or academic records sometimes mention percentages rather than CGPA values.

Choice: Deliberately avoid converting percentages into CGPA values.

Trade-Off: Avoids false equivalence across institutional grading scales and prevents silent misclassifications, while requiring human review or explicit CGPA criteria when only percentage figures appear.

Decision 4: Caching Extracted Criteria (criteria_cache)
Context: Calling an LLM for every job on every script run adds latency and API cost.

Choice: Cache extracted criteria per job while running check_facts and deterministic eligibility evaluation locally.

Trade-Off: Faster runs and lower API usage on repeated executions, with the responsibility to invalidate or refresh cache entries if jobs.csv or system_prompt.txt changes.

Decision 5: Deterministic Rules for Eligibility, Priority, and Skill Gaps
Context: Shortlisting, ranking, and skill comparison need consistent, repeatable outcomes.

Choice: Implement is_eligible, explain_eligibility, priority_sorter, duplicate resume hashing, and skill_gap_analyzer in deterministic Python logic rather than LLM scoring.

Trade-Off: Less flexible on messy synonyms without normalization helpers, but guarantees reproducibility, explainability, and zero stochastic drift across runs.