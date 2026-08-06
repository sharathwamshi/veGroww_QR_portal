"""
Event catalogue for the invitation generator.

Each event type declares which "host" fields it collects (bride/groom for a
wedding, baby name for a naming ceremony, and so on), whether it runs over
two sessions, and the palette it defaults to. The form, the validation and
the public invitation page all read from this one place, so adding a new
event type is a matter of adding a dict entry — nothing else changes.

Field spec: (name, label, required, placeholder)
"""

EVENT_TYPES = {
    # ---------------- Weddings and related ----------------
    "wedding": {
        "name": "Wedding",
        "icon": "&#128141;",
        "group": "Wedding",
        "two_sessions": True,
        "session_labels": ("Muhurtham / Ceremony", "Reception"),
        "hosts": [
            ("bride_name", "Bride's name", True, "E.g. Priya"),
            ("groom_name", "Groom's name", True, "E.g. Arun"),
            ("bride_parents", "Bride's parents", False, "D/o Mr. & Mrs. ..."),
            ("groom_parents", "Groom's parents", False, "S/o Mr. & Mrs. ..."),
        ],
        "palette": ("#8C1D40", "#D4A15E"),
        "greeting": "Together with our families, we invite you to celebrate our wedding",
    },
    "engagement": {
        "name": "Engagement",
        "icon": "&#128132;",
        "group": "Wedding",
        "two_sessions": False,
        "hosts": [
            ("bride_name", "Bride-to-be's name", True, "E.g. Priya"),
            ("groom_name", "Groom-to-be's name", True, "E.g. Arun"),
            ("bride_parents", "Bride's parents", False, ""),
            ("groom_parents", "Groom's parents", False, ""),
        ],
        "palette": ("#A0356B", "#E4B7C7"),
        "greeting": "We joyfully invite you to our engagement ceremony",
    },
    "reception": {
        "name": "Wedding Reception",
        "icon": "&#127870;",
        "group": "Wedding",
        "two_sessions": False,
        "hosts": [
            ("bride_name", "Bride's name", True, ""),
            ("groom_name", "Groom's name", True, ""),
        ],
        "palette": ("#5B2C6F", "#D2B4DE"),
        "greeting": "Please join us at our wedding reception",
    },
    "mehendi": {
        "name": "Mehendi / Haldi",
        "icon": "&#127807;",
        "group": "Wedding",
        "two_sessions": False,
        "hosts": [("celebrant_name", "Whose function", True, "E.g. Priya")],
        "palette": ("#A67C00", "#F2D680"),
        "greeting": "Join us for an evening of colour and celebration",
    },
    "anniversary": {
        "name": "Wedding Anniversary",
        "icon": "&#128149;",
        "group": "Wedding",
        "two_sessions": False,
        "hosts": [
            ("couple_names", "Couple's names", True, "E.g. Arun & Priya"),
            ("years_completed", "Years completed", False, "E.g. 25"),
        ],
        "palette": ("#7D3C98", "#E8DAEF"),
        "greeting": "Celebrating years of togetherness — please join us",
    },

    # ---------------- Baby and childhood ----------------
    "naming": {
        "name": "Naming Ceremony",
        "icon": "&#128118;",
        "group": "Baby & Childhood",
        "two_sessions": False,
        "hosts": [
            ("baby_name", "Baby's name", True, "E.g. Aarav"),
            ("parents_names", "Parents' names", False, "E.g. Arun & Priya"),
        ],
        "palette": ("#1F6F8B", "#A8DADC"),
        "greeting": "With joy, we invite you to our little one's naming ceremony",
    },
    "baby_shower": {
        "name": "Baby Shower / Seemantham",
        "icon": "&#127880;",
        "group": "Baby & Childhood",
        "two_sessions": False,
        "hosts": [("celebrant_name", "Mother-to-be's name", True, "E.g. Priya")],
        "palette": ("#D96C8E", "#F9DCE4"),
        "greeting": "Please join us in blessing the mother-to-be",
    },
    "cradle": {
        "name": "Cradle Ceremony",
        "icon": "&#128116;",
        "group": "Baby & Childhood",
        "two_sessions": False,
        "hosts": [
            ("baby_name", "Baby's name", False, ""),
            ("parents_names", "Parents' names", True, ""),
        ],
        "palette": ("#3E7C9B", "#BEE3F8"),
        "greeting": "We invite you to our baby's cradle ceremony",
    },
    "annaprasana": {
        "name": "Annaprasana (First Feeding)",
        "icon": "&#127859;",
        "group": "Baby & Childhood",
        "two_sessions": False,
        "hosts": [
            ("baby_name", "Baby's name", True, ""),
            ("parents_names", "Parents' names", False, ""),
        ],
        "palette": ("#B7791F", "#FAE9C8"),
        "greeting": "Join us for our little one's first-feeding ceremony",
    },
    "mundan": {
        "name": "Mundan / Tonsure",
        "icon": "&#9986;",
        "group": "Baby & Childhood",
        "two_sessions": False,
        "hosts": [
            ("baby_name", "Child's name", True, ""),
            ("parents_names", "Parents' names", False, ""),
        ],
        "palette": ("#8B5E3C", "#E8D5C4"),
        "greeting": "We invite you to our child's mundan ceremony",
    },
    "birthday": {
        "name": "Birthday",
        "icon": "&#127874;",
        "group": "Baby & Childhood",
        "two_sessions": False,
        "hosts": [
            ("celebrant_name", "Whose birthday", True, "E.g. Aarav"),
            ("turning_age", "Turning", False, "E.g. 5"),
        ],
        "palette": ("#2E86AB", "#F6C453"),
        "greeting": "You're invited to the birthday celebration",
    },

    # ---------------- Religious and cultural ----------------
    "housewarming": {
        "name": "Housewarming / Griha Pravesh",
        "icon": "&#127968;",
        "group": "Religious & Cultural",
        "two_sessions": False,
        "hosts": [("family_name", "Family name", True, "E.g. The Nair family")],
        "palette": ("#1B7A4B", "#B7E4C7"),
        "greeting": "With gratitude, we invite you to our new home",
    },
    "upanayanam": {
        "name": "Upanayanam / Thread Ceremony",
        "icon": "&#128367;",
        "group": "Religious & Cultural",
        "two_sessions": False,
        "hosts": [
            ("celebrant_name", "Whose ceremony", True, ""),
            ("parents_names", "Parents' names", False, ""),
        ],
        "palette": ("#9C4221", "#F3D5C0"),
        "greeting": "We invite you to the sacred thread ceremony",
    },
    "puja": {
        "name": "Puja / Satyanarayana Puja",
        "icon": "&#128367;",
        "group": "Religious & Cultural",
        "two_sessions": False,
        "hosts": [("family_name", "Hosted by", True, "E.g. The Nair family")],
        "palette": ("#B7791F", "#FBE8C8"),
        "greeting": "You are warmly invited to join us for the puja",
    },
    "festival": {
        "name": "Festival Gathering",
        "icon": "&#127881;",
        "group": "Religious & Cultural",
        "two_sessions": False,
        "hosts": [("family_name", "Hosted by", True, "")],
        "palette": ("#C2410C", "#FDD9A0"),
        "greeting": "Celebrate the festival with us",
    },
    "memorial": {
        "name": "Memorial / Remembrance",
        "icon": "&#128132;",
        "group": "Religious & Cultural",
        "two_sessions": False,
        "hosts": [
            ("remembered_name", "In memory of", True, ""),
            ("family_name", "Hosted by", False, ""),
        ],
        "palette": ("#4A5568", "#CBD5E0"),
        "greeting": "We gather in loving remembrance",
    },

    # ---------------- Milestones ----------------
    "graduation": {
        "name": "Graduation",
        "icon": "&#127891;",
        "group": "Milestones",
        "two_sessions": False,
        "hosts": [
            ("celebrant_name", "Graduate's name", True, ""),
            ("institution", "Institution", False, ""),
        ],
        "palette": ("#1E3A8A", "#BFD4F2"),
        "greeting": "Celebrate this milestone with us",
    },
    "retirement": {
        "name": "Retirement",
        "icon": "&#127882;",
        "group": "Milestones",
        "two_sessions": False,
        "hosts": [
            ("celebrant_name", "Whose retirement", True, ""),
            ("institution", "Organisation", False, ""),
        ],
        "palette": ("#2C5282", "#CDE3F5"),
        "greeting": "Join us in celebrating a remarkable innings",
    },
    "farewell": {
        "name": "Farewell",
        "icon": "&#128075;",
        "group": "Milestones",
        "two_sessions": False,
        "hosts": [("celebrant_name", "Farewell for", True, "")],
        "palette": ("#4C51BF", "#D6D9F7"),
        "greeting": "Join us for a farewell gathering",
    },

    # ---------------- Business ----------------
    "inauguration": {
        "name": "Shop / Office Inauguration",
        "icon": "&#9986;",
        "group": "Business",
        "two_sessions": False,
        "hosts": [
            ("business_name", "Business name", True, "E.g. Shetala Agencies"),
            ("family_name", "Hosted by", False, ""),
        ],
        "palette": ("#0B7285", "#A5E6F0"),
        "greeting": "We're delighted to invite you to our inauguration",
    },
    "corporate": {
        "name": "Corporate Event / Launch",
        "icon": "&#128188;",
        "group": "Business",
        "two_sessions": False,
        "hosts": [
            ("business_name", "Company / event name", True, ""),
            ("institution", "Hosted by", False, ""),
        ],
        "palette": ("#123B6B", "#BBD4EF"),
        "greeting": "You are cordially invited",
    },
    "get_together": {
        "name": "Get-together / Party",
        "icon": "&#127867;",
        "group": "Business",
        "two_sessions": False,
        "hosts": [("family_name", "Hosted by", True, "")],
        "palette": ("#7B341E", "#F5CBA7"),
        "greeting": "Come celebrate with us",
    },
    "other": {
        "name": "Other Event",
        "icon": "&#128197;",
        "group": "Business",
        "two_sessions": False,
        "hosts": [("family_name", "Hosted by", True, "")],
        "palette": ("#1e5ba8", "#A9C9EC"),
        "greeting": "You are invited",
    },
}

# All host field names across every event type — the model stores them in one
# JSON column, so this is just for reference and validation.
ALL_HOST_FIELDS = sorted({field[0] for ev in EVENT_TYPES.values() for field in ev["hosts"]})


def event_meta(key: str) -> dict:
    """Look up an event type, falling back to 'other' for unknown keys."""
    return EVENT_TYPES.get(key, EVENT_TYPES["other"])


def grouped_events():
    """Event types bucketed by their group, for the template's picker."""
    groups = {}
    for key, meta in EVENT_TYPES.items():
        groups.setdefault(meta["group"], []).append((key, meta))
    return groups
