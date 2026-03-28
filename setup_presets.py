#!/usr/bin/env python3
"""Setup helper to pre-download preset songs into the local song library."""

import time

from app import scraper, storage

PRESET_QUERIES = [
    "Nirvana Smells Like Teen Spirit",
    "Queen Bohemian Rhapsody",
    "Oasis Wonderwall",
    "Metallica Enter Sandman",
    "The Beatles Hey Jude",
    "Guns N' Roses Sweet Child O' Mine",
    "Led Zeppelin Stairway to Heaven",
    "AC/DC Back in Black",
    "Pink Floyd Wish You Were Here",
    "Red Hot Chili Peppers Under the Bridge",
]


def predownload_presets():
    config = storage.load_config()
    default_zoom = config.get("default_zoom", 3)

    for query in PRESET_QUERIES:
        print(f"Searching for preset: {query}")
        results, err = scraper.search_ultimate_guitar(query)
        if err or not results:
            print(f"  Skipped: {err or 'no results'}")
            continue

        chosen = results[0]
        print(f"  Downloading: {chosen['artist']} - {chosen['song']}")
        content, err = scraper.fetch_tab_content(chosen['url'])
        if err or not content:
            print(f"  Failed: {err or 'empty content'}")
            continue

        folder, version = storage.save_song(
            f"{chosen['artist']} - {chosen['song']}",
            content,
            artist=chosen['artist'],
            default_zoom=default_zoom,
        )
        print(f"  Saved: {folder}/{version}\n")
        time.sleep(2)

    print("Preset download complete.")


if __name__ == "__main__":
    predownload_presets()
