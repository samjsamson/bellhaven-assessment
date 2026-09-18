import json
import re
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://analyst-assessment-production.up.railway.app"

facilities = []
seen_links = set()

page = 1


while True:
    response = requests.get(
        f"{BASE_URL}/communities?page={page}"
    )
    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    cards = soup.select(".card")

    if not cards:
        break

    new_facilities = 0

    for card in cards:
        link = card.find("h3").find("a")

        name = link.get_text(strip=True)
        href = link["href"]

        if href in seen_links:
            continue

        seen_links.add(href)
        new_facilities += 1

        # Open facility detail page
        detail_response = requests.get(
            BASE_URL + href
        )
        detail_response.raise_for_status()

        detail_soup = BeautifulSoup(
            detail_response.text,
            "html.parser"
        )

        details = {}

        for dt in detail_soup.find_all("dt"):
            dd = dt.find_next_sibling("dd")

            if dd:
                key = dt.get_text(strip=True)
                value_parts = list(
                    dd.stripped_strings
                )

                details[key] = value_parts

        # Example:
        # ["210 Orchard Lane", "Maplewood, OH 44280"]
        address_parts = details.get(
            "Address",
            []
        )

        street = (
            address_parts[0]
            if len(address_parts) > 0
            else ""
        )

        location = (
            address_parts[1]
            if len(address_parts) > 1
            else ""
        )

        city = ""
        state = ""
        zip_code = ""

        match = re.match(
            r"(.+),\s*([A-Z]{2})\s+(\d{5})",
            location
        )

        if match:
            city = match.group(1)
            state = match.group(2)
            zip_code = match.group(3)

        care_parts = details.get(
            "Care Offerings",
            []
        )

        care_offerings = ", ".join(
            care_parts
        )

        facility = {
            "name": name,
            "address": street,
            "city": city,
            "state": state,
            "zip": zip_code,
            "care_offerings": care_offerings
        }

        facilities.append(facility)

    if new_facilities == 0:
        break

    page += 1


with open(
    "website_facilities.json",
    "w"
) as file:
    json.dump(
        facilities,
        file,
        indent=2
    )


for facility in facilities:
    print(facility)


print(
    "\nTotal facilities:",
    len(facilities)
)

print(
    "Saved to website_facilities.json"
)