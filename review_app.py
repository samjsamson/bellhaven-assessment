import json
import os
import streamlit as st

from crm_api import create_account, update_account, get_account


PROPOSALS_FILE = "proposals.json"
DECISIONS_FILE = "decisions.json"


def load_json(path, default):
    if not os.path.exists(path):
        return default

    with open(path) as f:
        return json.load(f)


def save_decisions(decisions):
    with open(DECISIONS_FILE, "w") as f:
        json.dump(decisions, f, indent=2)


def apply_proposal(proposal):
    action = proposal["action"]

    # -------------------------
    # Update one field
    # -------------------------
    if action == "UPDATE_FIELD":
        return update_account(
            proposal["crm_account_id"],
            {
                proposal["field"]: proposal["proposed_value"]
            }
        )

    # -------------------------
    # Change parent
    # -------------------------
    if action == "REPARENT":
        return update_account(
            proposal["crm_account_id"],
            proposal["proposed_values"]
        )

    # -------------------------
    # Mark duplicate
    # -------------------------
    if action == "MARK_DUPLICATE":
        return update_account(
            proposal["crm_account_id"],
            proposal["proposed_values"]
        )

    # -------------------------
    # Mark needs review
    # -------------------------
    if action == "MARK_NEEDS_REVIEW":
        return update_account(
            proposal["crm_account_id"],
            proposal["proposed_values"]
        )

    # -------------------------
    # Create missing facility
    # -------------------------
    if action == "CREATE":
        return create_account(
            proposal["proposed_values"]
        )

    # -------------------------
    # Change of ownership
    # -------------------------
    if action == "CHOW":
        old_account = get_account(
            proposal["crm_account_id"]
        )

        # Prevent duplicate CHOW creation
        if old_account.get("chow_current_account"):
            return {
                "message": "CHOW already applied",
                "new_account_id": old_account["chow_current_account"]
            }

        # Create new current account under Bellhaven
        new_account = create_account(
            proposal["proposed_values"]["create_new_account"]
        )

        new_id = new_account["account_id"]

        # Preserve old account and link it to new account
        old_update = update_account(
            proposal["crm_account_id"],
            {
                "chow_current_account": new_id
            }
        )

        return {
            "message": "CHOW completed",
            "new_account": new_account,
            "old_account_update": old_update
        }

    raise ValueError(f"Unknown action: {action}")


# -------------------------
# Load proposals / decisions
# -------------------------

data = load_json(
    PROPOSALS_FILE,
    {"proposals": []}
)

proposals = data["proposals"]

decisions = load_json(
    DECISIONS_FILE,
    {}
)


# -------------------------
# Page setup
# -------------------------

st.set_page_config(
    page_title="Bellhaven CRM Review",
    layout="wide"
)

st.title("Bellhaven CRM Review")


# Only count decisions belonging to the current proposal set
current_ids = {
    proposal["proposal_id"]
    for proposal in proposals
}

approved = sum(
    1
    for pid in current_ids
    if decisions.get(pid) == "approved"
)

rejected = sum(
    1
    for pid in current_ids
    if decisions.get(pid) == "rejected"
)

pending = len(proposals) - approved - rejected


# -------------------------
# Metrics
# -------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total", len(proposals))
col2.metric("Pending", pending)
col3.metric("Approved", approved)
col4.metric("Rejected", rejected)


# -------------------------
# Approve all
# -------------------------

st.divider()

confirm_all = st.checkbox(
    "I reviewed the remaining proposals and approve all pending changes."
)

if st.button(
    "Approve All Pending",
    type="primary",
    disabled=not confirm_all
):
    successes = []
    failures = []

    for proposal in proposals:
        pid = proposal["proposal_id"]

        # Skip anything already decided
        if decisions.get(pid) in {
            "approved",
            "rejected"
        }:
            continue

        try:
            result = apply_proposal(proposal)

            decisions[pid] = "approved"

            # Save immediately after every successful API call
            save_decisions(decisions)

            successes.append({
                "facility": proposal["facility"],
                "action": proposal["action"]
            })

        except Exception as e:
            failures.append({
                "facility": proposal["facility"],
                "action": proposal["action"],
                "error": str(e)
            })

    if successes:
        st.success(
            f"Successfully approved {len(successes)} proposals."
        )

        st.json(successes)

    if failures:
        st.error(
            f"{len(failures)} proposals failed."
        )

        st.json(failures)


st.divider()


# -------------------------
# Individual proposals
# -------------------------

for proposal in proposals:

    pid = proposal["proposal_id"]
    decision = decisions.get(pid)

    if decision == "approved":
        status = "✅ Approved"
    elif decision == "rejected":
        status = "❌ Rejected"
    else:
        status = "⏳ Pending"

    with st.expander(
        f'{proposal["action"]} | '
        f'{proposal["facility"]} | '
        f'{status}',
        expanded=(decision is None)
    ):

        st.write("### Reason")
        st.write(proposal["reason"])

        if "crm_account_id" in proposal:
            st.write("### CRM Account ID")
            st.code(proposal["crm_account_id"])

        if "current_values" in proposal:
            st.write("### Current CRM")
            st.json(proposal["current_values"])

        if "current_value" in proposal:
            st.write("### Current CRM")
            st.code(str(proposal["current_value"]))

        if "website_evidence" in proposal:
            st.write("### Website Evidence")
            st.json(proposal["website_evidence"])

        if "proposed_values" in proposal:
            st.write("### Proposed Change")
            st.json(proposal["proposed_values"])

        if "proposed_value" in proposal:
            st.write("### Proposed Change")
            st.code(str(proposal["proposed_value"]))

        approve_col, reject_col, reset_col = st.columns(3)

        # -------------------------
        # Individual approve
        # -------------------------

        if approve_col.button(
            "Approve",
            key=f"approve_{pid}",
            disabled=(decision == "approved")
        ):
            try:
                result = apply_proposal(proposal)

                decisions[pid] = "approved"
                save_decisions(decisions)

                st.success("CRM API call succeeded")

                st.write("### API Response")
                st.json(result)

            except Exception as e:
                st.error(
                    f"CRM update failed: {e}"
                )

        # -------------------------
        # Reject
        # -------------------------

        if reject_col.button(
            "Reject",
            key=f"reject_{pid}"
        ):
            decisions[pid] = "rejected"
            save_decisions(decisions)

            st.success("Proposal rejected.")

        # -------------------------
        # Reset
        # -------------------------

        if reset_col.button(
            "Reset",
            key=f"reset_{pid}"
        ):
            decisions.pop(pid, None)
            save_decisions(decisions)

            st.success("Decision reset.")