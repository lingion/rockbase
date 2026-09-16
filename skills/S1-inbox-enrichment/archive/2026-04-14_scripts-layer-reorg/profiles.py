PROFILES = {
    "basic_platform_raw": {
        "target_fields": [
            "handle",
            "author_name",
            "country",
            "followers",
            "language",
            "bio_raw",
            "category_tags",
            "external_links_raw",
        ]
    },
    "deep_easykol": {
        "target_fields": [
            "top_pinned_views",
            "avg_views_10",
            "contact",
            "contact_note",
        ]
    },
    "basic_identity": {
        "target_fields": [
            "handle",
            "author_name",
            "country",
            "followers",
        ]
    },
    "ticnote_cdik": {
        "target_fields": [
            "top_pinned_views",
            "avg_views_10",
            "contact",
            "contact_note",
            "notes",
        ]
    }
}


def fields_for_profile(profile_name: str) -> list[str]:
    profile = PROFILES.get(profile_name)
    if not profile:
        raise ValueError(f"未知 profile: {profile_name}")
    return list(profile["target_fields"])
