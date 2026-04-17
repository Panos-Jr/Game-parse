import ctypes
import re
import sys
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import filedialog, messagebox

import customtkinter as ctk

import game_parse

class GameSearchApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("🎮 Game-parse by Panos Jr - v1.3")
        self.geometry("800x720")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self._build_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── widget layout ─────────────────────────────────────────────────────────

    def _build_widgets(self):
        ctk.CTkLabel(self, text="🎮 Game Title:").pack(pady=(20, 0))
        self.title_entry = ctk.CTkEntry(self, width=500)
        self.title_entry.pack(pady=(5, 15))
        self.title_entry.bind("<Return>", lambda _: self._start_search())

        ctk.CTkLabel(self, text="📄 Config File:").pack()
        self.config_path_var = ctk.StringVar(value="sites.json")
        ctk.CTkEntry(self, width=500, textvariable=self.config_path_var).pack(pady=5)
        ctk.CTkButton(self, text="Browse", command=self._browse_config).pack(pady=(0, 15))

        self.search_button = ctk.CTkButton(self, text="Search", command=self._start_search)
        self.search_button.pack(pady=10)

        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.pack(pady=(4, 0))

        ctk.CTkLabel(
            self, text="Note: A Chrome window may open whilst parsing — don't panic!"
        ).pack(pady=(8, 0))

        self.output_box = ctk.CTkTextbox(
            self, width=750, height=320, wrap="word", font=("Consolas", 12)
        )
        self.output_box.pack(pady=(20, 10))
        self.output_box.bind("<Button-1>", self._open_link)

        ctk.CTkLabel(self, text="🛠 Error Log:").pack()
        self.error_log = ctk.CTkTextbox(
            self, width=750, height=100, wrap="word", font=("Consolas", 10)
        )
        self.error_log.pack(pady=(5, 20))

    def _ui(self, fn):
        self.after(0, fn)

    def _append_output(self, text: str):
        self._ui(lambda: self.output_box.insert("end", text))

    def _append_error(self, text: str):
        self._ui(lambda: self.error_log.insert("end", text))

    def _set_status(self, text: str):
        self._ui(lambda: self.status_label.configure(text=text))

    def _set_busy(self, busy: bool):
        label = "Searching…" if busy else "Search"
        state = "disabled"  if busy else "normal"
        self._ui(lambda: self.search_button.configure(text=label, state=state))

    def _browse_config(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if path:
            self.config_path_var.set(path)

    def _start_search(self):
        threading.Thread(target=self._run_search, daemon=True).start()

    def _run_search(self):
        self._ui(lambda: self.output_box.delete("1.0", "end"))
        self._ui(lambda: self.error_log.delete("1.0", "end"))
        self._set_busy(True)
        self._set_status("")

        title  = self.title_entry.get().strip()
        config = self.config_path_var.get().strip()

        

        if not title:
            self._append_output("⚠️  Please enter a game title.\n")
            self._set_busy(False)
            return

        try:
            sites = game_parse.load_sites(config)
        except Exception as e:
            self._append_error(f"Failed to load config: {e}\n")
            self._set_busy(False)
            return

        max_threads = len(sites)
        total       = len(sites)

        self._append_output(
            f"🔍 Searching for '{title}' across {total} site(s) "
            f"with {max_threads} threads…\n\n"
        )

        completed = 0

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_site = {
                executor.submit(game_parse.search_site, site, title): site
                for site in sites
            }
            for future in as_completed(future_to_site):
                site = future_to_site[future]
                completed += 1
                self._set_status(f"⏳ {completed}/{total} sites done…")

                try:
                    name, links = future.result()
                    self._ui(lambda n=name, l=links: self._display_one(n, l))
                except Exception as e:
                    name = site.get('name', '?')
                    self._append_error(f"[{name}] {e}\n")
                    self._ui(lambda n=name: self._display_one(n, None))

        self._set_status(f"✅ Done — {total} site(s) searched.")
        self._set_busy(False)

    def _display_one(self, site_name: str, links: list[str] | None):
        """Write a single site's results to the output box immediately."""
        self.output_box.insert("end", f"🌐 {site_name}:\n")
        if not links:
            self.output_box.insert("end", "  ❌ No matches found.\n\n")
        else:
            for link in links:
                self.output_box.insert("end", f"  🔗 {link}\n")
            self.output_box.insert("end", "\n")

    def _open_link(self, event):
        index = self.output_box.index(f"@{event.x},{event.y}")
        line  = self.output_box.get(f"{index} linestart", f"{index} lineend")
        m     = re.search(r"(https?://\S+)", line)
        if m:
            webbrowser.open(m.group(1))

    def _on_close(self):
        game_parse.close_selenium_driver()
        self.destroy()

if __name__ == "__main__":
    app = GameSearchApp()
    app.mainloop()