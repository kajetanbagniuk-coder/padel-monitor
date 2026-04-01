"""
All padel clubs in Poland — unified registry.

Each club has a booking_system field:
  - "kluby_org"  = only on kluby.org
  - "playtomic"  = only on Playtomic
  - "both"       = on both platforms

Clubs on Playtomic also have playtomic_id and playtomic_slug fields.
The dict key is the kluby.org slug (for kluby/both clubs) or Playtomic slug (for Playtomic-only).
"""

CLUBS = {
    # ── kluby.org only ────────────────────────────────────────────
    "ahoj-padel": {"name": "Ahoj Padel", "slug": "ahoj-padel", "courts": 4, "city": "Niepolomice", "booking_system": "kluby_org"},
    "akademia-padla": {"name": "Akademia Padla", "slug": "akademia-padla", "courts": 4, "city": "Poznan", "booking_system": "kluby_org"},
    "amber-park": {"name": "Amber Park Spa", "slug": "amber-park", "courts": 1, "city": "Niechorze", "booking_system": "kluby_org"},
    "asaja-sport": {"name": "ASAJA SPORT", "slug": "asaja-sport", "courts": 1, "city": "Rogozino", "booking_system": "kluby_org"},
    "bajada-sports-club": {"name": "Bajada Padel Club", "slug": "bajada-sports-club", "courts": 3, "city": "Krakow", "booking_system": "kluby_org"},
    "baltic-padel-club": {"name": "Baltic Padel Club", "slug": "baltic-padel-club", "courts": 9, "city": "Gdynia", "booking_system": "kluby_org"},
    "baza-padel-club": {"name": "Baza Padel Club", "slug": "baza-padel-club", "courts": 5, "city": "Grudziadz", "booking_system": "kluby_org"},
    "baza-sport-suchy-dwor": {"name": "BAZA SPORT SUCHY DWOR", "slug": "baza-sport-suchy-dwor", "courts": 2, "city": "Suchy Dwor", "booking_system": "kluby_org"},
    "bulwary-wislane": {"name": "Padel4All Bulwary Wislane", "slug": "bulwary-wislane", "courts": 1, "city": "Warszawa", "booking_system": "kluby_org"},
    "calisia-padel": {"name": "Calisia Padel", "slug": "calisia-padel", "courts": 7, "city": "Kalisz", "booking_system": "kluby_org"},
    "carthagowola": {"name": "Carthagowola Klub Padel", "slug": "carthagowola", "courts": 2, "city": "Turbia", "booking_system": "kluby_org"},
    "chorzowska-liga-padla": {"name": "Chorzowska Liga Padla", "slug": "chorzowska-liga-padla", "courts": 2, "city": "Chorzow", "booking_system": "kluby_org"},
    "csr-platinum": {"name": "CSR Platinum", "slug": "csr-platinum", "courts": 2, "city": "Rybnik", "booking_system": "kluby_org"},
    "fast-tennis-gdanska": {"name": "Fast Tennis Padel Club", "slug": "fast-tennis-gdanska", "courts": 2, "city": "Bydgoszcz", "booking_system": "kluby_org"},
    "gdynia-padel-club": {"name": "GDYNIA PADEL CLUB", "slug": "gdynia-padel-club", "courts": 6, "city": "Gdynia", "booking_system": "kluby_org"},
    "happy-padel": {"name": "Happy Padel", "slug": "happy-padel", "courts": 3, "city": "Warszawa", "booking_system": "kluby_org"},
    "kortmax": {"name": "Kortmax", "slug": "kortmax", "courts": 2, "city": "Blonie", "booking_system": "kluby_org"},
    "leo-padel": {"name": "LEO PADEL", "slug": "leo-padel", "courts": 2, "city": "Trabki Wielkie", "booking_system": "kluby_org"},
    "loba-padel": {"name": "Loba Padel", "slug": "loba-padel", "courts": 8, "city": "Warszawa", "booking_system": "kluby_org"},
    "lomianki-padel-club": {"name": "Lomianki Padel Club", "slug": "lomianki-padel-club", "courts": 4, "city": "Lomianki", "booking_system": "kluby_org"},
    "mana-padel": {"name": "Mana Padel", "slug": "mana-padel", "courts": 8, "city": "Warszawa", "booking_system": "kluby_org"},
    "mera": {"name": "WKT Mera", "slug": "mera", "courts": 2, "city": "Warszawa", "booking_system": "kluby_org"},
    "miedzeszyn": {"name": "Klub Miedzeszyn", "slug": "miedzeszyn", "courts": 2, "city": "Warszawa", "booking_system": "kluby_org"},
    "moris-katowicka": {"name": "MORIS Chorzow", "slug": "moris-katowicka", "courts": 2, "city": "Chorzow", "booking_system": "kluby_org"},
    "mosir-slowian": {"name": "MOSiR Slowian", "slug": "mosir-slowian", "courts": 1, "city": "Katowice", "booking_system": "kluby_org"},
    "nowosolna": {"name": "Korty Nowosolna", "slug": "nowosolna", "courts": 1, "city": "Lodz", "booking_system": "kluby_org"},
    "one-padel": {"name": "One Padel Center", "slug": "one-padel", "courts": 4, "city": "Bielsko-Biala", "booking_system": "kluby_org"},
    "padbox": {"name": "PADBOX STADION", "slug": "padbox", "courts": 5, "city": "Gdansk", "booking_system": "kluby_org"},
    "padbox-kartuska": {"name": "PADBOX KARTUSKA", "slug": "padbox-kartuska", "courts": 5, "city": "Gdansk", "booking_system": "kluby_org"},
    "padel-arena": {"name": "Padel Arena Limanowa", "slug": "padel-arena", "courts": 3, "city": "Limanowa", "booking_system": "kluby_org"},
    "padel-club-szczecin": {"name": "Padel Club Szczecin", "slug": "padel-club-szczecin", "courts": 5, "city": "Szczecin", "booking_system": "kluby_org"},
    "padel-factory": {"name": "Padel Factory", "slug": "padel-factory", "courts": 2, "city": "Nowy Sacz", "booking_system": "kluby_org"},
    "padel-gdansk": {"name": "Padel Gdansk", "slug": "padel-gdansk", "courts": 6, "city": "Gdansk", "booking_system": "kluby_org"},
    "padel-house-krakow": {"name": "Padel House Krakow", "slug": "padel-house-krakow", "courts": 4, "city": "Krakow", "booking_system": "kluby_org"},
    "padel-jaworzno": {"name": "Padel Jaworzno VIA Sport", "slug": "padel-jaworzno", "courts": 4, "city": "Jaworzno", "booking_system": "kluby_org"},
    "padel-lodz": {"name": "Padel Lodz", "slug": "padel-lodz", "courts": 2, "city": "Lodz", "booking_system": "kluby_org"},
    "padel-park": {"name": "Padel Park", "slug": "padel-park", "courts": 4, "city": "Pruszcz Gdanski", "booking_system": "kluby_org"},
    "padel-park-bydgoszcz": {"name": "Padel Park Bydgoszcz", "slug": "padel-park-bydgoszcz", "courts": 2, "city": "Bydgoszcz", "booking_system": "kluby_org"},
    "padel-point-bialystok": {"name": "Padel Point Bialystok", "slug": "padel-point-bialystok", "courts": 5, "city": "Bialystok", "booking_system": "kluby_org"},
    "padel-point-lublin": {"name": "Padel Point Lublin", "slug": "padel-point-lublin", "courts": 5, "city": "Lublin", "booking_system": "kluby_org"},
    "padel-radom": {"name": "Padel Radom", "slug": "padel-radom", "courts": 4, "city": "Radom", "booking_system": "kluby_org"},
    "padel-score-elblag": {"name": "Padel Score Elblag", "slug": "padel-score-elblag", "courts": 2, "city": "Elblag", "booking_system": "kluby_org"},
    "padelbox-rzeszow": {"name": "PadelBOX Rzeszow", "slug": "padelbox-rzeszow", "courts": 2, "city": "Rzeszow", "booking_system": "kluby_org"},
    "padelmania": {"name": "Padelmania", "slug": "padelmania", "courts": 3, "city": "Dabrowa Gornicza", "booking_system": "kluby_org"},
    "payments-lights": {"name": "PAYMENTS & LIGHTS", "slug": "payments-lights", "courts": 5, "city": "Lubsko", "booking_system": "kluby_org"},
    "pisz-point": {"name": "Klub Tenisowy Pisz-Point", "slug": "pisz-point", "courts": 2, "city": "Pisz", "booking_system": "kluby_org"},
    "pogoria-padel-club": {"name": "Pogoria Padel Club", "slug": "pogoria-padel-club", "courts": 2, "city": "Dabrowa Gornicza", "booking_system": "kluby_org"},
    "prestigecourt": {"name": "Otwocka Akademia Tenisa", "slug": "prestigecourt", "courts": 1, "city": "Otwock", "booking_system": "kluby_org"},
    "propadel": {"name": "ProPadel Jutrzenki", "slug": "propadel", "courts": 5, "city": "Warszawa", "booking_system": "kluby_org"},
    "pura-padel-pickleball": {"name": "PURA PADEL", "slug": "pura-padel-pickleball", "courts": 5, "city": "Bydgoszcz", "booking_system": "kluby_org"},
    "rakietmania": {"name": "Rakietmania", "slug": "rakietmania", "courts": 1, "city": "Lublin", "booking_system": "kluby_org"},
    "sporteum": {"name": "Sporteum", "slug": "sporteum", "courts": 2, "city": "Warszawa", "booking_system": "kluby_org"},
    "stacja-padel": {"name": "Stacja Padel", "slug": "stacja-padel", "courts": 5, "city": "Lodz", "booking_system": "kluby_org"},
    "tenes": {"name": "TENES Klub Sportowy", "slug": "tenes", "courts": 3, "city": "Jawczyce", "booking_system": "kluby_org"},
    "teniswil": {"name": "TenisWil", "slug": "teniswil", "courts": 3, "city": "Warszawa", "booking_system": "kluby_org"},
    "toro-padel": {"name": "Toro Padel", "slug": "toro-padel", "courts": 6, "city": "Warszawa", "booking_system": "kluby_org"},
    "ultra-padel-gliwice": {"name": "ULTRA PADEL Gliwice", "slug": "ultra-padel-gliwice", "courts": 4, "city": "Gliwice", "booking_system": "kluby_org"},

    # ── Both platforms (kluby.org + Playtomic) ────────────────────
    "city-padel-torun": {"name": "City Padel Torun", "slug": "city-padel-torun", "courts": 5, "city": "Torun", "booking_system": "both", "playtomic_id": "828ccdaf-99e0-4989-86fb-a313529edc58", "playtomic_slug": "city-padel-torun"},
    "fabryka-energii": {"name": "Fabryka Energii", "slug": "fabryka-energii", "courts": 4, "city": "Szczecin", "booking_system": "both", "playtomic_id": "4c0b171f-8e62-48a2-8fdc-46fb5b1073e9", "playtomic_slug": "fabryka-energii"},
    "fiesta-padel": {"name": "Fiesta Padel", "slug": "fiesta-padel", "courts": 3, "city": "Wroclaw", "booking_system": "both", "playtomic_id": "cf58118a-353b-4ec1-a51e-ea52acc99063", "playtomic_slug": "fiesta-padel"},
    "interpadel-gdynia": {"name": "InterPadel Gdynia", "slug": "interpadel-gdynia", "courts": 10, "city": "Gdynia", "booking_system": "both", "playtomic_id": "91a60f0a-1fef-4efc-9548-3a6b37ae25e0", "playtomic_slug": "interpadel-gdynia"},
    "interpadel-poznan": {"name": "Interpadel Poznan", "slug": "interpadel-poznan", "courts": 9, "city": "Poznan", "booking_system": "both", "playtomic_id": "34f066f9-4292-4cce-923f-2fa95f1c7b47", "playtomic_slug": "interpadel-poznań"},
    "interpadel-torun": {"name": "InterPadel Torun", "slug": "interpadel-torun", "courts": 8, "city": "Torun", "booking_system": "both", "playtomic_id": "08e4db64-8cdd-4ae1-b38e-a8f7a77bfdcc", "playtomic_slug": "interpadel-torun"},
    "interpadel-warszawa": {"name": "InterPadel Warszawa", "slug": "interpadel-warszawa", "courts": 11, "city": "Warszawa", "booking_system": "both", "playtomic_id": "057c5f40-f54b-4e4d-977c-1f9547a25076", "playtomic_slug": "interpadel-warszawa"},
    "padel-center-academy": {"name": "Padel Center Academy", "slug": "padel-center-academy", "courts": 9, "city": "Katowice", "booking_system": "both", "playtomic_id": "dd500ac3-5004-41ee-ab6c-c60545ae3ae4", "playtomic_slug": "padel-center-academy"},
    "padel-on": {"name": "Padel On", "slug": "padel-on", "courts": 4, "city": "Pszczyna", "booking_system": "both", "playtomic_id": "8b616ddb-93a6-4629-a00a-b940a3f66e20", "playtomic_slug": "padel-on-"},
    "padel-pl-wroclaw": {"name": "Padel PL Wroclaw", "slug": "padel-pl-wroclaw", "courts": 11, "city": "Wroclaw", "booking_system": "both", "playtomic_id": "280bfe06-18e4-464f-a1f3-edc0bee96e35", "playtomic_slug": "padel-pl-wrocław"},
    "padel-team-bytom": {"name": "Padel Team Bytom", "slug": "padel-team-bytom", "courts": 9, "city": "Bytom", "booking_system": "both", "playtomic_id": "05a9122e-d8ff-442d-a026-58b98170b4d8", "playtomic_slug": "padel-team-bytom"},
    "padel-team-tychy": {"name": "Padel Team Tychy", "slug": "padel-team-tychy", "courts": 4, "city": "Tychy", "booking_system": "both", "playtomic_id": "d5a93847-b621-4852-9fa1-4a310afd3423", "playtomic_slug": "padel-team-tychy"},
    "padel-team-zabrze": {"name": "Padel Team Zabrze", "slug": "padel-team-zabrze", "courts": 4, "city": "Zabrze", "booking_system": "both", "playtomic_id": "90779e1e-84b3-404f-820d-73a83a467b4e", "playtomic_slug": "padelteam-zabrze"},
    "plek-poznan": {"name": "PLEK Poznan", "slug": "plek-poznan", "courts": 10, "city": "Poznan", "booking_system": "both", "playtomic_id": "56e1531e-e108-42af-b877-834a53381efa", "playtomic_slug": "plek-poznan"},
    "rancho-padel-club": {"name": "Rancho Padel Club", "slug": "rancho-padel-club", "courts": 5, "city": "Mala Nieszawka", "booking_system": "both", "playtomic_id": "9ac2868b-0085-4e1b-b22e-229866a1ad62", "playtomic_slug": "rancho-padel-club-"},
    "viva-padel-katowice": {"name": "VIVA PADEL KATOWICE", "slug": "viva-padel-katowice", "courts": 9, "city": "Katowice", "booking_system": "both", "playtomic_id": "84b91836-ee5b-42f1-8c44-77cde714d2e9", "playtomic_slug": "viva-padel-katowice"},
    "warsaw-padel-club": {"name": "Warsaw Padel Club", "slug": "warsaw-padel-club", "courts": 11, "city": "Warszawa", "booking_system": "both", "playtomic_id": "e7284c78-e269-44ad-8f3d-a4d63089c80c", "playtomic_slug": "warsaw-padel-club"},

    # ── Playtomic only ────────────────────────────────────────────
    "akademia-padla-bukowska": {"name": "Akademia Padla Bukowska", "slug": "akademia-padla-bukowska", "courts": 5, "city": "Wysogotowo", "booking_system": "playtomic", "playtomic_id": "bc890e60-1580-43c2-8721-b96fa53bb775", "playtomic_slug": "akademia-padla-bukowska"},
    "passion-padel": {"name": "Passion Padel", "slug": "passion-padel", "courts": 2, "city": "Poznan", "booking_system": "playtomic", "playtomic_id": "98ee88f9-0ad1-4c0e-84ab-f620097ee1d2", "playtomic_slug": "passion-padel"},
    "pop-yard-padel": {"name": "Pop Yard", "slug": "pop-yard-padel", "courts": 3, "city": "Opole", "booking_system": "playtomic", "playtomic_id": "68323d20-8d88-4653-9a50-148cb9a5b49e", "playtomic_slug": "pop-yard-padel"},
    "rakiety-outdoor-padel": {"name": "Rakiety Aero - Padel Outdoor", "slug": "rakiety-outdoor-padel", "courts": 1, "city": "Warszawa", "booking_system": "playtomic", "playtomic_id": "f3f86625-3c23-41fd-be77-526395fabe74", "playtomic_slug": "rakiety---outdoor-padel"},
    "rakiety-pge-narodowy": {"name": "Rakiety PGE Narodowy - Padel Outdoor", "slug": "rakiety-pge-narodowy", "courts": 5, "city": "Warszawa", "booking_system": "playtomic", "playtomic_id": "153bbff6-abf6-4ffe-ad93-ba1045e9d43b", "playtomic_slug": "rakiety-pge-narodowy"},
    "rqt-spot": {"name": "RQT Spot", "slug": "rqt-spot", "courts": 8, "city": "Warszawa", "booking_system": "playtomic", "playtomic_id": "44340c7a-0951-47bd-8a7e-ccbe0703cdc3", "playtomic_slug": "rqt-spot"},
}

DEFAULT_CLUB = "loba-padel"
