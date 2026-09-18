import os
import requests


BASE_URL = "https://analyst-assessment-production.up.railway.app/api/v1"

TOKEN = os.environ["CRM_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}"
}


def get_account(account_id):
    response = requests.get(
        f"{BASE_URL}/accounts/{account_id}",
        headers=HEADERS
    )

    response.raise_for_status()
    return response.json()


def update_account(account_id, values):
    response = requests.patch(
        f"{BASE_URL}/accounts/{account_id}",
        headers=HEADERS,
        json=values
    )

    response.raise_for_status()
    return response.json()


def create_account(values):
    response = requests.post(
        f"{BASE_URL}/accounts",
        headers=HEADERS,
        json=values
    )

    response.raise_for_status()
    return response.json()