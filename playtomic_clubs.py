# -*- coding: utf-8 -*-
"""
Playtomic padel clubs in Poland.
Total unique clubs: 23
Data collected from Playtomic API (https://api.playtomic.io/v1/tenants)
Queried from 15 major Polish cities with radius=100km each.
"""


PLAYTOMIC_CLUBS = {
    "padel-team-bytom": {
        "tenant_id": "05a9122e-d8ff-442d-a026-58b98170b4d8",
        "name": "Padelteam Bytom",
        "city": "Bytom",
        "address": "Dzierżonia 19",
        "courts": 9,
        "lat": 50.3576904,
        "lon": 18.846304,
    },
    "interpadel-gdynia": {
        "tenant_id": "91a60f0a-1fef-4efc-9548-3a6b37ae25e0",
        "name": "Interpadel Gdynia",
        "city": "Gdynia",
        "address": "Pucka 5",
        "courts": 10,
        "lat": 54.54516338,
        "lon": 18.46836375,
    },
    "padel-center-academy": {
        "tenant_id": "dd500ac3-5004-41ee-ab6c-c60545ae3ae4",
        "name": "Padel Center & Academy",
        "city": "Katowice",
        "address": "Lwowska 40",
        "courts": 9,
        "lat": 50.2510115,
        "lon": 19.0899297,
    },
    "viva-padel-katowice": {
        "tenant_id": "84b91836-ee5b-42f1-8c44-77cde714d2e9",
        "name": "Viva Padel Katowice",
        "city": "Katowice",
        "address": "Józefa Mackiewicza 1",
        "courts": 9,
        "lat": 50.2700586,
        "lon": 19.0692057,
    },
    "rancho-padel-club-": {
        "tenant_id": "9ac2868b-0085-4e1b-b22e-229866a1ad62",
        "name": "Rancho Padel Club",
        "city": "Mała Nieszawka",
        "address": "Prosta 8",
        "courts": 5,
        "lat": 52.9861163,
        "lon": 18.5169627,
    },
    "pop-yard-padel": {
        "tenant_id": "68323d20-8d88-4653-9a50-148cb9a5b49e",
        "name": "Pop Yard",
        "city": "Opole",
        "address": "Kowalska 2",
        "courts": 3,
        "lat": 50.65608279,
        "lon": 17.93085976,
    },
    "interpadel-poznań": {
        "tenant_id": "34f066f9-4292-4cce-923f-2fa95f1c7b47",
        "name": "Interpadel Poznań",
        "city": "Poznań",
        "address": "Wolczynska 18",
        "courts": 9,
        "lat": 52.3725398,
        "lon": 16.8384,
    },
    "passion-padel": {
        "tenant_id": "98ee88f9-0ad1-4c0e-84ab-f620097ee1d2",
        "name": "Passion Padel",
        "city": "Poznań",
        "address": "28 Czerwca 1956 r. 390/A",
        "courts": 2,
        "lat": 52.36218197,
        "lon": 16.9034489,
    },
    "plek-poznan": {
        "tenant_id": "56e1531e-e108-42af-b877-834a53381efa",
        "name": "Plek Padel Poznań",
        "city": "Poznań",
        "address": "Margonińska 25",
        "courts": 10,
        "lat": 52.4299159,
        "lon": 16.8381971,
    },
    "padel-on-": {
        "tenant_id": "8b616ddb-93a6-4629-a00a-b940a3f66e20",
        "name": "Padel On",
        "city": "Pszczyna",
        "address": "ul Zofii Nałkowskiej 17",
        "courts": 4,
        "lat": 49.9722646,
        "lon": 18.95640747,
    },
    "fabryka-energii": {
        "tenant_id": "4c0b171f-8e62-48a2-8fdc-46fb5b1073e9",
        "name": "Fabryka Energii",
        "city": "Szczecin",
        "address": "Łukasińskiego 112",
        "courts": 0,
        "lat": 53.43871017,
        "lon": 14.48045646,
    },
    "city-padel-torun": {
        "tenant_id": "828ccdaf-99e0-4989-86fb-a313529edc58",
        "name": "City Padel Toruń",
        "city": "Toruń",
        "address": "Równinna 28",
        "courts": 5,
        "lat": 53.0435316,
        "lon": 18.6507168,
    },
    "interpadel-torun": {
        "tenant_id": "08e4db64-8cdd-4ae1-b38e-a8f7a77bfdcc",
        "name": "Interpadel Torun",
        "city": "Toruń",
        "address": "Kociewska 24 - 26",
        "courts": 8,
        "lat": 53.03961682,
        "lon": 18.6391049,
    },
    "padel-team-tychy": {
        "tenant_id": "d5a93847-b621-4852-9fa1-4a310afd3423",
        "name": "Padelteam Tychy",
        "city": "Tychy",
        "address": "Lawendowa 2",
        "courts": 4,
        "lat": 50.12995227,
        "lon": 18.99969738,
    },
    "rqt-spot": {
        "tenant_id": "44340c7a-0951-47bd-8a7e-ccbe0703cdc3",
        "name": "RQT Spot",
        "city": "Warsaw",
        "address": "Estrady 13K",
        "courts": 8,
        "lat": 52.29213636,
        "lon": 20.87689692,
    },
    "interpadel-warszawa": {
        "tenant_id": "057c5f40-f54b-4e4d-977c-1f9547a25076",
        "name": "Interpadel Warszawa",
        "city": "Warszawa",
        "address": "Bokserska 66A",
        "courts": 11,
        "lat": 52.17282,
        "lon": 20.988908,
    },
    "rakiety---outdoor-padel": {
        "tenant_id": "f3f86625-3c23-41fd-be77-526395fabe74",
        "name": "Rakiety Aero - Padel Outdoor",
        "city": "Warszawa",
        "address": "Wał Miedzeszyński 646",
        "courts": 1,
        "lat": 52.22189332,
        "lon": 21.08425495,
    },
    "rakiety-pge-narodowy": {
        "tenant_id": "153bbff6-abf6-4ffe-ad93-ba1045e9d43b",
        "name": "Rakiety PGE Narodowy - Padel Outdoor",
        "city": "Warszawa",
        "address": "al. Księcia Józefa Poniatowskiego 1",
        "courts": 5,
        "lat": 52.24113912,
        "lon": 21.04775185,
    },
    "warsaw-padel-club": {
        "tenant_id": "e7284c78-e269-44ad-8f3d-a4d63089c80c",
        "name": "Warsaw Padel Club",
        "city": "Warszawa",
        "address": "Annopol 3",
        "courts": 11,
        "lat": 52.30257,
        "lon": 21.01963,
    },
    "fiesta-padel": {
        "tenant_id": "cf58118a-353b-4ec1-a51e-ea52acc99063",
        "name": "Fiesta Padel",
        "city": "Wrocław",
        "address": "Kozanowska 69",
        "courts": 2,
        "lat": 51.13946108,
        "lon": 16.97328862,
    },
    "padel-pl-wrocław": {
        "tenant_id": "280bfe06-18e4-464f-a1f3-edc0bee96e35",
        "name": "Padel Pl Wrocław",
        "city": "Wrocław",
        "address": "Żmigrodzka 242D",
        "courts": 11,
        "lat": 51.16080948,
        "lon": 17.02350386,
    },
    "akademia-padla-bukowska": {
        "tenant_id": "bc890e60-1580-43c2-8721-b96fa53bb775",
        "name": "Akademia Padla Bukowska",
        "city": "Wysogotowo",
        "address": "Bukowska 10",
        "courts": 5,
        "lat": 52.41580815,
        "lon": 16.78370712,
    },
    "padelteam-zabrze": {
        "tenant_id": "90779e1e-84b3-404f-820d-73a83a467b4e",
        "name": "Padelteam Zabrze",
        "city": "Zabrze",
        "address": "Piłsudskiego 83A",
        "courts": 4,
        "lat": 50.2978909,
        "lon": 18.7642584,
    },
}


# --- Summary ---
# Total clubs: 23
#
# Breakdown by city:
#   Bytom: 1
#   Gdynia: 1
#   Katowice: 2
#   Mała Nieszawka: 1
#   Opole: 1
#   Poznań: 3
#   Pszczyna: 1
#   Szczecin: 1
#   Toruń: 2
#   Tychy: 1
#   Warsaw: 1
#   Warszawa: 4
#   Wrocław: 2
#   Wysogotowo: 1
#   Zabrze: 1


if __name__ == "__main__":
    print(f"Total padel clubs in Poland: {len(PLAYTOMIC_CLUBS)}")
    print()
    city_counts = {}
    for uid, club in PLAYTOMIC_CLUBS.items():
        city = club["city"]
        city_counts[city] = city_counts.get(city, 0) + 1
    print("Breakdown by city:")
    for city in sorted(city_counts.keys()):
        print(f"  {city}: {city_counts[city]}")
    print()
    print("All clubs:")
    for uid, club in sorted(PLAYTOMIC_CLUBS.items(), key=lambda x: (x[1]["city"], x[1]["name"])):
        print(f"  [{club['city']}] {club['name']} - {club['courts']} courts ({uid})")
