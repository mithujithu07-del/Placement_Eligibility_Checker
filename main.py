import csv
import hashlib
import json
import os
import re
import time

from dotenv import load_dotenv
from google import genai


# ----------------------------
# FILE LOADING
# ----------------------------

def load_jobs(filename):
    with open(filename, "r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def load_students(filename):
    students = []

    with open(filename, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            row["roll"] = (row.get("roll") or "").strip()
            row["name"] = (row.get("name") or "").strip()
            row["branch"] = (row.get("branch") or "").strip().upper()
            row["cgpa"] = float(row["cgpa"])
            row["backlogs"] = int(row["backlogs"])
            row["batch"] = int(row["batch"])
            row["skills"] = (row.get("skills") or "").strip()
            students.append(row)

    return students

# ----------------------------
# CRITERIA CACHE
# ----------------------------

def load_criteria_cache(filename="criteria.json"):
    if not os.path.isfile(filename):
        return {}

    try:
        with open(filename, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        print("Cache file could not be read. Starting with an empty cache.")
        return {}


def save_criteria_cache(cache, filename="criteria.json"):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(cache, file, indent=4)


def make_job_cache_key(job):
    # If the post changes, its old cached criteria will not be reused.
    post_hash = hashlib.sha256(job["post"].encode("utf-8")).hexdigest()
    return f'{job["id"]}:{post_hash}'


# ----------------------------
# GEMINI CRITERIA EXTRACTION
# ----------------------------

def is_valid(criteria):
    required_fields = {
        "branches",
        "min_cgpa",
        "max_backlogs",
        "batch",
        "summary"
    }

    if not isinstance(criteria, dict):
        return False

    if set(criteria.keys()) != required_fields:
        return False

    if not isinstance(criteria["branches"], list):
        return False

    if not all(isinstance(branch, str) for branch in criteria["branches"]):
        return False

    if criteria["min_cgpa"] is not None:
        if isinstance(criteria["min_cgpa"], bool):
            return False
        if not isinstance(criteria["min_cgpa"], (int, float)):
            return False
        if not 0 <= criteria["min_cgpa"] <= 10:
            return False

    if criteria["max_backlogs"] is not None:
        if isinstance(criteria["max_backlogs"], bool):
            return False
        if not isinstance(criteria["max_backlogs"], int):
            return False
        if criteria["max_backlogs"] < 0:
            return False
    
    if criteria["batch"] is not None:

        if isinstance(criteria["batch"], int):
            if isinstance(criteria["batch"], bool):
                return False

        elif isinstance(criteria["batch"], list):

            if not criteria["batch"]:
                return False

            if not all(
                isinstance(year, int) and not isinstance(year, bool)
                for year in criteria["batch"]
            ):
                return False

        else:
            return False
    if not isinstance(criteria["summary"], str):
        return False

    if len(criteria["summary"].split()) > 12:
        return False

    return True


def read_criteria(job_post, system_prompt, client):
    for attempt in range(2):
        try:
            print(f"Gemini API attempt {attempt + 1}...")

            response = client.interactions.create(
                model="gemini-3.8-flash",
                input=system_prompt + "\n\nJob post:\n" + job_post
            )

            raw_text = response.output_text.strip()

            # Handle a response wrapped in Markdown JSON fences.
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)

            criteria = json.loads(raw_text)

            if not is_valid(criteria):
              print("Gemini returned invalid criteria.")
              print("Gemini raw response:", raw_text)

              if attempt == 0:
                print("Retrying once...")
                time.sleep(2)
                continue

              return None

            # Copy only the five approved fields.
            return {
                "branches": criteria["branches"],
                "min_cgpa": criteria["min_cgpa"],
                "max_backlogs": criteria["max_backlogs"],
                "batch": criteria["batch"],
                "summary": criteria["summary"]
            }

        except Exception as error:
            print("Criteria extraction error:", error)

            if attempt == 0:
                print("Retrying once after a short pause...")
                time.sleep(2)
            else:
                print("Skipping this job for now.")

    return None


# ----------------------------
# STUDENT DATA VALIDATION
# ----------------------------

def validate_student_data(students):
    errors = []
    valid_branches = {
        "CSE", "IT", "AIDS", "ECE", "EEE", "MECH", "CIVIL"
    }
    seen_rolls = set()

    for student in students:
        roll = student.get("roll", "").strip()

        if not roll or not student.get("name", "").strip():
            errors.append("Missing student roll number or name")

        if not 0 <= student["cgpa"] <= 10:
            errors.append(f"{roll}: Invalid CGPA")

        if student["backlogs"] < 0:
            errors.append(f"{roll}: Invalid backlog count")

        if student.get("branch", "").strip().upper() not in valid_branches:
            errors.append(f"{roll}: Invalid branch")

        if roll in seen_rolls:
            errors.append(f"{roll}: Duplicate roll number")

        seen_rolls.add(roll)

    return errors


# ----------------------------
# FACT CHECKING
# ----------------------------

BRANCH_ALIASES = {
    "CSE": [r"\bCSE\b", r"COMPUTER\s+SCIENCE"],
    "IT": [r"\bIT\b", r"INFORMATION\s+TECHNOLOGY"],
    "AIDS": [r"\bAIDS\b", r"AI\s*&\s*DS", r"ARTIFICIAL\s+INTELLIGENCE\s*&?\s*DATA\s+SCIENCE"],
    "ECE": [r"\bECE\b", r"ELECTRONICS\s+AND\s+COMMUNICATION"],
    "EEE": [r"\bEEE\b", r"ELECTRICAL\s+AND\s+ELECTRONICS"],
    "MECH": [r"\bMECH(?:ANICAL)?\b"],
    "CIVIL": [r"\bCIVIL\b"]
}


def normalize_branch(branch):
    branch = branch.strip().upper()

    aliases = {
        "AI&DS": "AIDS",
        "AI & DS": "AIDS",
        "ARTIFICIAL INTELLIGENCE AND DATA SCIENCE": "AIDS",
        "MECHANICAL": "MECH",
        "MECHANICAL ENGINEERING": "MECH",
        "COMPUTER SCIENCE": "CSE",
        "INFORMATION TECHNOLOGY": "IT",
        "ELECTRONICS AND COMMUNICATION": "ECE",
        "ELECTRICAL AND ELECTRONICS": "EEE"
    }

    return aliases.get(branch, branch)


def branch_is_mentioned(branch, post):
    branch = normalize_branch(branch)

    patterns = BRANCH_ALIASES.get(branch, [])

    return any(
        re.search(pattern, post, flags=re.IGNORECASE)
        for pattern in patterns
    )

def extract_cgpa_numbers(post):
    patterns = [
        r"CGPA\s*(?:OF\s*)?(?:AT\s+LEAST\s*)?(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*(?:OR\s+ABOVE|AND\s+ABOVE|\+)?\s*CGPA",
        r"MINIMUM\s+CGPA\s*(?:OF\s*)?(\d+(?:\.\d+)?)",
        r"CGPA\s*(?:OF\s*)?(\d+(?:\.\d+)?)\s*(?:OR\s+ABOVE|AND\s+ABOVE|\+)?"
    ]

    found = []
    for pattern in patterns:
        found.extend(re.findall(pattern, post, flags=re.IGNORECASE))

    return [float(value) for value in found]


def check_facts(job_post, criteria):
    checked = criteria.copy()
    reasons = []
    post = job_post.upper()

    # Branches: only accept branches explicitly present in the job post.
    if "ALL" in [b.upper() for b in checked["branches"]]:
        if not re.search(r"\bANY\s+BRANCH\b|\bALL\s+BRANCHES\b", post):
            checked["branches"] = []
            reasons.append("The post does not explicitly allow all branches.")
        else:
            checked["branches"] = ["ALL"]
    else:
        verified = []
        for branch in checked["branches"]:
            normalized = normalize_branch(branch)
            if branch_is_mentioned(normalized, post):
                if normalized not in verified:
                    verified.append(normalized)
            else:
                reasons.append(f"Branch not supported by post: {normalized}")
        checked["branches"] = verified

    # CGPA: percentages are deliberately not converted to CGPA.
    if checked["min_cgpa"] is not None:
        cgpa_values = extract_cgpa_numbers(post)
        if not any(abs(value - float(checked["min_cgpa"])) < 0.001
                   for value in cgpa_values):
            checked["min_cgpa"] = None
            reasons.append("CGPA value is not explicitly supported by the post.")

    # Backlogs.
    if checked["max_backlogs"] is not None:
        backlog_supported = False

        if checked["max_backlogs"] == 0:
            backlog_supported = bool(re.search(
                r"\bNO\s+(?:ACTIVE\s+)?BACKLOGS?\b|\bZERO\s+BACKLOGS?\b",
                post
            ))
        else:
            number_words = {
                "ONE": 1, "TWO": 2, "THREE": 3,
                "FOUR": 4, "FIVE": 5
            }

            match = re.search(
                r"\b(?:MAXIMUM|MAX|UP\s+TO|AT\s+MOST|MAXIMUM\s+OF)\s+"
                r"(\d+|ONE|TWO|THREE|FOUR|FIVE)\s+(?:ACTIVE\s+)?BACKLOGS?\b",
                post
            )
            if not match:
                match = re.search(
                    r"\b(\d+|ONE|TWO|THREE|FOUR|FIVE)\s+(?:ACTIVE\s+)?BACKLOGS?\s+"
                    r"(?:ARE\s+|IS\s+)?(?:PERMITTED|ALLOWED)\b",
                    post
                )

            if match:
                value = match.group(1)
                limit = int(value) if value.isdigit() else number_words[value]
                backlog_supported = limit == checked["max_backlogs"]

            if not backlog_supported:
                permitted = re.search(
                    r"\b(\d+|ONE|TWO|THREE)\s+BACKLOGS?\s+(?:ARE\s+)?PERMITTED\b",
                    post
                )
                if permitted:
                    value = permitted.group(1)
                    limit = int(value) if value.isdigit() else number_words[value]
                    backlog_supported = limit == checked["max_backlogs"]

        if not backlog_supported:
            checked["max_backlogs"] = None
            reasons.append("Backlog limit is not explicitly supported by the post.")

    # Batch: supports one or multiple graduating years.
    if checked["batch"] is not None:

        mentioned_batches = [
            int(year)
            for year in re.findall(r"\b20\d{2}\b", post)
        ]

        if isinstance(checked["batch"], int):
            extracted_batches = [checked["batch"]]
        else:
            extracted_batches = checked["batch"]

        if not all(
            year in mentioned_batches
            for year in extracted_batches
        ):
            checked["batch"] = None
            reasons.append(
                "Batch is not fully supported by the job post."
            )

    return checked, reasons

def job_status(criteria):
    if not criteria.get("branches") or criteria.get("min_cgpa") is None:
        return "needs_review"
    return "matched"


# ----------------------------
# ELIGIBILITY AND EXPLANATION
# ----------------------------


def is_eligible(student, criteria):
    student_branch = student["branch"].strip().upper()

    if "ALL" not in criteria["branches"]:
        if student_branch not in criteria["branches"]:
            return False

    if criteria["min_cgpa"] is not None:
        if student["cgpa"] < criteria["min_cgpa"]:
            return False

    if criteria["max_backlogs"] is not None:
        if student["backlogs"] > criteria["max_backlogs"]:
            return False

    if criteria["batch"] is not None:
        if isinstance(criteria["batch"], list):
            if student["batch"] not in criteria["batch"]:
                return False
        else:
            if student["batch"] != criteria["batch"]:
                return False

    return True



def explain_eligibility(student, criteria):
    reasons = []

    # Branch check
    if "ALL" not in criteria["branches"]:
        if student["branch"].strip().upper() not in criteria["branches"]:
            reasons.append("Branch does not match")

    # CGPA check
    if criteria["min_cgpa"] is not None:
        if student["cgpa"] < criteria["min_cgpa"]:
            reasons.append("CGPA is below requirement")

    # Backlog check
    if criteria["max_backlogs"] is not None:
        if student["backlogs"] > criteria["max_backlogs"]:
            reasons.append("Backlogs exceed permitted limit")

    # Batch check
    if criteria["batch"] is not None:
        allowed_batches = criteria["batch"]

        if isinstance(allowed_batches, int):
            allowed_batches = [allowed_batches]

        if student["batch"] not in allowed_batches:
            reasons.append("Batch does not match")

    if reasons:
        return "Not Eligible", reasons

    return "Eligible", ["All stated eligibility criteria satisfied"]

# ----------------------------
# REPORT GENERATION
# ----------------------------

def write_csv(filename, fields, records):
    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def write_reports(processed_jobs, students):
    job_summary = []
    eligible_records = []
    review_records = []
    explanation_records = []
    students_with_jobs = set()

    for job in processed_jobs:
        criteria = job["criteria"]
        eligible_students = []

        if job["status"] == "matched":
            for student in students:
                result, reasons = explain_eligibility(student, criteria)

                explanation_records.append({
                    "job_id": job["id"],
                    "company": job["company"],
                    "roll": student["roll"],
                    "name": student["name"],
                    "status": result,
                    "reason": "; ".join(reasons)
                })

                if result == "Eligible":
                    eligible_students.append(student)
                    students_with_jobs.add(student["roll"])

                    eligible_records.append({
                        "job_id": job["id"],
                        "company": job["company"],
                        "roll": student["roll"],
                        "name": student["name"],
                        "branch": student["branch"],
                        "cgpa": student["cgpa"],
                        "backlogs": student["backlogs"],
                        "batch": student["batch"]
                    })

        job_summary.append({
            "job_id": job["id"],
            "company": job["company"],
            "branches": json.dumps(criteria["branches"]),
            "min_cgpa": criteria["min_cgpa"],
            "max_backlogs": criteria["max_backlogs"],
            "batch": criteria["batch"],
            "status": job["status"],
            "eligible_count": len(eligible_students)
        })

        if job["status"] == "needs_review":
            review_records.append({
                "job_id": job["id"],
                "company": job["company"],
                "post": job["post"],
                "reason": "; ".join(job.get("reasons", []))
            })

    write_csv(
        "job_summary.csv",
        ["job_id", "company", "branches", "min_cgpa",
         "max_backlogs", "batch", "status", "eligible_count"],
        job_summary
    )

    write_csv(
        "eligible.csv",
        ["job_id", "company", "roll", "name", "branch",
         "cgpa", "backlogs", "batch"],
        eligible_records
    )

    write_csv(
        "review.csv",
        ["job_id", "company", "post", "reason"],
        review_records
    )

    write_csv(
        "eligibility_explanations.csv",
        ["job_id", "company", "roll", "name", "status", "reason"],
        explanation_records
    )

    with open("summary.txt", "w", encoding="utf-8") as file:
        file.write("PLACEMENT ELIGIBILITY SUMMARY\n")
        file.write("=============================\n\n")

        for item in job_summary:
            file.write(
                f'{item["company"]}: {item["eligible_count"]} eligible students '
                f'({item["status"]})\n'
            )

        file.write("\nSTUDENTS ELIGIBLE FOR NO MATCHED JOB\n")
        file.write("------------------------------------\n")

        for student in students:
            if student["roll"] not in students_with_jobs:
                file.write(f'{student["roll"]} - {student["name"]}\n')

    print("job_summary.csv created.")
    print("eligible.csv created.")
    print("review.csv created.")
    print("eligibility_explanations.csv created.")
    print("summary.txt created.")


# ----------------------------
# EXTRA FEATURES
# ----------------------------

def load_company_skills(filename="company_skills.csv"):
    company_skills = {}

    if not os.path.isfile(filename):
        print(f"{filename} not found. Skill-gap report will use no required skills.")
        return company_skills

    with open(filename, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            job_id = row.get("job_id", "").strip()
            raw_skills = row.get("required_skills", "")
            company_skills[job_id] = [
                skill.strip().lower()
                for skill in raw_skills.split(";")
                if skill.strip()
            ]

    return company_skills


def priority_sorter(eligible_students):
    return sorted(
        eligible_students,
        key=lambda student: student["cgpa"],
        reverse=True
    )


def skill_gap_analyzer(student, required_skills):
    # Optional "skills" column in students.csv; blank/missing means no skills listed.
    student_skills = [
        skill.strip().lower()
        for skill in student.get("skills", "").split(";")
        if skill.strip()
    ]

    matched = [skill for skill in required_skills if skill in student_skills]
    missing = [skill for skill in required_skills if skill not in student_skills]

    percentage = (
        len(matched) / len(required_skills) * 100
        if required_skills else 0
    )

    return matched, missing, percentage



def detect_duplicate_resumes(folder="resumes"):

    import hashlib

    if not os.path.isdir(folder):
        print("Resume folder not found.")
        return

    seen_files = {}
    total_scanned = 0
    duplicate_count = 0

    print("\nDuplicate Resume Detection Summary")
    print("----------------------------------")

    for filename in os.listdir(folder):

        if not filename.lower().endswith(".txt"):
            continue

        path = os.path.join(folder, filename)

        if not os.path.isfile(path):
            continue

        total_scanned += 1

        with open(path, "r", encoding="utf-8-sig") as file:
            content = file.read()

        # Normalize text before comparing
        normalized = " ".join(content.lower().split())

        file_hash = hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

        if file_hash in seen_files:

            duplicate_count += 1

            print(
                "Duplicate Resume:",
                filename,
                "matches",
                seen_files[file_hash]
            )

        else:
            seen_files[file_hash] = filename

    print("Total resumes scanned:", total_scanned)
    print("Duplicate resumes found:", duplicate_count)

    if duplicate_count == 0:
        print("No duplicate resumes found.")

def generate_extra_reports(processed_jobs, students):
    company_skills = load_company_skills()

    priority_records = []
    skill_records = []

    for job in processed_jobs:
        if job["status"] != "matched":
            continue

        eligible = [
            student for student in students
            if is_eligible(student, job["criteria"])
        ]

        ranked = priority_sorter(eligible)

        for rank, student in enumerate(ranked, start=1):
            priority_records.append({
                "job_id": job["id"],
                "company": job["company"],
                "rank": rank,
                "roll": student["roll"],
                "name": student["name"],
                "cgpa": student["cgpa"]
            })

        required = company_skills.get(job["id"], [])

        for student in eligible:
            matched, missing, percentage = skill_gap_analyzer(
                student, required
            )

            skill_records.append({
                "job_id": job["id"],
                "company": job["company"],
                "roll": student["roll"],
                "name": student["name"],
                "matched_skills": "; ".join(matched),
                "missing_skills": "; ".join(missing),
                "skill_match_percentage": round(percentage, 2)
            })

    write_csv(
        "priority_report.csv",
        ["job_id", "company", "rank", "roll", "name", "cgpa"],
        priority_records
    )

    write_csv(
        "skill_gap_report.csv",
        ["job_id", "company", "roll", "name", "matched_skills",
         "missing_skills", "skill_match_percentage"],
        skill_records
    )

    print("priority_report.csv created.")
    print("skill_gap_report.csv created.")


# ----------------------------
# MAIN PROGRAM
# ----------------------------


def main():
    print("PLACEMENT ELIGIBILITY CHECKER")
    print("----------------------------")

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("API key not found. Check your .env file.")
        return

    try:
        jobs = load_jobs("jobs.csv")
        students = load_students("students.csv")
    except (OSError, KeyError, ValueError) as error:
        print("Input file error:", error)
        return

    print("Total Job Posts:", len(jobs))
    print("Total Students:", len(students))

    # Student validation
    print("\nSTUDENT DATA VALIDATION")
    print("-----------------------")

    errors = validate_student_data(students)

    if errors:
        for error in errors:
            print(error)
        return

    print("All student records are valid.")

    # Load system prompt
    try:
        with open("system_prompt.txt", "r", encoding="utf-8") as file:
            system_prompt = file.read()
    except OSError:
        print("system_prompt.txt not found.")
        return

    client = genai.Client(api_key=api_key)

    # Load saved criteria
    criteria_cache = load_criteria_cache()
    processed_jobs = []

    print("\nGEMINI CRITERIA EXTRACTION")
    print("--------------------------")

    for job in jobs:
        print("\nProcessing:", job["id"], "-", job["company"])
        cache_key = make_job_cache_key(job)

        # STEP 1: Check saved criteria
        if cache_key in criteria_cache and is_valid(criteria_cache[cache_key]):
            print("Using saved criteria for", job["id"])
            criteria = criteria_cache[cache_key]

        # STEP 2: Call Gemini only if criteria is not saved
        else:
            print("Sending job post to Gemini...")
            criteria = read_criteria(
                job["post"],
                system_prompt,
                client
            )

            # STEP 3: Save valid criteria once
            if criteria is not None and is_valid(criteria):
                criteria_cache[cache_key] = criteria
                save_criteria_cache(criteria_cache)
                print("Criteria saved successfully.")

        # STEP 4: Handle invalid criteria
        if criteria is None:

            print("Job Status: needs_review")

            processed_jobs.append({
                "id": job["id"],
                "company": job["company"],
                "post": job["post"],
                "criteria": {
                    "branches": [],
                    "min_cgpa": None,
                    "max_backlogs": None,
                    "batch": None,
                    "summary": ""
                },
                "status": "needs_review",
                "reasons": [
                    "Criteria extraction failed. Manual review required."
                ]
            })

            continue

        # STEP 5: Verify Gemini criteria with original job post
        checked, reasons = check_facts(
            job["post"],
            criteria
        )

        status = job_status(checked)

        if reasons and status == "matched":
            status = "needs_review"

        processed_jobs.append({
            "id": job["id"],
            "company": job["company"],
            "post": job["post"],
            "criteria": checked,
            "status": status,
            "reasons": reasons
        })

        print("Job Status:", status)

    # STEP 6: Generate reports
    print("\nREPORT GENERATION")
    print("-----------------")

    write_reports(processed_jobs, students)

    generate_extra_reports(processed_jobs, students)

    # STEP 7: Resume duplicate detection
    print("\nDUPLICATE RESUME DETECTION")
    print("-------------------------")

    detect_duplicate_resumes()

    print("\nPROJECT EXECUTION COMPLETED.")


if __name__ == "__main__":
    main()
