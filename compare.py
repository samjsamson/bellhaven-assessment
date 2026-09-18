import json
import re
import hashlib
import os
from difflib import SequenceMatcher
from collections import defaultdict
from datetime import datetime, timezone


BELLHAVEN_PARENT_NAME = "Bellhaven Senior Living (Parent Account)"

PROPOSALS_FILE = "proposals.json"
DECISIONS_FILE = "decisions.json"


# -------------------------
# Load data
# -------------------------

with open("website_facilities.json") as f:
    website = json.load(f)

with open("crm_accounts.json") as f:
    crm = json.load(f)

if os.path.exists(DECISIONS_FILE):
    with open(DECISIONS_FILE) as f:
        decisions = json.load(f)
else:
    decisions = {}


parent = next(
    account for account in crm
    if account["name"] == BELLHAVEN_PARENT_NAME
)

BELLHAVEN_PARENT_ID = parent["account_id"]


crm_facilities = [
    account for account in crm
    if "(Parent Account)" not in account["name"]
]


# Current accounts eligible to match the website.
# Historical CHOW accounts and resolved duplicate losers are excluded.
match_candidates = [
    account for account in crm_facilities
    if not account.get("chow_current_account")
    and not account.get("duplicate_of_account")
    and account.get("status") != "Inactive"
]


# -------------------------
# Normalization
# -------------------------

def normalize(value):
    if not value:
        return ""

    value = value.lower()
    value = value.replace("&", "and")
    value = re.sub(r"[^a-z0-9 ]", " ", value)

    return " ".join(value.split())


def normalize_address(value):
    value = normalize(value)

    replacements = {
        "street": "st",
        "road": "rd",
        "avenue": "ave",
        "boulevard": "blvd",
        "drive": "dr",
        "lane": "ln",
        "west": "w",
        "east": "e",
        "north": "n",
        "south": "s",
        "northwest": "nw",
        "northeast": "ne",
        "southwest": "sw",
        "southeast": "se",
    }

    words = value.split()
    words = [
        replacements.get(word, word)
        for word in words
    ]

    return " ".join(words)


def website_care_to_crm(value):
    mapping = {
        "Assisted Living": "Assisted Living",
        "Memory Support": "Memory Care",
        "Short-Term Rehabilitation & Nursing": "Skilled Nursing",
    }

    return mapping.get(value)


# -------------------------
# Matching
# -------------------------

def match_score(web, crm_account):
    score = 0

    if normalize(web["city"]) == normalize(
        crm_account["billing_city"]
    ):
        score += 35

    if web["state"] == crm_account["billing_state"]:
        score += 20

    if web["zip"] == crm_account["billing_zip"]:
        score += 20

    name_similarity = SequenceMatcher(
        None,
        normalize(web["name"]),
        normalize(crm_account["name"])
    ).ratio()

    score += name_similarity * 25

    return score


def proposal_id(action, key):
    raw = f"{action}|{key}"
    return hashlib.sha256(
        raw.encode()
    ).hexdigest()[:12]


proposals = []
matched_ids = set()
matches = {}


def add_proposal(proposal):
    pid = proposal["proposal_id"]

    # Already reviewed in a previous run
    if decisions.get(pid) in {
        "approved",
        "rejected"
    }:
        return

    proposals.append(proposal)


# -------------------------
# Match website -> CRM
# -------------------------

for web in website:

    ranked = sorted(
        match_candidates,
        key=lambda account: match_score(
            web,
            account
        ),
        reverse=True
    )

    if not ranked:
        best = None
        score = 0
    else:
        best = ranked[0]
        score = match_score(web, best)

    # -------------------------
    # No confident match
    # -------------------------

    if not best or score < 70:

        care_type = website_care_to_crm(
            web["care_offerings"]
        )

        pid = proposal_id(
            "CREATE",
            f'{web["name"]}|{web["city"]}|{web["zip"]}'
        )

        add_proposal({
            "proposal_id": pid,
            "action": "CREATE",
            "facility": web["name"],
            "reason": (
                "Facility appears on Bellhaven website "
                "but no confident current CRM account was found."
            ),
            "website_evidence": web,
            "proposed_values": {
                "name": web["name"],
                "parent_id": BELLHAVEN_PARENT_ID,
                "billing_street": web["address"],
                "billing_city": web["city"],
                "billing_state": web["state"],
                "billing_zip": web["zip"],
                "care_type": care_type,
                "status": "Active"
            }
        })

        continue

    matched_ids.add(best["account_id"])
    matches[best["account_id"]] = web


    # -------------------------
    # Parent correction / CHOW
    # -------------------------

    if best["parent_id"] != BELLHAVEN_PARENT_ID:

        revenue = (
            best.get("lifetime_revenue", 0)
            or 0
        )

        ar = (
            best.get("outstanding_ar", 0)
            or 0
        )

        if revenue > 0 and ar > 0:

            pid = proposal_id(
                "CHOW",
                best["account_id"]
            )

            add_proposal({
                "proposal_id": pid,
                "action": "CHOW",
                "facility": web["name"],
                "crm_account_id": best["account_id"],
                "reason": (
                    "Wrong parent, but account has revenue "
                    "history and outstanding AR. SOP requires "
                    "preserving the old account and creating "
                    "a new current account."
                ),
                "current_values": {
                    "parent_id": best["parent_id"],
                    "parent_name": best["parent_name"],
                    "lifetime_revenue": revenue,
                    "outstanding_ar": ar
                },
                "proposed_values": {
                    "create_new_account": {
                        "name": web["name"],
                        "parent_id": BELLHAVEN_PARENT_ID,
                        "billing_street": web["address"],
                        "billing_city": web["city"],
                        "billing_state": web["state"],
                        "billing_zip": web["zip"],
                        "care_type": website_care_to_crm(
                            web["care_offerings"]
                        ),
                        "status": "Active"
                    },
                    "old_account_update": {
                        "chow_current_account": "<NEW_ACCOUNT_ID>"
                    }
                }
            })

        else:

            pid = proposal_id(
                "REPARENT",
                best["account_id"]
            )

            add_proposal({
                "proposal_id": pid,
                "action": "REPARENT",
                "facility": web["name"],
                "crm_account_id": best["account_id"],
                "reason": (
                    "Facility belongs to Bellhaven according "
                    "to the current website and does not meet "
                    "the CHOW preservation rule."
                ),
                "current_values": {
                    "parent_id": best["parent_id"],
                    "parent_name": best["parent_name"]
                },
                "proposed_values": {
                    "parent_id": BELLHAVEN_PARENT_ID
                }
            })


    # -------------------------
    # ZIP mismatch
    # -------------------------

    if web["zip"] != best["billing_zip"]:

        pid = proposal_id(
            "UPDATE_ZIP",
            best["account_id"]
        )

        add_proposal({
            "proposal_id": pid,
            "action": "UPDATE_FIELD",
            "facility": web["name"],
            "crm_account_id": best["account_id"],
            "reason": (
                "CRM ZIP differs from current "
                "Bellhaven website."
            ),
            "field": "billing_zip",
            "current_value": best["billing_zip"],
            "proposed_value": web["zip"]
        })


    # -------------------------
    # Address mismatch
    # -------------------------

    if normalize_address(
        web["address"]
    ) != normalize_address(
        best["billing_street"]
    ):

        pid = proposal_id(
            "UPDATE_ADDRESS",
            best["account_id"]
        )

        add_proposal({
            "proposal_id": pid,
            "action": "UPDATE_FIELD",
            "facility": web["name"],
            "crm_account_id": best["account_id"],
            "reason": (
                "CRM street address differs "
                "from Bellhaven website."
            ),
            "field": "billing_street",
            "current_value": best["billing_street"],
            "proposed_value": web["address"]
        })


    # -------------------------
    # Name mismatch
    # -------------------------

    if normalize(web["name"]) != normalize(
        best["name"]
    ):

        pid = proposal_id(
            "UPDATE_NAME",
            best["account_id"]
        )

        add_proposal({
            "proposal_id": pid,
            "action": "UPDATE_FIELD",
            "facility": web["name"],
            "crm_account_id": best["account_id"],
            "reason": (
                "CRM facility name differs "
                "from current Bellhaven website."
            ),
            "field": "name",
            "current_value": best["name"],
            "proposed_value": web["name"]
        })


    # -------------------------
    # Care type mismatch
    # -------------------------

    expected_care = website_care_to_crm(
        web["care_offerings"]
    )

    if (
        expected_care
        and expected_care != best["care_type"]
    ):

        pid = proposal_id(
            "UPDATE_CARE",
            best["account_id"]
        )

        add_proposal({
            "proposal_id": pid,
            "action": "UPDATE_FIELD",
            "facility": web["name"],
            "crm_account_id": best["account_id"],
            "reason": (
                "CRM care type differs "
                "from Bellhaven website."
            ),
            "field": "care_type",
            "current_value": best["care_type"],
            "proposed_value": expected_care
        })


# -------------------------
# Duplicate detection
# -------------------------

groups = defaultdict(list)

for account in crm_facilities:

    # Historical CHOW accounts are intentional,
    # not duplicates.
    if account.get("chow_current_account"):
        continue

    # Already resolved duplicate.
    if account.get("duplicate_of_account"):
        continue

    key = (
        normalize(account["name"]),
        normalize(account["billing_city"]),
        account["billing_state"],
        account["billing_zip"]
    )

    groups[key].append(account)


duplicate_loser_ids = set()


for group in groups.values():

    if len(group) < 2:
        continue

    web = None

    for account in group:
        if account["account_id"] in matches:
            web = matches[
                account["account_id"]
            ]
            break

    def survivor_score(account):

        address_score = 0

        if web:
            address_score = SequenceMatcher(
                None,
                normalize_address(
                    web["address"]
                ),
                normalize_address(
                    account["billing_street"]
                )
            ).ratio()

        return (
            account.get("outstanding_ar", 0) or 0,
            account.get("lifetime_revenue", 0) or 0,
            address_score
        )

    survivor = max(
        group,
        key=survivor_score
    )

    for duplicate in group:

        if (
            duplicate["account_id"]
            == survivor["account_id"]
        ):
            continue

        duplicate_loser_ids.add(
            duplicate["account_id"]
        )

        pid = proposal_id(
            "MARK_DUPLICATE",
            duplicate["account_id"]
        )

        add_proposal({
            "proposal_id": pid,
            "action": "MARK_DUPLICATE",
            "facility": duplicate["name"],
            "crm_account_id": duplicate["account_id"],
            "reason": (
                "Multiple active CRM accounts appear "
                "to represent the same facility."
            ),
            "surviving_account_id": (
                survivor["account_id"]
            ),
            "proposed_values": {
                "duplicate_of_account": (
                    survivor["account_id"]
                ),
                "status": "Inactive"
            }
        })


# -------------------------
# CRM-only Bellhaven accounts
# -------------------------

for account in crm_facilities:

    if account["account_id"] in matched_ids:
        continue

    if account["account_id"] in duplicate_loser_ids:
        continue

    if account.get("chow_current_account"):
        continue

    if account.get("duplicate_of_account"):
        continue

    if account["parent_id"] != BELLHAVEN_PARENT_ID:
        continue

    # Already handled
    if account.get("status") == "Needs Review":
        continue

    pid = proposal_id(
        "NEEDS_REVIEW",
        account["account_id"]
    )

    add_proposal({
        "proposal_id": pid,
        "action": "MARK_NEEDS_REVIEW",
        "facility": account["name"],
        "crm_account_id": account["account_id"],
        "reason": (
            "CRM account is under Bellhaven but no "
            "corresponding facility appears on the "
            "current Bellhaven website."
        ),
        "proposed_values": {
            "status": "Needs Review",
            "note": (
                "Not found on current Bellhaven website. "
                "Ownership or operating status should be reviewed."
            )
        }
    })


# -------------------------
# Save
# -------------------------

output = {
    "generated_at": datetime.now(
        timezone.utc
    ).isoformat(),
    "proposal_count": len(proposals),
    "proposals": proposals
}

with open(PROPOSALS_FILE, "w") as f:
    json.dump(
        output,
        f,
        indent=2
    )


# -------------------------
# Summary
# -------------------------

counts = defaultdict(int)

for proposal in proposals:
    counts[proposal["action"]] += 1


print("\nGenerated proposals.json")
print("Total proposals:", len(proposals))

for action, count in sorted(
    counts.items()
):
    print(f"{action}: {count}")