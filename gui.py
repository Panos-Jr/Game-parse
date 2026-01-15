import customtkinter as ctk
from tkinter import filedialog
import io
import ctypes, os
import sys
import webbrowser
import re
import threading
import game_parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import messagebox

class GameSearchApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("🎮 Game-parse by Panos Jr - v1.1")
        self.geometry("800x700")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.create_widgets()

    def create_widgets(self):
        self.title_label = ctk.CTkLabel(self, text="🎮 Game Title:")
        self.title_label.pack(pady=(20, 0))
        self.title_entry = ctk.CTkEntry(self, width=500)
        self.title_entry.pack(pady=(5, 15))

        self.config_label = ctk.CTkLabel(self, text="📄 Config File:")
        self.config_label.pack()
        self.config_path_var = ctk.StringVar(value="sites.json")
        self.config_entry = ctk.CTkEntry(self, width=500, textvariable=self.config_path_var)
        self.config_entry.pack(pady=5)
        self.browse_button = ctk.CTkButton(self, text="Browse", command=self.browse_config)
        self.browse_button.pack(pady=(0, 15))

        self.thread_label = ctk.CTkLabel(self, text="⚙️ Max Threads:")
        self.thread_label.pack()
        self.thread_count_var = ctk.StringVar(value="5")
        self.thread_dropdown = ctk.CTkOptionMenu(self, values=[str(i) for i in range(1, 21)], variable=self.thread_count_var)
        self.thread_dropdown.pack(pady=(0, 20))

        self.search_button = ctk.CTkButton(
            self,
            text="Search",
            command=self.start_search_thread
        )
        self.search_button.pack(pady=10)

        self.info_label = ctk.CTkLabel(self, text="Note: A Chrome window may open whilst parsing, don't panic!")
        self.info_label.pack(pady=(20, 0))


        self.output_box = ctk.CTkTextbox(self, width=750, height=350, wrap="word", font=("Consolas", 12))
        self.output_box.pack(pady=(20, 10))
        self.output_box.bind("<Button-1>", self.open_link)

        self.error_label = ctk.CTkLabel(self, text="🛠 Error Log:")
        self.error_label.pack()
        self.error_log = ctk.CTkTextbox(self, width=750, height=100, wrap="word", font=("Consolas", 10))
        self.error_log.pack(pady=(5, 20))

    def start_search_thread(self):
        thread = threading.Thread(target=self.run_search, daemon=True)
        thread.start()

    def browse_config(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if path:
            self.config_path_var.set(path)

    def check_for_admin(self):
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False

        if not is_admin:
            print("Not running as admin")

            messagebox.showwarning(
                "Admin privileges",
                "This program needs to be run as administrator. Relaunching now..."
            )

            # Relaunch with admin rights (UAC prompt will appear)
            try:
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv), None, 1
                )
            except Exception as e:
                messagebox.showerror("Error", f"Failed to relaunch as admin:\n{e}")
            sys.exit(0)

        else:
            print("Running as admin")
            

    def run_search(self):
        self.after(0, lambda: self.output_box.delete("1.0", "end"))
        self.after(0, lambda: self.error_log.delete("1.0", "end"))

        title = self.title_entry.get()
        config = self.config_path_var.get()
        try:
            max_threads = int(self.thread_count_var.get())
        except ValueError:
            max_threads = 5

        if not title:
            self.after(0, lambda: self.output_box.insert("end", "⚠️ Please enter a game title.\n"))
            return

        self.after(0, lambda: self.output_box.insert("end", f"Looking for {title}\n"))

        from game_parse import search_site, load_sites

        try:
            sites = load_sites(config)
        except Exception as e:
            self.after(0, lambda: self.error_log.insert("end", f"Failed to load config, {e}\n"))
            return

        results = {}

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_site = {executor.submit(search_site, site, title): site for site in sites}
            for future in as_completed(future_to_site):
                site = future_to_site[future]
                try:
                    name, links = future.result()
                except Exception as e:
                    print(e)
                    name = site['name']
                    self.error_log.insert("end", f"Error: {e}\n")
                    links = None
                results[name] = links

        self.after(0, lambda: self.display_results(title, results))

        old_stdout = sys.stdout
        sys.stdout = mystdout = io.StringIO()

        sys.stdout = old_stdout
        self.output_box.insert("end", mystdout.getvalue())

    def display_results(self, title, results):
        self.output_box.insert("end", f"\n📊 Results for '{title}'\n{'=' * 50}\n\n")
        for site, links in results.items():
            self.output_box.insert("end", f"🌐 {site}:\n")
            if not links:
                self.output_box.insert("end", "  ❌ No matches found.\n\n")
            else:
                for link in links:
                    self.output_box.insert("end", f"  🔗 {link}\n")
                self.output_box.insert("end", "\n")

    def open_link(self, event):
        content = self.output_box.get("1.0", "end")
        index = self.output_box.index(f"@{event.x},{event.y}")
        line = self.output_box.get(index + " linestart", index + " lineend")

        url_match = re.search(r"(https?://\S+)", line)
        if url_match:
            webbrowser.open(url_match.group(1))

if __name__ == "__main__":
    app = GameSearchApp()
    app.check_for_admin()
    app.mainloop()

