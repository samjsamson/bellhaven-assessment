import json
import os
import requests


BASE_URL = "https://analyst-assessment-production.up.railway.app/api/v1/accounts"

TOKEN = os.environ["CRM_TOKEN"]

headers = {
    "Authorization": f"Bearer {TOKEN}"
}

response = requests.get(
    BASE_URL,
    headers=headers,
    params={"q": "bellhaven"}
)

response.raise_for_status()

data = response.json()
accounts = data["data"]

with open("crm_accounts.json", "w") as file:
    json.dump(accounts, file, indent=2)

print("Total CRM accounts:", len(accounts))
print("Saved to crm_accounts.json")