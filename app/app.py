import os
os.environ["DISPLAY"] = ":0"

import logging
import customtkinter as ctk
import threading

from app.input_handler import (
    InputHandler,
    EVT_LEFT,
    EVT_RIGHT,
    EVT_MIDDLE,
    EVT_MIDDLE_LONG,
    EVT_MIDDLE_TRIPLE,
    EVT_SPACE,
    EVT_ZOOM_OUT,
    EVT_ZOOM_IN,
    EVT_PAGE_PREV,
    EVT_PAGE_NEXT,
    EVT_UNLOCK,
    EVT_LOCK,
)
from app.keyboard_widget import PedalKeyboard
from app import storage, scraper

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── States ────────────────────────────────────────────────────────────────────
STATE_STANDBY       = "standby"
STATE_MENU          = "menu"
STATE_ADD_SONG      = "add_song"
STATE_UG_RESULTS    = "ug_results"
STATE_UG_VERSIONS   = "ug_versions"
STATE_VIEW_ALL      = "view_all"
STATE_SONG_VIEW     = "song_view"
STATE_EDIT_MENU     = "edit_menu"
STATE_SEARCH_LOCAL  = "search_local"
STATE_LOCAL_RESULTS = "local_results"
STATE_RENAME        = "rename"
STATE_SETTINGS      = "settings"

MENU_ITEMS = ["➕  Add Song", "📂  View All Songs", "🔍 Search Song", "⚙️ Settings"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def make_scrollable_label(parent, text, font_size=14):
    frame = ctk.CTkScrollableFrame(parent)
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    lbl = ctk.CTkLabel(frame, text=text, font=ctk.CTkFont(size=font_size, family="Courier"),
                       justify="left", anchor="nw", wraplength=900)
    lbl.pack(anchor="nw")
    return frame


# ── App ───────────────────────────────────────────────────────────────────────
class StompApp(ctk.CTk):

    def __init__(self, use_gpio=True):
        super().__init__()
        self.title("Stomp — Guitar Tab Manager")
        self.attributes("-fullscreen", True)
        self.configure(fg_color="#0f0f0f")

        self.screen       = STATE_STANDBY
        self._sel_index  = 0
        self._list_data       = []          # generic list for any list screen
        self._list_page       = 0
        self._list_page_size  = 8
        self._ug_results      = []
        self._current_song    = None    # {folder, name, versions, favourite}
        self._current_tab     = ""      # full tab text
        self._tab_lines       = []
        self._tab_page        = 0
        self._zoom_level      = 3
        self._font_size       = self._font_for_zoom(self._zoom_level)
        self._lines_per_page  = self._lines_for_zoom(self._zoom_level)
        self._global_default_zoom = storage.load_config().get("default_zoom", 3)
        self._previous_screen = None
        self._edit_items      = ["✏️  Rename", "🗑️  Delete", "⭐  Toggle Favourite", "← Back"]
        self._status_msg      = ""

        # Input
        self._input = InputHandler(use_gpio=use_gpio, use_serial=True)
        logger.info("Input handler initialized (use_gpio=%s)", use_gpio)
        self._input.on(EVT_LEFT,          self._on_left)
        self._input.on(EVT_RIGHT,         self._on_right)
        self._input.on(EVT_MIDDLE,        self._on_middle)
        self._input.on(EVT_MIDDLE_LONG,   self._on_middle_long)
        self._input.on(EVT_MIDDLE_TRIPLE, self._on_middle_triple)
        self._input.on(EVT_SPACE,         self._on_space)
        self._input.on(EVT_ZOOM_OUT,      self._on_zoom_out)
        self._input.on(EVT_ZOOM_IN,       self._on_zoom_in)
        self._input.on(EVT_PAGE_PREV,     self._on_page_prev)
        self._input.on(EVT_PAGE_NEXT,     self._on_page_next)
        self._input.on(EVT_UNLOCK,        self._on_unlock)
        self._input.on(EVT_LOCK,          self._on_lock)
        self._input.bind_keyboard(self)

        # Main content area
        self._content = ctk.CTkFrame(self, fg_color="#0f0f0f")
        self._content.pack(fill="both", expand=True)

        # Status bar
        self._status_var = ctk.StringVar(value="")
        ctk.CTkLabel(self, textvariable=self._status_var,
                     font=ctk.CTkFont(size=12), text_color="gray",
                     height=24).pack(side="bottom", fill="x", padx=10)

        self.after(100, lambda: self.attributes("-fullscreen", True))
        self._render_standby()
        self.bind("<Escape>", self._handle_escape)
        logger.info("StompApp UI rendered and fullscreen enabled")

    # ── Screen clearing ───────────────────────────────────────────────────────
    def _clear(self):
        for w in self._content.winfo_children():
            w.destroy()

    def _set_status(self, msg):
        self._status_var.set(msg)

    # ── Input routing ─────────────────────────────────────────────────────────
    def _on_left(self):
        self.after(0, self._handle_left)

    def _on_right(self):
        self.after(0, self._handle_right)

    def _on_middle(self):
        self.after(0, self._handle_middle)

    def _on_middle_long(self):
        self.after(0, self._handle_middle_long)

    def _on_middle_triple(self):
        self.after(0, self._handle_middle_triple)

    def _on_zoom_out(self):
        self.after(0, self._handle_zoom_out)

    def _on_zoom_in(self):
        self.after(0, self._handle_zoom_in)

    def _on_space(self):
        self.after(0, self._handle_space)

    def _on_page_prev(self):
        self.after(0, self._handle_page_prev)

    def _on_page_next(self):
        self.after(0, self._handle_page_next)

    def _on_unlock(self):
        self.after(0, self._handle_unlock)

    def _handle_unlock(self):
        if self.screen == STATE_STANDBY:
            self.screen = STATE_MENU
            self._sel_index = 0
            self._render_menu()

    def _on_lock(self):
        self.after(0, self._handle_lock)

    def _handle_lock(self):
        if self.screen == STATE_MENU:
            self.screen = STATE_STANDBY
            self._render_standby()

    def _handle_escape(self, event=None):
        if self.screen == STATE_STANDBY:
            return
        if self.screen == STATE_MENU:
            self.screen = STATE_STANDBY
            self._render_standby()
            return
        self._go_back()

    def _handle_left(self):
        s = self.screen
        if s == STATE_MENU:
            self._sel_index = (self._sel_index - 1) % len(MENU_ITEMS)
            self._render_menu()
        elif s in (STATE_UG_RESULTS, STATE_VIEW_ALL, STATE_UG_VERSIONS,
                   STATE_EDIT_MENU, STATE_LOCAL_RESULTS):
            self._sel_index = max(0, self._sel_index - 1)
            self._ensure_list_page_for_selection()
            self._render_list_screen()
        elif s == STATE_SONG_VIEW:
            self._page_prev()
        elif s == STATE_SETTINGS:
            self._adjust_default_zoom(-1)
        elif s == STATE_ADD_SONG:
            self._kb_widget.pedal_left()
        elif s == STATE_SEARCH_LOCAL:
            self._kb_widget.pedal_left()
        elif s == STATE_RENAME:
            self._kb_widget.pedal_left()

    def _handle_right(self):
        s = self.screen
        if s == STATE_MENU:
            self._sel_index = (self._sel_index + 1) % len(MENU_ITEMS)
            self._render_menu()
        elif s in (STATE_UG_RESULTS, STATE_VIEW_ALL, STATE_UG_VERSIONS,
                   STATE_EDIT_MENU, STATE_LOCAL_RESULTS):
            self._sel_index = min(len(self._list_data) - 1, self._sel_index + 1)
            self._ensure_list_page_for_selection()
            self._render_list_screen()
        elif s == STATE_SONG_VIEW:
            self._page_next()
        elif s == STATE_SETTINGS:
            self._adjust_default_zoom(1)
        elif s == STATE_ADD_SONG:
            self._kb_widget.pedal_right()
        elif s == STATE_SEARCH_LOCAL:
            self._kb_widget.pedal_right()
        elif s == STATE_RENAME:
            self._kb_widget.pedal_right()

    def _handle_middle(self):
        s = self.screen
        if s == STATE_ADD_SONG:
            self._kb_widget.pedal_select()
        elif s == STATE_SEARCH_LOCAL:
            self._kb_widget.pedal_select()
        elif s == STATE_RENAME:
            self._kb_widget.pedal_select()
        elif s == STATE_SONG_VIEW:
            self._page_next()

    def _handle_page_prev(self):
        if self.screen == STATE_SONG_VIEW:
            self._page_prev()
        elif self.screen in (STATE_UG_RESULTS, STATE_VIEW_ALL, STATE_UG_VERSIONS,
                             STATE_EDIT_MENU, STATE_LOCAL_RESULTS):
            self._list_page = max(0, self._list_page - 1)
            self._sel_index = min(len(self._list_data) - 1, self._list_page * self._list_page_size)
            self._render_list_screen()

    def _handle_page_next(self):
        if self.screen == STATE_SONG_VIEW:
            self._page_next()
        elif self.screen in (STATE_UG_RESULTS, STATE_VIEW_ALL, STATE_UG_VERSIONS,
                             STATE_EDIT_MENU, STATE_LOCAL_RESULTS):
            max_page = max(0, (len(self._list_data) - 1) // self._list_page_size)
            self._list_page = min(max_page, self._list_page + 1)
            self._sel_index = min(len(self._list_data) - 1, self._list_page * self._list_page_size)
            self._render_list_screen()

    def _handle_middle_triple(self):
        s = self.screen
        if s == STATE_MENU:
            [self._go_add_song, self._go_view_all, self._go_search_local, self._go_settings][self._sel_index]()
        elif s == STATE_ADD_SONG:
            self._kb_widget.pedal_select()
        elif s == STATE_SEARCH_LOCAL:
            self._kb_widget.pedal_select()
        elif s == STATE_RENAME:
            self._kb_widget.pedal_select()
        elif s == STATE_UG_RESULTS:
            self._select_ug_result()
        elif s == STATE_UG_VERSIONS:
            self._select_ug_version()
        elif s == STATE_VIEW_ALL:
            self._open_song_from_list()
        elif s == STATE_LOCAL_RESULTS:
            self._open_local_result()
        elif s == STATE_SONG_VIEW:
            self._go_edit_menu()
        elif s == STATE_SETTINGS:
            self._go_back()
        elif s == STATE_EDIT_MENU:
            self._select_edit_action()

    def _handle_space(self):
        if self.screen in (STATE_ADD_SONG, STATE_SEARCH_LOCAL, STATE_RENAME):
            self._kb_widget.type_char(' ')

    def _handle_zoom_in(self):
        if self.screen == STATE_SONG_VIEW:
            self._set_zoom_level(min(8, self._zoom_level + 1))
            self._render_song_view()

    def _handle_zoom_out(self):
        if self.screen == STATE_SONG_VIEW:
            self._set_zoom_level(max(0, self._zoom_level - 1))
            self._render_song_view()

    def _ensure_list_page_for_selection(self):
        if not self._list_data:
            self._sel_index = 0
            self._list_page = 0
            return
        self._sel_index = min(self._sel_index, len(self._list_data) - 1)
        max_page = max(0, (len(self._list_data) - 1) // self._list_page_size)
        self._list_page = min(max_page, self._sel_index // self._list_page_size)

    def _zoom_in(self):
        if self.screen != STATE_SONG_VIEW:
            return
        self._set_zoom_level(min(5, self._zoom_level + 1))
        self._render_song_view()

    def _zoom_out(self):
        if self.screen != STATE_SONG_VIEW:
            return
        self._set_zoom_level(max(1, self._zoom_level - 1))
        self._render_song_view()

    def _adjust_default_zoom(self, delta):
        self._global_default_zoom = min(8, max(0, self._global_default_zoom + delta))
        storage.save_config({"default_zoom": self._global_default_zoom})
        self._set_status(f"Default zoom set to {self._global_default_zoom}")
        if self.screen == STATE_SETTINGS:
            self._render_settings_screen()

    def _compute_lines_per_page(self):
        self.update_idletasks()
        total_height = max(0, self.winfo_height())
        header_height = 56
        footer_height = 40
        padding = 24
        line_height = max(12, int(self._font_size * 1.4))
        available = max(1, total_height - header_height - footer_height - padding)
        return max(4, available // line_height)

    def _page_prev(self):
        lpp = self._compute_lines_per_page()
        max_page = max(0, (len(self._tab_lines) - 1) // lpp)
        self._tab_page = max(0, self._tab_page - 1)
        self._render_song_view()

    def _page_next(self):
        lpp = self._compute_lines_per_page()
        max_page = max(0, (len(self._tab_lines) - 1) // lpp)
        self._tab_page = min(max_page, self._tab_page + 1)
        self._render_song_view()

    def _handle_middle_long(self):
        s = self.screen
        if s == STATE_SONG_VIEW:
            self._go_back()
        elif s in (STATE_ADD_SONG, STATE_SEARCH_LOCAL, STATE_RENAME):
            self.screen = STATE_MENU
            self._render_menu()
        elif s in (STATE_EDIT_MENU, STATE_UG_RESULTS, STATE_UG_VERSIONS,
                   STATE_LOCAL_RESULTS, STATE_SETTINGS):
            self._go_back()
        elif s == STATE_MENU:
            self.screen = STATE_STANDBY
            self._render_standby()

    def _lines_for_zoom(self, level):
        if level <= 0:
            return 96
        if level == 1:
            return 80
        if level == 2:
            return 62
        if level == 3:
            return 48
        if level == 4:
            return 36
        if level == 5:
            return 28
        if level == 6:
            return 22
        if level == 7:
            return 18
        if level >= 8:
            return 14
        return 48

    def _font_for_zoom(self, level):
        return max(10, 10 + 2 * level)

    def _set_zoom_level(self, level):
        self._zoom_level = level
        self._lines_per_page = self._lines_for_zoom(level)
        self._font_size = self._font_for_zoom(level)
        if self._current_song and self._current_song.get("folder"):
            meta = storage.load_metadata(self._current_song["folder"])
            meta["zoom_level"] = level
            storage.save_metadata(self._current_song["folder"], meta)

    def _load_current_song(self, song, content):
        self._current_song = song
        self._current_tab = content
        self._tab_lines = content.splitlines()
        self._tab_page = 0
        if song.get("folder"):
            meta = storage.load_metadata(song["folder"])
            self._zoom_level = meta.get("zoom_level", self._global_default_zoom)
        else:
            self._zoom_level = self._global_default_zoom
        self._font_size = self._font_for_zoom(self._zoom_level)

    def _save_current_song(self):
        name = self._current_song.get("name")
        if not name:
            self._render_error("Unable to save: song name missing.")
            return

        folder, version = storage.save_song(
            name,
            self._current_tab,
            artist=self._current_song.get("artist", ""),
            default_zoom=self._global_default_zoom
        )
        song_meta = storage.load_metadata(folder)
        self._current_song = {
            "folder": folder,
            "name": song_meta.get("name", name),
            "favourite": song_meta.get("favourite", False),
            "versions": storage.get_versions(folder),
        }
        self._load_current_song(self._current_song, self._current_tab)
        self._set_status(f"Saved: {name}")
        self.screen = STATE_SONG_VIEW
        self._render_song_view()

    # ── Navigation helpers ────────────────────────────────────────────────────
    def _go_back(self):
        s = self.screen
        if s == STATE_SONG_VIEW and self._previous_screen:
            self.screen = self._previous_screen
            if self.screen in (STATE_VIEW_ALL, STATE_UG_RESULTS, STATE_UG_VERSIONS, STATE_LOCAL_RESULTS):
                self._render_list_screen()
            elif self.screen == STATE_SEARCH_LOCAL:
                self._render_search_local()
            else:
                self._render_menu()
            return

        if s in (STATE_UG_RESULTS, STATE_ADD_SONG):
            self.screen = STATE_MENU
            self._render_menu()
        elif s == STATE_UG_VERSIONS:
            self.screen = STATE_UG_RESULTS
            self._render_list_screen()
        elif s == STATE_EDIT_MENU:
            self.screen = STATE_SONG_VIEW
            self._render_song_view()
        elif s == STATE_LOCAL_RESULTS:
            self.screen = STATE_SEARCH_LOCAL
            self._render_search_local()
        else:
            self.screen = STATE_MENU
            self._render_menu()

    def _go_add_song(self):
        self.screen = STATE_ADD_SONG
        self._render_keyboard_screen(
            prompt="Search Ultimate Guitar:",
            on_confirm=self._search_ug,
            on_cancel=lambda: (setattr(self, 'screen', STATE_MENU), self._render_menu())
        )

    def _go_view_all(self):
        self.screen = STATE_VIEW_ALL
        self._sel_index = 0
        self._list_page = 0
        songs = storage.get_all_songs()
        self._list_data = songs
        self._render_list_screen()

    def _go_search_local(self):
        self.screen = STATE_SEARCH_LOCAL
        self._render_search_local()

    def _go_edit_menu(self):
        self.screen = STATE_EDIT_MENU
        self._sel_index = 0
        self._list_page = 0
        if not self._current_song.get("folder"):
            self._edit_items = [
                "💾  Save",
                "← Back"
            ]
        else:
            fav = self._current_song.get("favourite", False)
            self._edit_items = [
                "✏️  Rename",
                "🗑️  Delete",
                f"{'★' if fav else '☆'}  {'Unfavourite' if fav else 'Favourite'}",
                "← Back"
            ]
        self._list_data = self._edit_items
        self._render_list_screen()

    def _go_settings(self):
        self.screen = STATE_SETTINGS
        self._sel_index = 0
        self._render_settings_screen()

    def _render_settings_screen(self):
        self._clear()

        header = ctk.CTkFrame(self._content, height=60, corner_radius=0, fg_color="#1a1a1a")
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Settings",
                     font=ctk.CTkFont(size=24, weight="bold")).pack(side="left", padx=16, pady=10)

        body = ctk.CTkFrame(self._content, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=40, pady=40)

        ctk.CTkLabel(body, text="Default Zoom",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(0, 16))
        ctk.CTkLabel(body, text=f"Current default zoom: {self._global_default_zoom}",
                     font=ctk.CTkFont(size=18), text_color="gray").pack(pady=(0, 8))

        zoom_map = {
            1: "Tiny",
            2: "Small",
            3: "Normal",
            4: "Large",
            5: "Huge",
        }
        ctk.CTkLabel(body, text=f"Zoom level meaning: {zoom_map.get(self._global_default_zoom, 'Normal')}",
                     font=ctk.CTkFont(size=16), text_color="gray").pack(pady=(0, 24))

        ctk.CTkLabel(body,
                     text="Use ◀ / ▶ to change the default zoom, then press middle triple to return.",
                     font=ctk.CTkFont(size=14), text_color="#888",
                     wraplength=700, justify="left").pack(pady=(0, 8))

        self._render_footer("◀ / ▶ change default zoom   |   middle triple = back   |   hold middle = lock")

    # ── UG Search ─────────────────────────────────────────────────────────────
    def _search_ug(self, query):
        self._set_status(f"Searching Ultimate Guitar for '{query}'...")
        self._render_loading("Searching Ultimate Guitar…")

        def task():
            results, err = scraper.search_ultimate_guitar(query)
            self.after(0, lambda: self._on_ug_results(results, err, query))

        threading.Thread(target=task, daemon=True).start()

    def _on_ug_results(self, results, err, query):
        if err:
            self._set_status(f"Error: {err}")
            self._render_error(err)
            return
        if not results:
            self._set_status("No results found.")
            self._render_error(f"No results found for '{query}'")
            return

        self._ug_results = results
        self._list_page = 0
        self._list_data  = [f"{r['artist']} — {r['song']}  [{r['type']}]" for r in results]
        self.screen = STATE_UG_RESULTS
        self._sel_index = 0
        self._set_status(f"{len(results)} results found")
        self._render_list_screen()

    def _select_ug_result(self):
        if not self._ug_results:
            return
        chosen = self._ug_results[self._sel_index]
        self._pending_ug_result = chosen
        self._set_status(f"Selected: {chosen['song']}")

        # If we have a direct URL, go straight to download confirmation
        self._list_data = [f"Version {chosen['version']}  [{chosen['type']}]  ★{chosen['rating']:.1f}"]
        self.screen = STATE_UG_VERSIONS
        self._sel_index = 0
        self._render_list_screen()

    def _select_ug_version(self):
        chosen = self._pending_ug_result
        url = chosen.get("url", "")
        if not url:
            self._render_error("No URL available for this tab.")
            return

        self._set_status("Downloading tab…")
        self._render_loading("Downloading tab…")

        def task():
            content, err = scraper.fetch_tab_content(url)
            self.after(0, lambda: self._on_tab_downloaded(content, err, chosen))

        threading.Thread(target=task, daemon=True).start()

    def _on_tab_downloaded(self, content, err, meta):
        if err or not content:
            self._render_error(err or "Failed to download tab.")
            return

        name = f"{meta['artist']} - {meta['song']}"
        self._set_status(f"Downloaded: {name}. Select Save to keep it.")

        self._current_song = {
            "folder": None,
            "name": name,
            "favourite": False,
            "versions": [],
            "artist": meta.get("artist", ""),
            "saved": False,
        }
        self._load_current_song(self._current_song, content)
        self.screen = STATE_SONG_VIEW
        self._render_song_view()

    # ── View All ──────────────────────────────────────────────────────────────
    def _open_song_from_list(self):
        if not self._list_data:
            return
        song = self._list_data[self._sel_index]
        versions = song["versions"]
        if not versions:
            self._set_status("No versions downloaded.")
            return
        content = storage.load_song_version(song["folder"], versions[0])
        self._previous_screen = self.screen
        self._load_current_song(song, content)
        self.screen = STATE_SONG_VIEW
        self._render_song_view()

    # ── Local Search ──────────────────────────────────────────────────────────
    def _render_search_local(self):
        self.screen = STATE_SEARCH_LOCAL
        self._render_keyboard_screen(
            prompt="Search your songs:",
            on_confirm=self._do_local_search,
            on_cancel=lambda: (setattr(self, 'screen', STATE_MENU), self._render_menu())
        )

    def _do_local_search(self, query):
        results = storage.search_local(query)
        self._list_page = 0
        self._list_data = results
        self.screen = STATE_LOCAL_RESULTS
        self._sel_index = 0
        self._set_status(f"{len(results)} local results")
        self._render_list_screen()

    def _open_local_result(self):
        if not self._list_data:
            return
        song = self._list_data[self._sel_index]
        versions = song["versions"]
        if not versions:
            self._set_status("No versions downloaded.")
            return
        content = storage.load_song_version(song["folder"], versions[0])
        self._previous_screen = self.screen
        self._load_current_song(song, content)
        self.screen = STATE_SONG_VIEW
        self._render_song_view()

    # ── Edit Menu ─────────────────────────────────────────────────────────────
    def _select_edit_action(self):
        idx = self._sel_index
        folder = self._current_song.get("folder")

        if not folder:
            if idx == 0:  # Save
                self._save_current_song()
            elif idx == 1:  # Back
                self.screen = STATE_SONG_VIEW
                self._render_song_view()
            return

        if idx == 0:  # Rename
            self.screen = STATE_RENAME
            self._render_keyboard_screen(
                prompt="New name:",
                on_confirm=self._do_rename,
                on_cancel=self._go_edit_menu
            )
        elif idx == 1:  # Delete
            storage.delete_song(folder)
            self._set_status("Song deleted.")
            self._go_view_all()
        elif idx == 2:  # Favourite
            fav = storage.toggle_favourite(folder)
            self._current_song["favourite"] = fav
            self._set_status(f"{'Favourited ★' if fav else 'Unfavourited'}")
            self._go_edit_menu()
        elif idx == 3:  # Back
            self.screen = STATE_SONG_VIEW
            self._render_song_view()

    def _do_rename(self, new_name):
        new_folder = storage.rename_song(self._current_song["folder"], new_name)
        self._current_song["folder"] = new_folder
        self._current_song["name"]   = new_name
        self._set_status(f"Renamed to {new_name}")
        self.screen = STATE_SONG_VIEW
        self._render_song_view()

    # ══════════════════════════════════════════════════════════════════════════
    # Renderers
    # ══════════════════════════════════════════════════════════════════════════

    def _render_standby(self):
        self._clear()
        f = ctk.CTkFrame(self._content, fg_color="transparent")
        f.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(f, text="🎸", font=ctk.CTkFont(size=72)).pack(pady=(0, 16))
        ctk.CTkLabel(f, text="STOMP", font=ctk.CTkFont(size=56, weight="bold"),
                     text_color="white").pack()
        ctk.CTkLabel(f, text="Guitar Tab Manager",
                     font=ctk.CTkFont(size=20), text_color="gray").pack(pady=4)

        ctk.CTkFrame(f, height=2, fg_color="gray30").pack(fill="x", pady=24)

        ctk.CTkLabel(f, text="Press two pedals (including middle) to unlock",
                     font=ctk.CTkFont(size=18), text_color="#888").pack()
        ctk.CTkLabel(f, text="(or press  U  on keyboard)",
                     font=ctk.CTkFont(size=13), text_color="#555").pack(pady=4)
        self._render_footer("U = unlock | press two pedals (including middle) to unlock")

    def _render_footer(self, text):
        footer = ctk.CTkFrame(self._content, height=40, corner_radius=0, fg_color="#111")
        footer.pack(side="bottom", fill="x")
        ctk.CTkLabel(footer, text=text,
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=8)

    def _render_menu(self):
        self._clear()
        f = ctk.CTkFrame(self._content, fg_color="transparent")
        f.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(f, text="Main Menu",
                     font=ctk.CTkFont(size=32, weight="bold")).pack(pady=(0, 32))

        for i, item in enumerate(MENU_ITEMS):
            selected = i == self._sel_index
            btn = ctk.CTkButton(
                f, text=item,
                font=ctk.CTkFont(size=20, weight="bold" if selected else "normal"),
                width=380, height=60, corner_radius=14,
                fg_color=("#1e6fb5" if selected else "gray25"),
                hover_color="#1e6fb5",
                command=lambda x=i: self._menu_select(x)
            )
            btn.pack(pady=8)

        ctk.CTkLabel(f, text="◀ / ▶ navigate   |   middle triple = select   |   hold all 3 = lock",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(24, 0))
        self._render_footer("◀ / ▶ move   |   middle triple = select   |   hold all 3 = lock")

    def _menu_select(self, idx):
        self._sel_index = idx
        self._handle_middle()

    def _render_list_screen(self):
        """Generic list renderer used by UG results, view all, edit menu, etc."""
        self._clear()
        s = self.screen

        title_map = {
            STATE_UG_RESULTS:    "Search Results",
            STATE_UG_VERSIONS:   "Available Versions",
            STATE_VIEW_ALL:      "All Songs",
            STATE_EDIT_MENU:     "Edit Song",
            STATE_LOCAL_RESULTS: "Local Search Results",
        }
        title = title_map.get(s, "")

        # Header
        hdr = ctk.CTkFrame(self._content, height=60, corner_radius=0, fg_color="#1a1a1a")
        hdr.pack(fill="x")
        self._ensure_list_page_for_selection()
        max_page = max(0, (len(self._list_data) - 1) // self._list_page_size)
        self._list_page = min(self._list_page, max_page)
        start = self._list_page * self._list_page_size
        end = start + self._list_page_size
        page_items = self._list_data[start:end]

        ctk.CTkLabel(hdr, text=f"Page {self._list_page + 1} / {max_page + 1}",
                     font=ctk.CTkFont(size=14), text_color="gray").pack(side="right", padx=20)
        self._render_footer("◀ / ▶ select   |   middle triple = open   |   hold middle = back")

        if not page_items:
            empty_frame = ctk.CTkFrame(self._content, fg_color="transparent")
            empty_frame.pack(fill="both", expand=True, padx=16, pady=16)
            ctk.CTkLabel(empty_frame, text="No items found.", font=ctk.CTkFont(size=18),
                         text_color="gray").pack(pady=40)
            return

        container = ctk.CTkFrame(self._content, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=16, pady=16)

        for idx, item in enumerate(page_items):
            global_index = start + idx
            selected = global_index == self._sel_index

            if isinstance(item, dict):
                fav = "★ " if item.get("favourite") else ""
                text = f"{fav}{item.get('name', item.get('folder', '?'))}"
                sub = f"{len(item.get('versions', []))} version(s)"
            else:
                text = str(item)
                sub = ""

            row = ctk.CTkFrame(container, corner_radius=10,
                               fg_color=("#1e4d7a" if selected else ("gray20", "gray15")))
            row.pack(fill="x", pady=4)
            row.bind("<Button-1>", lambda e, x=global_index: self._list_click(x))

            ctk.CTkLabel(row, text=text,
                         font=ctk.CTkFont(size=17, weight="bold" if selected else "normal"),
                         anchor="w").pack(side="left", padx=16, pady=10)

            if sub:
                ctk.CTkLabel(row, text=sub, font=ctk.CTkFont(size=12),
                             text_color="gray", anchor="e").pack(side="right", padx=16)

            if selected:
                row.after(10, lambda r=row: r.tk.call('update', 'idletasks'))

    def _list_click(self, idx):
        self._sel_index = idx
        self._handle_middle()

    def _render_song_view(self):
        self._clear()
        song = self._current_song
        lines = self._tab_lines
        page  = self._tab_page
        lpp   = self._compute_lines_per_page()
        total_pages = max(1, (len(lines) + lpp - 1) // lpp)

        # Header
        hdr = ctk.CTkFrame(self._content, height=56, corner_radius=0, fg_color="#1a1a1a")
        hdr.pack(fill="x")

        fav = "★ " if song.get("favourite") else ""
        ctk.CTkLabel(hdr, text=f"{fav}{song['name']}",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=16, pady=8)
        ctk.CTkLabel(hdr, text=f"Zoom {self._zoom_level} | Page {page+1} / {total_pages}",
                     font=ctk.CTkFont(size=14), text_color="gray").pack(side="right", padx=16)

        # Tab content
        start = page * lpp
        visible = "\n".join(lines[start:start + lpp])
        content_frame = ctk.CTkFrame(self._content, fg_color="#0f0f0f")
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        content_label = ctk.CTkLabel(
            content_frame,
            text=visible,
            font=ctk.CTkFont(size=self._font_size, family="Courier"),
            justify="left",
            anchor="nw"
        )
        content_label.pack(fill="both", expand=True)

        # Footer
        ftr = ctk.CTkFrame(self._content, height=40, corner_radius=0, fg_color="#111")
        ftr.pack(fill="x")
        ctk.CTkLabel(ftr, text="◀ page prev   ▶ page next   |   left+middle = zoom out   right+middle = zoom in   |   middle triple = edit   |   hold middle = back to list",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=8)

    def _render_keyboard_screen(self, prompt, on_confirm, on_cancel=None):
        self._clear()
        self._kb_widget = PedalKeyboard(
            self._content,
            on_confirm=on_confirm,
            on_cancel=on_cancel,
            prompt=prompt,
            fg_color="transparent"
        )
        self._render_footer("◀ / ▶ move   |   middle = select   |   hold middle = submit | space = insert space")
        self._kb_widget.pack(expand=True, fill="both", padx=40, pady=(40, 0))

        # Wire normal typing
        self.bind("<Key>", self._kb_keypress)

    def _kb_keypress(self, event):
        if self.screen in (STATE_ADD_SONG, STATE_SEARCH_LOCAL, STATE_RENAME):
            ch = event.char
            if ch:
                self._kb_widget.type_char(ch)

    def _render_loading(self, msg="Loading…"):
        self._clear()
        f = ctk.CTkFrame(self._content, fg_color="transparent")
        f.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(f, text="⏳", font=ctk.CTkFont(size=48)).pack()
        ctk.CTkLabel(f, text=msg, font=ctk.CTkFont(size=20), text_color="gray").pack(pady=12)
        bar = ctk.CTkProgressBar(f, width=300, mode="indeterminate")
        bar.pack(pady=8)
        bar.start()

    def _render_error(self, msg):
        self._clear()
        f = ctk.CTkFrame(self._content, fg_color="transparent")
        f.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(f, text="⚠️", font=ctk.CTkFont(size=48)).pack()
        ctk.CTkLabel(f, text=msg, font=ctk.CTkFont(size=18),
                     text_color="#e05050", wraplength=600).pack(pady=12)
        ctk.CTkButton(f, text="← Back", command=self._go_back).pack(pady=16)
        self._render_footer("← Back = return | hold middle = back")
