import os
import json
import shutil

SONGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "songs")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def ensure_songs_dir():
    os.makedirs(SONGS_DIR, exist_ok=True)


def get_all_songs():
    ensure_songs_dir()
    songs = []
    for folder in sorted(os.listdir(SONGS_DIR)):
        path = os.path.join(SONGS_DIR, folder)
        if os.path.isdir(path):
            meta = load_metadata(folder)
            songs.append({
                "folder": folder,
                "name": meta.get("name", folder),
                "favourite": meta.get("favourite", False),
                "versions": get_versions(folder),
            })
    return songs


def get_versions(folder):
    path = os.path.join(SONGS_DIR, folder)
    versions = []
    for f in sorted(os.listdir(path)):
        if f.startswith("version_") and f.endswith(".txt"):
            versions.append(f)
    return versions


def load_song_version(folder, version_file):
    path = os.path.join(SONGS_DIR, folder, version_file)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error loading song: {e}"


def save_song(name, content, artist="", default_zoom=3):
    ensure_songs_dir()
    folder = sanitise_folder_name(name)
    song_path = os.path.join(SONGS_DIR, folder)
    os.makedirs(song_path, exist_ok=True)

    existing = get_versions(folder)
    version_num = len(existing) + 1
    version_file = f"version_{version_num}.txt"

    with open(os.path.join(song_path, version_file), "w", encoding="utf-8") as f:
        f.write(content)

    meta = load_metadata(folder)
    if "name" not in meta:
        meta["name"] = name
    if "zoom_level" not in meta:
        meta["zoom_level"] = default_zoom
    if artist:
        meta["artist"] = artist
    save_metadata(folder, meta)

    return folder, version_file


def rename_song(folder, new_name):
    meta = load_metadata(folder)
    meta["name"] = new_name
    save_metadata(folder, meta)
    new_folder = sanitise_folder_name(new_name)
    old_path = os.path.join(SONGS_DIR, folder)
    new_path = os.path.join(SONGS_DIR, new_folder)
    if old_path != new_path:
        shutil.move(old_path, new_path)
    return new_folder


def delete_song(folder):
    path = os.path.join(SONGS_DIR, folder)
    if os.path.exists(path):
        shutil.rmtree(path)


def toggle_favourite(folder):
    meta = load_metadata(folder)
    meta["favourite"] = not meta.get("favourite", False)
    save_metadata(folder, meta)
    return meta["favourite"]


def load_metadata(folder):
    path = os.path.join(SONGS_DIR, folder, "meta.json")
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_metadata(folder, meta):
    path = os.path.join(SONGS_DIR, folder, "meta.json")
    with open(path, "w") as f:
        json.dump(meta, f, indent=2)


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


def search_local(query):
    query = query.lower()
    results = []
    for song in get_all_songs():
        if query in song["name"].lower():
            results.append(song)
    return results


def sanitise_folder_name(name):
    keep = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-")
    return "".join(c if c in keep else "_" for c in name).strip().replace(" ", "_")
