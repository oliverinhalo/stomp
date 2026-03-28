import customtkinter as ctk

KEY_ROWS = [
    ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
    ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
    ["Z", "X", "C", "V", "B", "N", "M", ",", ".", "/"],
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
    ["@", "#", "$", "%", "&", "-", "_", "+", "=", ";"],
    [" ", "←"],
]

CHARS = [ch for row in KEY_ROWS for ch in row]


class PedalKeyboard(ctk.CTkFrame):
    """
    Grid keyboard layout navigable by left/right/middle pedal.
    Also accepts normal keyboard typing with punctuation and symbols.
    on_confirm(text) called when user presses Enter or confirm button.
    """

    def __init__(self, parent, on_confirm, on_cancel=None, prompt="Enter text:", **kwargs):
        super().__init__(parent, **kwargs)

        self.on_confirm = on_confirm
        self.on_cancel  = on_cancel
        self.cursor     = 0
        self.text       = ""

        # Prompt
        ctk.CTkLabel(self, text=prompt, font=ctk.CTkFont(size=18)).pack(pady=(16, 4))

        # Text display
        self.text_var = ctk.StringVar(value="")
        self.text_display = ctk.CTkLabel(
            self, textvariable=self.text_var,
            font=ctk.CTkFont(size=22, weight="bold"),
            fg_color=("gray90", "gray20"),
            corner_radius=8, width=500, height=44
        )
        self.text_display.pack(pady=8, padx=20)

        # Character strip
        self.char_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.char_frame.pack(pady=8)

        self.char_labels = []
        index = 0
        for row_idx, row in enumerate(KEY_ROWS):
            for col_idx, ch in enumerate(row):
                display = "SPC" if ch == " " else ("DEL" if ch == "←" else ch)
                lbl = ctk.CTkLabel(
                    self.char_frame,
                    text=display,
                    font=ctk.CTkFont(size=15, weight="bold"),
                    width=42, height=42,
                    corner_radius=6,
                )
                lbl.grid(row=row_idx, column=col_idx, padx=2, pady=2)
                self.char_labels.append(lbl)
                index += 1

        # Confirm / cancel buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=12)

        ctk.CTkButton(btn_frame, text="✓ Confirm", width=140, height=40,
                      fg_color="green", hover_color="darkgreen",
                      command=self._confirm).grid(row=0, column=0, padx=10)

        if on_cancel:
            ctk.CTkButton(btn_frame, text="✕ Cancel", width=140, height=40,
                          fg_color="gray40", hover_color="gray30",
                          command=on_cancel).grid(row=0, column=1, padx=10)

        # Hint
        ctk.CTkLabel(self, text="◀ / ▶ move   |   middle = select   |   hold middle = submit   |   or just type",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=4)

        self._highlight()

    def _highlight(self):
        for i, lbl in enumerate(self.char_labels):
            if i == self.cursor:
                lbl.configure(fg_color=("dodgerblue", "#1e6fb5"), text_color="white")
            else:
                lbl.configure(fg_color=("gray85", "gray25"), text_color=("gray10", "gray90"))

    def pedal_left(self):
        self.cursor = (self.cursor - 1) % len(CHARS)
        self._highlight()

    def pedal_right(self):
        self.cursor = (self.cursor + 1) % len(CHARS)
        self._highlight()

    def pedal_select(self):
        ch = CHARS[self.cursor]
        if ch == "←":
            self.text = self.text[:-1]
        else:
            self.text += ch
        self.text_var.set(self.text)

    def type_char(self, ch):
        """Called from normal keyboard input."""
        if ch == "\x08":  # backspace
            self.text = self.text[:-1]
        elif ch in ("\r", "\n"):
            self._confirm()
            return
        elif len(ch) == 1 and ch.isprintable():
            self.text += ch.upper() if ch.isalpha() else ch
        self.text_var.set(self.text)

    def _confirm(self):
        if self.text.strip():
            self.on_confirm(self.text.strip())

    def get_text(self):
        return self.text
