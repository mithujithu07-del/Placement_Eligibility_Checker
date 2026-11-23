
import os
import csv
import json

from dotenv import load_dotenv
from google import genai


# STEP 1: Load API key
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("API key not found. Check your .env file.")
    raise SystemExit(1)


# STEP 2: Initialize Gemini client
client = genai.Client(api_key=api_key,)


# STEP 3: Read system prompt
try:
    with open("system_prompt.txt", "r", encoding="utf-8") as file:
        system_prompt = file.read()

except FileNotFoundError:
    print("Error: system_prompt.txt not found.")
    raise SystemExit(1)


# STEP 4: Read only the first job post
try:
    with open("jobs.csv", "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        first_job = next(reader, None)

except FileNotFoundError:
    print("Error: jobs.csv not found.")
    raise SystemExit(1)


if first_job is None:
    print("Error: No job posts found.")
    raise SystemExit(1)


job_post = first_job["post"]


# STEP 5: Send job post to Gemini
print("Sending first job post to Gemini...", flush=True)

try:
    response = client.interactions.create(
        model="gemini-3.8-flash",
        input=(
            system_prompt
            + "\n\nExtract eligibility criteria from this job post:\n"
            + job_post
        )
    )

    # STEP 6: Read Gemini response
    response_text = response.output_text

    if not response_text:
        raise ValueError("Gemini returned an empty response.")

    # STEP 7: Convert response into JSON
    criteria = json.loads(response_text)

    # STEP 8: Check required fields
    required_fields = {
        "branches",
        "min_cgpa",
        "max_backlogs",
        "batch",
        "summary"
    }

    if not isinstance(criteria, dict):
        raise ValueError("Response must be a JSON object.")

    if set(criteria.keys()) != required_fields:
        raise ValueError("Response does not contain exactly five required fields.")

    if not isinstance(criteria["branches"], list):
        raise ValueError("Branches must be a list.")

    # STEP 9: Display result
    print("\nGEMINI RESPONSE")
    print("----------------")

    print(json.dumps(criteria, indent=4))

    print("\nCheckpoint 2 API test completed.")

except json.JSONDecodeError:
    print("Error: Gemini did not return valid JSON.")
    
except Exception as error:
    print("\nGemini API error:")
    print(type(error).__name__, error)
