# Bellhaven CRM Reconciliation

A small CRM reconciliation pipeline built for the Clipboard Health Analyst Assessment.

The system:

1. Scrapes current Bellhaven facilities from the website.
2. Fetches relevant CRM accounts through the sandbox API.
3. Matches website facilities to CRM accounts.
4. Generates proposed CRM corrections.
5. Presents proposals in a local Streamlit review app.
6. Writes approved changes back through the CRM API.
7. Can be scheduled to run daily.

## Project Structure

```text
bellhaven-assessment/
├── .github/
│   └── workflows/
│       └── daily.yml
├── scrape.py
├── fetch_crm.py
├── compare.py
├── crm_api.py
├── review_app.py
├── website_facilities.json
├── crm_accounts.json
├── proposals.json
├── decisions.json
├── requirements.txt
└── README.md

Matching Approach

The matching logic combines several signals:

City match
State match
ZIP match
Fuzzy facility-name similarity
Normalized addresses

Names and addresses are normalized before comparison so differences such as:

Road vs Rd
Avenue vs Ave
& vs and

do not automatically create false mismatches.

Each website facility is classified into an action such as:

CREATE
UPDATE_FIELD
REPARENT
CHOW
MARK_DUPLICATE
MARK_NEEDS_REVIEW
CHOW Handling

The pipeline follows the required change-of-ownership SOP.

If an account has both:

lifetime revenue greater than zero
outstanding AR greater than zero

the existing account is preserved.

Instead of changing its parent:

A new facility account is created under the correct parent.
The old account remains unchanged.
chow_current_account on the old account is set to the new account ID.

The CHOW workflow is also retry-safe. If the old account already has a chow_current_account, another new account is not created.

Duplicate Handling

Likely duplicates are identified using facility name, city, state, ZIP, and address information.

For confirmed duplicates:

the losing record is marked Inactive
duplicate_of_account points to the surviving CRM account

Historical CHOW accounts are excluded from duplicate detection because both records are intentionally preserved.

Review App

The review app is built with Streamlit.

Each proposed change displays:

reason for the proposal
current CRM data
website evidence
proposed CRM values
Approve / Reject controls

Nothing writes to the CRM until approved.

The app also supports approving all remaining reviewed proposals in one batch.

Idempotency

The pipeline is designed to be safe on repeated runs.

It avoids re-proposing:

previously approved or rejected proposals
completed CHOW records
resolved duplicates
accounts already marked Needs Review

After completing the assessment corrections, I re-fetched the CRM and reran the reconciliation pipeline.

Final result:

Total CRM accounts: 41
Total proposals: 0

This means the pipeline found no additional unresolved changes on the next run.

Running Locally

Install dependencies:

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

Set the CRM token as an environment variable:

export CRM_TOKEN="YOUR_TOKEN"

Scrape the website:

python3 scrape.py

Fetch CRM data:

python3 fetch_crm.py

Generate proposals:

python3 compare.py

Start the review app:

python3 -m streamlit run review_app.py
Daily Schedule

.github/workflows/daily.yml contains an example GitHub Actions workflow that:

installs dependencies
scrapes the Bellhaven website
fetches CRM accounts
runs the reconciliation logic

The CRM token is expected to be stored as a GitHub Actions secret named:

CRM_TOKEN

No credentials are committed to the repository.

AI Usage

I used ChatGPT as a development partner throughout the exercise.

AI helped with:

understanding the assessment requirements
designing the reconciliation workflow
writing and debugging Python
developing matching logic
identifying edge cases
implementing the Streamlit review UI
interpreting the CHOW SOP
debugging API interactions

I validated the generated logic by inspecting the source data, testing individual API operations, and re-running the reconciliation against the updated CRM.

What I Would Build Next

With more time, I would add:

automated tests for matching and CHOW behavior
stronger address normalization
explicit confidence scores in the review UI
structured logging
a persistent database for proposal history
better handling of partial failures in multi-step operations
alerting when daily runs produce unusually large changes
Time Spent

Actual time spent: 2.5 hours