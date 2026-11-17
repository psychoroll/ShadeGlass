import tkinter as tk
import customtkinter as ctk
import sqlite3
import json
import os
import threading
import queue
import webbrowser  # Added to support web routing links safely
import re
import requests    # Added for fallback backend validation references
from urllib.parse import urlparse
from requests.auth import HTTPBasicAuth

# Import pipeline components
from engine import audit_url, load_api_keys, CONFIG_FILE
from database import save_new_audit, initialize_database
from report import build_report_html, site_name as report_site_name
import insights
import theme as T
import tkinter.font as tkfont
import tkinter.messagebox

ctk.set_appearance_mode("Dark")

# Sidebar label -> insights section key
PANELS = [
    ("Overview", "overview"),
    ("On-Page SEO", "onpage"),
    ("Performance", "performance"),
    ("Links & Backlinks", "links"),
    ("Authority & Trust", "authority"),
]


class MarketingApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        initialize_database()

        # --- Window Settings ---
        self.title("ShadeGlass")
        self.geometry("1180x760")
        self.minsize(900, 600)
        self.configure(fg_color=T.DEAD_AIR)

        # Brand fonts if installed, otherwise the closest system fonts
        families = tkfont.families(self)
        self.font_display = T.pick_font(T.DISPLAY_FONTS, families)
        self.font_body = T.pick_font(T.BODY_FONTS, families)
        self.font_mono = T.pick_font(T.MONO_FONTS, families)

        # --- Tab State & Custom Workspace Memory ---
        self.active_tabs = {}       # Per-project widgets and report data
        self.tab_buttons = {}       # Tab bar widgets, for restyling on focus and rename
        self.current_visible_tab = None

        # Worker threads hand finished audits back to the Tk thread through this queue
        self._ui_queue = queue.Queue()
        self.after(100, self._poll_ui_queue)

        # --- 1. Global Top Menus ---
        self.setup_top_menus()

        # --- 2. Tab bar: brand mark, tabs, then a "+" right after the last tab ---
        self.top_tab_bar_frame = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=T.DEAD_AIR_DEEP)
        self.top_tab_bar_frame.pack(fill="x", side="top")

        brand = ctk.CTkLabel(self.top_tab_bar_frame, text="shade(glass)", text_color=T.SNOW,
                             font=ctk.CTkFont(family=self.font_display, size=15, weight="bold"))
        brand.pack(side="left", padx=(18, 14), pady=12)

        self.tabs_container = ctk.CTkFrame(self.top_tab_bar_frame, fg_color="transparent")
        self.tabs_container.pack(side="left", fill="both", expand=True, pady=10)

        self.add_tab_btn = ctk.CTkButton(
            self.tabs_container, text="+", width=34, height=32, corner_radius=10,
            fg_color="transparent", hover_color=T.NOISE, border_width=1, border_color=T.LINE_STRONG,
            text_color=T.GLITCH, font=ctk.CTkFont(family=self.font_body, size=18, weight="bold"),
            command=self.prompt_new_tab)
        self.add_tab_btn.pack(side="left", padx=(4, 0))

        tagline = ctk.CTkLabel(self.top_tab_bar_frame, text="REQLESS ( DESIGN ) CO.", text_color=T.FAINT,
                               font=ctk.CTkFont(family=self.font_mono, size=10))
        tagline.pack(side="right", padx=18)

        # --- 3. Master Area for Main Dashboard Content Panels ---
        self.main_workspace_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_workspace_container.pack(fill="both", expand=True, padx=14, pady=14)

        self.add_new_project_tab("New project")

    def setup_top_menus(self):
        menu_bar = tk.Menu(self)
        
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="New Project Workspace", command=self.prompt_new_tab)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)

        settings_menu = tk.Menu(menu_bar, tearoff=0)
        # Pointed directly to open_settings_popup to match the new window configuration
        settings_menu.add_command(label="Configure API Hooks", command=self.open_settings_popup)
        menu_bar.add_cascade(label="Settings", menu=settings_menu)
        
        self.config(menu=menu_bar)

    def add_new_project_tab(self, tab_title):
        """Builds one project workspace (sidebar, URL bar, results) and its tab."""
        if tab_title in self.active_tabs:
            self.focus_project_tab(tab_title)
            return

        tab_frame = ctk.CTkFrame(self.main_workspace_container, fg_color="transparent")

        # --- Sidebar ---
        sidebar_frame = ctk.CTkFrame(tab_frame, width=190, corner_radius=20, fg_color=T.NOISE)
        sidebar_frame.pack(side="left", fill="y", padx=(0, 14))
        sidebar_frame.pack_propagate(False)

        ctk.CTkLabel(sidebar_frame, text="( ANALYTICS )", text_color=T.GLITCH,
                     font=ctk.CTkFont(family=self.font_mono, size=11)).pack(anchor="w", padx=20, pady=(22, 12))

        sidebar_btns = {}
        for name, _key in PANELS:
            btn = ctk.CTkButton(
                sidebar_frame, text=name, anchor="w", height=36, corner_radius=10,
                fg_color="transparent", hover_color=T.NOISE_HOVER, text_color=T.MUTED,
                font=ctk.CTkFont(family=self.font_body, size=13),
                command=lambda m=name, t=tab_title: self.switch_view_panel(t, m))
            btn.pack(fill="x", padx=10, pady=2)
            sidebar_btns[name] = btn

        ctk.CTkLabel(sidebar_frame, text="time to get reqless", text_color=T.FAINT,
                     font=ctk.CTkFont(family=self.font_mono, size=10)).pack(side="bottom", anchor="w", padx=20, pady=18)

        # --- Content area ---
        content_workspace = ctk.CTkFrame(tab_frame, corner_radius=20, fg_color=T.NOISE)
        content_workspace.pack(side="right", fill="both", expand=True)

        header_controls = ctk.CTkFrame(content_workspace, fg_color="transparent")
        header_controls.pack(fill="x", padx=18, pady=(18, 10))

        url_input = ctk.CTkEntry(
            header_controls, height=42, corner_radius=12, border_width=1,
            fg_color=T.DEAD_AIR, border_color=T.LINE_STRONG, text_color=T.SNOW,
            placeholder_text="Paste a client or competitor URL…", placeholder_text_color=T.FAINT,
            font=ctk.CTkFont(family=self.font_body, size=14))
        url_input.pack(side="left", fill="x", expand=True, padx=(0, 10))
        url_input.bind("<Return>", lambda event, t=tab_title: self.trigger_live_audit(t))

        run_btn = ctk.CTkButton(
            header_controls, text="run audit →", width=130, height=42, corner_radius=12,
            fg_color=T.GLITCH, hover_color=T.GLITCH_HOVER, text_color=T.SNOW,
            text_color_disabled=T.MUTED,
            font=ctk.CTkFont(family=self.font_body, size=14, weight="bold"),
            command=lambda t=tab_title: self.trigger_live_audit(t))
        run_btn.pack(side="left", padx=(0, 8))

        export_btn = ctk.CTkButton(
            header_controls, text="export report ↗", width=150, height=42, corner_radius=12,
            fg_color="transparent", hover_color=T.NOISE_HOVER, border_width=1, border_color=T.CARRIER,
            text_color=T.SNOW, font=ctk.CTkFont(family=self.font_body, size=14),
            command=lambda t=tab_title: self.trigger_report_export(t))
        export_btn.pack(side="left")

        display_output = ctk.CTkTextbox(
            content_workspace, corner_radius=14, fg_color=T.DEAD_AIR, text_color=T.SNOW,
            border_width=0, wrap="word", activate_scrollbars=True,
            scrollbar_button_color=T.LINE_STRONG, scrollbar_button_hover_color=T.FAINT,
            font=ctk.CTkFont(family=self.font_body, size=13))
        display_output.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self._configure_text_tags(display_output)

        self.active_tabs[tab_title] = {
            "master_frame": tab_frame,
            "url_input": url_input,
            "display": display_output,
            "last_report_data": None,
            "current_panel": "Overview",
            "run_btn": run_btn,
            "export_btn": export_btn,
            "sidebar_btns": sidebar_btns,
        }

        self.render_tab_button_widget(tab_title)
        self.focus_project_tab(tab_title)
        self.switch_view_panel(tab_title, "Overview")

    def render_tab_button_widget(self, tab_title):
        """One tab: a rounded chip holding the name and, inside it, a small rename pencil."""
        widget_wrapper = ctk.CTkFrame(self.tabs_container, corner_radius=10, fg_color=T.NOISE,
                                      border_width=1, border_color=T.LINE_STRONG)
        widget_wrapper.pack(side="left", padx=(0, 6), before=self.add_tab_btn)

        text_clicker = ctk.CTkButton(
            widget_wrapper, text=tab_title, height=28, width=40, corner_radius=8,
            fg_color=T.NOISE, hover_color=T.NOISE_HOVER, text_color=T.MUTED,
            font=ctk.CTkFont(family=self.font_body, size=13),
            command=lambda t=tab_title: self.focus_project_tab(t))
        text_clicker.pack(side="left", padx=(3, 0), pady=2)

        pencil_modifier = ctk.CTkButton(
            widget_wrapper, text="✎", width=24, height=28, corner_radius=8,
            fg_color=T.NOISE, hover_color=T.NOISE_HOVER, text_color=T.FAINT,
            font=ctk.CTkFont(family=self.font_body, size=13),
            command=lambda t=tab_title: self.prompt_rename_tab(t))
        pencil_modifier.pack(side="left", padx=(0, 3), pady=2)

        self.tab_buttons[tab_title] = {
            "wrapper": widget_wrapper,
            "clicker": text_clicker,
            "editor": pencil_modifier,
        }

    def focus_project_tab(self, tab_title):
        """Shows the chosen project's workspace and highlights its tab."""
        if self.current_visible_tab == tab_title:
            return

        if self.current_visible_tab and self.current_visible_tab in self.active_tabs:
            self.active_tabs[self.current_visible_tab]["master_frame"].pack_forget()
            self._style_tab(self.current_visible_tab, active=False)

        self.current_visible_tab = tab_title
        self.active_tabs[tab_title]["master_frame"].pack(fill="both", expand=True)
        self._style_tab(tab_title, active=True)

    def prompt_rename_tab(self, old_title):
        """Asks for a new tab name."""
        new_title = self._input_dialog(f"Rename '{old_title}' to:", "Rename project")

        if not new_title or new_title.strip() == "" or new_title.strip() == old_title:
            return

        new_title = new_title.strip()

        if new_title in self.active_tabs:
            tk.messagebox.showwarning("Name already in use", f"A project called '{new_title}' is already open.")
            return

        self.rename_tab(old_title, new_title)

    def rename_tab(self, old_title, new_title):
        """Renames a tab and re-points every callback at the new name. Caller ensures new_title is free."""
        # 1. Pivot Data Reference Maps
        self.active_tabs[new_title] = self.active_tabs.pop(old_title)
        self.tab_buttons[new_title] = self.tab_buttons.pop(old_title)

        # 2. Re-wire Dynamic Callback Logic Inside UI Elements
        button_refs = self.tab_buttons[new_title]
        button_refs["clicker"].configure(text=new_title, command=lambda t=new_title: self.focus_project_tab(t))
        button_refs["editor"].configure(command=lambda t=new_title: self.prompt_rename_tab(t))
        
        # 3. Update Title String Labels for the Context Panels Loop
        tab_data = self.active_tabs[new_title]
        
        # Rewire URL Input
        url_input = tab_data["url_input"]
        url_input.unbind("<Return>")
        url_input.bind("<Return>", lambda event, t=new_title: self.trigger_live_audit(t))
        
        # Rewire Core Action Buttons
        tab_data["run_btn"].configure(command=lambda t=new_title: self.trigger_live_audit(t))
        tab_data["export_btn"].configure(command=lambda t=new_title: self.trigger_report_export(t))
        
        # Rewire Sidebar Navigation Buttons
        for mod, btn in tab_data["sidebar_btns"].items():
            btn.configure(command=lambda m=mod, t=new_title: self.switch_view_panel(t, m))
        
        # If renamed tab was current, sync global visible key values
        if self.current_visible_tab == old_title:
            self.current_visible_tab = new_title

        print(f"Successfully pivoted track context mapping elements from '{old_title}' into '{new_title}'.")

    @staticmethod
    def domain_from_url(url):
        """'https://www.Website.com:443/page' -> 'website.com'"""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        host = (urlparse(url).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host

    def _unique_tab_name(self, wanted, tab_data):
        """Returns wanted, or 'wanted (2)', 'wanted (3)'... if another tab already uses it."""
        name, n = wanted, 2
        while name in self.active_tabs and self.active_tabs[name] is not tab_data:
            name = f"{wanted} ({n})"
            n += 1
        return name

    def _tab_name_for(self, tab_data):
        """Returns the current name of a tab, which may have changed via rename."""
        for name, data in self.active_tabs.items():
            if data is tab_data:
                return name
        return None

    def trigger_live_audit(self, project_name):
        # Runs on the Tk main thread: read widgets here, never from the worker.
        tab_data = self.active_tabs[project_name]
        if tab_data.get("audit_running"):
            return

        target_url = tab_data["url_input"].get().strip()

        if not target_url:
            self.show_message(tab_data, "no address yet", "Paste a website address into the box above, then press run audit.", "warn")
            return

        # The first successful check renames the tab to the site's domain (e.g. "website.com"),
        # so save that first audit under the domain name too.
        if not tab_data.get("first_check_done"):
            domain = self.domain_from_url(target_url)
            if domain:
                project_name = self._unique_tab_name(domain, tab_data)

        tab_data["audit_running"] = True
        tab_data["run_btn"].configure(state="disabled")
        self.show_message(tab_data, "auditing", f"Reading {target_url} and asking Google PageSpeed, OpenPageRank and DataForSEO about it. "
                          "Mobile speed tests can take up to a minute.", animate_dots=True)

        tab_data["pending_name"] = project_name
        worker_thread = threading.Thread(target=self._async_audit_worker, args=(tab_data, project_name, target_url))
        worker_thread.daemon = True
        worker_thread.start()

    def _async_audit_worker(self, tab_data, project_name, target_url):
        """Network work only. All widget updates are handed back to the main thread via after()."""
        try:
            report = audit_url(target_url)
            if "error" not in report:
                clean_domain = self.domain_from_url(target_url)
                report["open_pagerank"] = self.fetch_open_pagerank(clean_domain)
                report["dataforseo"] = self.fetch_dataforseo(clean_domain)
                save_new_audit(project_name, target_url, report)
        except Exception as e:
            report = {"error": f"Unexpected error during audit: {e}"}

        # Tk calls (including after()) are not safe from this thread; the main
        # thread picks results up from this queue in _poll_ui_queue.
        self._ui_queue.put((tab_data, report))

    def _poll_ui_queue(self):
        try:
            while True:
                tab_data, report = self._ui_queue.get_nowait()
                try:
                    self._finish_audit(tab_data, report)
                except Exception as e:
                    # Never let one bad result stop the polling loop, or later audits would hang.
                    tab_data["audit_running"] = False
                    tab_data["run_btn"].configure(state="normal")
                    self.show_message(tab_data, "couldn't show results", str(e), "poor")
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_ui_queue)

    def _finish_audit(self, tab_data, report):
        tab_data["audit_running"] = False
        tab_data["run_btn"].configure(state="normal")

        if "error" in report:
            self.show_message(tab_data, "couldn't reach the site", report["error"], "poor")
            return

        tab_data["last_report_data"] = report
        current_name = self._tab_name_for(tab_data)

        if not tab_data.get("first_check_done"):
            tab_data["first_check_done"] = True
            # Re-check for clashes: another tab may have taken the name while this audit ran.
            new_name = self._unique_tab_name(tab_data.get("pending_name") or current_name, tab_data)
            if current_name and new_name != current_name:
                self.rename_tab(current_name, new_name)
                current_name = new_name
        if current_name:
            self.switch_view_panel(current_name, tab_data["current_panel"])


    def switch_view_panel(self, project_name, selected_panel):
        tab_memory = self.active_tabs.get(project_name, {})
        display_box = tab_memory.get("display")
        report = tab_memory.get("last_report_data")
        tab_memory["current_panel"] = selected_panel

        # Highlight the active sidebar item
        for name, btn in tab_memory.get("sidebar_btns", {}).items():
            active = name == selected_panel
            btn.configure(fg_color=T.GLITCH_TINT if active else "transparent",
                          text_color=T.SNOW if active else T.MUTED)

        if tab_memory.get("audit_running"):
            return  # keep the "auditing..." message up until results arrive

        if not report:
            self.show_message(tab_memory, "ready when you are",
                              "Paste a website address above and press run audit. "
                              "Results appear here, and export report builds the client-ready version.")
            return

        display_box.configure(state="normal")
        display_box.delete("0.0", "end")
        key = dict(PANELS)[selected_panel]
        if key == "overview":
            self._write_overview(display_box, report)
        else:
            section = next(s for s in insights.build_sections(report) if s["key"] == key)
            self._write_section(display_box, section)
        display_box.configure(state="disabled")
        display_box.yview_moveto(0)

    # ------------------------------------------------------------------ settings

    def _style_tab(self, tab_title, active):
        refs = self.tab_buttons.get(tab_title)
        if not refs:
            return
        refs["wrapper"].configure(border_color=T.GLITCH if active else T.LINE_STRONG)
        refs["clicker"].configure(text_color=T.SNOW if active else T.MUTED)
        refs["editor"].configure(text_color=T.GLITCH if active else T.FAINT)

    def _input_dialog(self, text, title):
        dialog = ctk.CTkInputDialog(
            text=text, title=title, fg_color=T.DEAD_AIR, text_color=T.SNOW,
            button_fg_color=T.GLITCH, button_hover_color=T.GLITCH_HOVER, button_text_color=T.SNOW,
            entry_fg_color=T.NOISE, entry_border_color=T.LINE_STRONG, entry_text_color=T.SNOW,
            font=ctk.CTkFont(family=self.font_body, size=13))
        return dialog.get_input()

    def _configure_text_tags(self, box):
        """Colour and type styles for the results panel (fonts go on the inner Text widget)."""
        text = box._textbox
        text.configure(spacing1=2, spacing3=2, padx=20, pady=16, insertbackground=T.SNOW,
                       selectbackground=T.CARRIER)
        text.tag_configure("site", font=(self.font_display, 30, "bold"), foreground=T.SNOW, spacing3=4)
        text.tag_configure("h1", font=(self.font_display, 18, "bold"), foreground=T.SNOW, spacing1=6, spacing3=2)
        text.tag_configure("h2", font=(self.font_mono, 10, "bold"), foreground=T.MUTED, spacing1=14, spacing3=6)
        text.tag_configure("kicker", font=(self.font_mono, 10), foreground=T.GLITCH, spacing1=4)
        text.tag_configure("label", font=(self.font_body, 13, "bold"), foreground=T.SNOW, spacing1=10)
        text.tag_configure("value", font=(self.font_mono, 12, "bold"), foreground=T.SNOW)
        text.tag_configure("body", font=(self.font_body, 12), foreground=T.SNOW, lmargin1=18, lmargin2=18)
        text.tag_configure("muted", font=(self.font_body, 12), foreground=T.MUTED, lmargin1=18, lmargin2=18)
        text.tag_configure("guide", font=(self.font_mono, 10), foreground=T.FAINT, lmargin1=18, lmargin2=18)
        text.tag_configure("intro", font=(self.font_body, 12), foreground=T.MUTED, spacing3=8)
        text.tag_configure("list", font=(self.font_mono, 11), foreground=T.SNOW, lmargin1=18, lmargin2=34)
        for level, color in T.LEVEL_COLORS.items():
            text.tag_configure(f"lvl-{level}", font=(self.font_mono, 10, "bold"), foreground=color)
            text.tag_configure(f"big-{level}", font=(self.font_display, 20, "bold"), foreground=color)

    def _write(self, box, *parts):
        """parts: (text, tag) pairs; plain strings are written untagged."""
        for part in parts:
            if isinstance(part, tuple):
                box._textbox.insert("end", part[0], part[1])
            else:
                box._textbox.insert("end", part)

    def show_message(self, tab_data, title, body, level="info", animate_dots=False):
        box = tab_data["display"]
        box.configure(state="normal")
        box.delete("0.0", "end")
        self._write(box, ("( SHADEGLASS )\n", "kicker"), (title, "h1"))
        if animate_dots:
            # Three dots that always take up space; _animate_dots shows or hides each one by colour
            self._write(box, (".", ("h1", "dot0")), (".", ("h1", "dot1")), (".", ("h1", "dot2")))
        self._write(box, ("\n", "h1"), (body + "\n", "intro" if level == "info" else f"lvl-{level}"))
        box.configure(state="disabled")
        if animate_dots:
            self._animate_dots(tab_data, 0)

    def _animate_dots(self, tab_data, frame):
        """While an audit runs, shows 0, 1, 2, then 3 dots in order, then starts again."""
        job = tab_data.pop("dots_job", None)
        if job:
            self.after_cancel(job)
        if not tab_data.get("audit_running"):
            return
        text = tab_data["display"]._textbox
        visible = frame % 4
        for i in range(3):
            text.tag_configure(f"dot{i}", foreground=T.SNOW if i < visible else T.DEAD_AIR)
        tab_data["dots_job"] = self.after(350, self._animate_dots, tab_data, frame + 1)

    def _append_note(self, tab_data, text, level="info"):
        """Adds a one-line status note to the bottom of the results panel."""
        box = tab_data["display"]
        box.configure(state="normal")
        self._write(box, "\n", (f"● {text}\n", f"lvl-{level}"))
        box.configure(state="disabled")
        box.see("end")

    def _write_item(self, box, it):
        level = it["level"]
        self._write(box, (it["label"], "label"), ("   " + str(it["value"]) + "\n", "value"))
        self._write(box, (f"● {insights.LEVEL_LABELS[level].upper()}", f"lvl-{level}"))
        if it.get("verdict"):
            self._write(box, ("  " + it["verdict"], "body"))
        self._write(box, "\n")
        if it.get("guide"):
            self._write(box, (it["guide"] + "\n", "guide"))
        if it.get("why"):
            self._write(box, (it["why"] + "\n", "muted"))

    def _write_section(self, box, section):
        self._write(box, (f"( {section['kicker'].upper()} )\n", "kicker"), (section["title"].lower() + "\n", "h1"),
                    (section["intro"] + "\n", "intro"))
        for it in section["items"]:
            self._write_item(box, it)
        for group in section["groups"]:
            if not group["items"] and not group.get("note"):
                continue
            self._write(box, (group["title"].upper() + "\n", "h2"))
            if group.get("note"):
                self._write(box, (group["note"] + "\n", "muted"))
            for it in group["items"]:
                self._write_item(box, it)
        if section.get("list"):
            self._write(box, (section["list_title"].upper() + "\n", "h2"), (section["list_note"] + "\n", "muted"))
            for entry in section["list"]:
                self._write(box, ("→ " + entry + "\n", "list"))
        if section.get("status") and section["status"] != "Successfully retrieved cloud metrics.":
            self._write(box, ("\n" + section["status"] + "\n", "guide"))

    def _write_overview(self, box, report):
        sections = insights.build_sections(report)
        summary = insights.summary(report, sections)
        counts = summary["counts"]
        name = report_site_name(report.get("target_url", ""))

        self._write(box, ("// SITE AUDIT FOR\n", "kicker"), (name + "\n", "site"),
                    (report.get("target_url", "") + "\n", "guide"), "\n")
        self._write(box, (f"● {counts['good']} GOOD", "lvl-good"), "     ",
                    (f"● {counts['warn']} NEED WORK", "lvl-warn"), "     ",
                    (f"● {counts['poor']} POOR", "lvl-poor"), "\n")

        for tile in summary["tiles"]:
            self._write(box, (tile["label"].upper() + "\n", "h2"),
                        (str(tile["value"]), f"big-{tile['level']}"),
                        ("   " + insights.LEVEL_LABELS[tile["level"]].upper() + "\n", f"lvl-{tile['level']}"))

        self._write(box, ("\n( PRIORITIES )\n", "kicker"), ("fix these first\n", "h1"))
        if not summary["priorities"]:
            self._write(box, ("Every graded check passed.\n", "intro"))
        for it in summary["priorities"]:
            self._write(box, (f"● {insights.LEVEL_LABELS[it['level']].upper()}  ", f"lvl-{it['level']}"),
                        (it["label"], "label"), ("   " + str(it["value"]) + "\n", "value"),
                        (it["verdict"] + "\n", "muted"))
        self._write(box, ("\nUse the sidebar for the full detail on each area, or export the client report.\n", "guide"))

    def trigger_report_export(self, project_name):
        tab_data = self.active_tabs.get(project_name, {})
        report_data = tab_data.get("last_report_data")

        if not report_data:
            self._append_note(tab_data, "Nothing to export yet. Run an audit first.", "warn")
            return

        # Keep only characters that are safe in a filename on every OS
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", project_name).strip("_") or "report"
        filename = f"{safe_name}_Full_SEO_Report.html"
        html_content = build_report_html(project_name, report_data)

        try:
            import os
            import sys
            import urllib.request
            import webbrowser

            # --- 1. Find the exact directory where ShadeGlass is running ---
            if getattr(sys, 'frozen', False):
                # If running as a compiled Windows .exe or Mac .app
                app_dir = os.path.dirname(sys.executable)
                # Mac .app bundle correction (moves out of the hidden internal folder)
                if app_dir.endswith("MacOS"):
                    app_dir = os.path.dirname(os.path.dirname(os.path.dirname(app_dir)))
            else:
                # If running normally via python script
                app_dir = os.path.dirname(os.path.abspath(__file__))

            # --- 2. Build the absolute file path ---
            absolute_file_path = os.path.join(app_dir, filename)

            # --- 3. Write the file safely to that exact location ---
            with open(absolute_file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            # --- 4. Cross-Platform Browser Formatting ---
            # This translates the C:\ (Windows) or /Users/ (Mac) path into a safe browser URL
            file_url = "file:" + urllib.request.pathname2url(absolute_file_path)
            
            # --- 5. Open in default browser ---
            webbrowser.open(file_url)
            
            self._append_note(tab_data, f"Report exported and opened in your browser: {absolute_file_path}", "good")
        except Exception as e:
            self._append_note(tab_data, f"Export failed: {e}", "poor")
    
    def prompt_new_tab(self):
        name = self._input_dialog("Name the new project (it switches to the site's domain after the first audit):", "New project")
        if name and name.strip():
            self.add_new_project_tab(self._unique_tab_name(name.strip(), None))

    # ------------------------------------------------------------------ results display

    def fetch_open_pagerank(self, domain, config_path="config.json"):
        """Fetches domain authority, referring domains and 12-month trend from OpenPageRank."""
        api_key = load_api_keys().get("open_pagerank_key", "").strip()
        if not api_key:
            return {"status": "skipped", "error": "No OpenPageRank API Key configured."}

        url = "https://openpagerank.keywordseverywhere.com/v1/domains/bulk"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"domains": [domain], "include_history": True}

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            try:
                data = response.json()
            except ValueError:
                data = {}

            if response.status_code != 200:
                error = data.get("error") if isinstance(data, dict) else None
                if isinstance(error, dict):
                    reason = error.get("message", "")
                    if error.get("type") == "address_error":
                        reason += " Free keys only work from the IP address set on your OpenPageRank account page."
                else:
                    reason = error or ""
                return {"status": "error", "error": f"HTTP {response.status_code}: {reason}".rstrip(": ")}

            results = data.get("results") or []
            if not results:
                return {"status": "error", "error": "Invalid API data format structure."}
            info = results[0]
            if not info.get("found"):
                return {"status": "not_found", "error": "Domain is not in OpenPageRank's index yet."}

            # Monthly history, oldest first. Keep the last 3 years and work out the 12-month change.
            history = sorted(info.get("history") or [], key=lambda h: h.get("date", ""))
            history = [{"date": h["date"], "score": h.get("open_page_rank")} for h in history if h.get("date")][-36:]
            trend = None
            if len(history) >= 2:
                latest = history[-1]
                year_ago_date = f"{int(latest['date'][:4]) - 1}{latest['date'][4:]}"
                earlier = [h for h in history if h["date"] <= year_ago_date] or history[:1]
                start = earlier[-1]
                if start["score"] is not None and latest["score"] is not None:
                    trend = {"from_date": start["date"], "from": start["score"],
                             "to_date": latest["date"], "to": latest["score"],
                             "change": round(latest["score"] - start["score"], 2)}

            return {
                "status": "success",
                "score": info.get("open_page_rank", "N/A"),          # 0-10, higher is better
                "rank": info.get("rank", "N/A"),                     # global position, lower is better
                "referring_domains": info.get("referring_domains", "N/A"),
                "as_of": data.get("as_of", ""),
                "trend": trend,
                "history": history,
            }
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": f"Connection failed: {type(e).__name__}"}

    def fetch_dataforseo(self, domain, config_path="config.json"):
        """Fetches domain rank, spam scores and the backlink profile from DataForSEO (paid per call)."""
        config = load_api_keys()
        api_login = config.get("dataforseo_login", "")
        api_password = config.get("dataforseo_password", "")

        if not api_login or not api_password:
            return {"status": "skipped", "error": "DataForSEO credentials missing."}

        url = "https://api.dataforseo.com/v3/backlinks/summary/live"
        payload = [{"target": domain}]

        try:
            response = requests.post(url, json=payload, auth=HTTPBasicAuth(api_login, api_password), timeout=30)
            data = response.json()

            if response.status_code == 200:
                tasks = data.get("tasks", [])
                if tasks and tasks[0].get("status_code") == 20000:
                    result = (tasks[0].get("result") or [{}])[0] or {}
                    return {
                        "status": "success",
                        "rank": result.get("rank", "N/A"),                        # 0-1000, higher is better
                        "backlinks_spam_score": result.get("backlinks_spam_score", "N/A"),
                        "target_spam_score": (result.get("info") or {}).get("target_spam_score", "N/A"),
                        "backlinks": result.get("backlinks", "N/A"),
                        "referring_domains": result.get("referring_domains", "N/A"),
                        "referring_main_domains": result.get("referring_main_domains", "N/A"),
                        "referring_domains_nofollow": result.get("referring_domains_nofollow", "N/A"),
                        "broken_backlinks": result.get("broken_backlinks", "N/A"),
                        "first_seen": (result.get("first_seen") or "")[:10],
                    }
                elif tasks:
                    return {
                        "status": "error",
                        "error": f"{tasks[0].get('status_message', 'Error')} (Code: {tasks[0].get('status_code')})"
                    }

            return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def open_settings_popup(self):
        """API key settings, styled to match the app."""
        win = ctk.CTkToplevel(self)
        win.title("API keys")
        win.geometry("520x660")
        win.configure(fg_color=T.DEAD_AIR)
        win.attributes("-topmost", True)

        def heading(text, link_text, url, top=18):
            ctk.CTkLabel(win, text=text, text_color=T.SNOW,
                         font=ctk.CTkFont(family=self.font_display, size=15, weight="bold")).pack(anchor="w", padx=40, pady=(top, 0))
            link = ctk.CTkLabel(win, text=link_text + " ↗", text_color=T.GLITCH, cursor="hand2",
                                font=ctk.CTkFont(family=self.font_mono, size=11))
            link.pack(anchor="w", padx=40, pady=(0, 6))
            link.bind("<Button-1>", lambda e: webbrowser.open_new_tab(url))

        def field(label, secret=True):
            ctk.CTkLabel(win, text=label.upper(), text_color=T.FAINT,
                         font=ctk.CTkFont(family=self.font_mono, size=10)).pack(anchor="w", padx=40)
            entry = ctk.CTkEntry(win, width=440, height=38, corner_radius=10, border_width=1,
                                 fg_color=T.NOISE, border_color=T.LINE_STRONG, text_color=T.SNOW,
                                 show="•" if secret else "", font=ctk.CTkFont(family=self.font_body, size=13))
            entry.pack(anchor="w", padx=40, pady=(2, 8))
            return entry

        ctk.CTkLabel(win, text="( SETTINGS )", text_color=T.GLITCH,
                     font=ctk.CTkFont(family=self.font_mono, size=11)).pack(anchor="w", padx=40, pady=(26, 0))
        ctk.CTkLabel(win, text="api keys", text_color=T.SNOW,
                     font=ctk.CTkFont(family=self.font_display, size=26, weight="bold")).pack(anchor="w", padx=40)

        heading("Google PageSpeed", "get a free key", "https://developers.google.com/speed/docs/insights/v5/get-started")
        google_entry = field("API key")
        heading("OpenPageRank", "get a free key (starts with opr_live_)", "https://keywordseverywhere.com/account/openpagerank")
        opr_entry = field("API key")
        heading("DataForSEO", "create an account (paid per lookup)", "https://dataforseo.com/")
        dfs_login_entry = field("API login", secret=False)
        dfs_pass_entry = field("API password")

        current_keys = load_api_keys()
        google_entry.insert(0, current_keys.get("google_pagespeed_key", ""))
        opr_entry.insert(0, current_keys.get("open_pagerank_key", ""))
        dfs_login_entry.insert(0, current_keys.get("dataforseo_login", ""))
        dfs_pass_entry.insert(0, current_keys.get("dataforseo_password", ""))

        def save_keys():
            payload = {
                "google_pagespeed_key": google_entry.get().strip(),
                "open_pagerank_key": opr_entry.get().strip(),
                "dataforseo_login": dfs_login_entry.get().strip(),
                "dataforseo_password": dfs_pass_entry.get().strip(),
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)
            win.destroy()

        ctk.CTkLabel(win, text="Keys are saved in config.json on this computer only.", text_color=T.FAINT,
                     font=ctk.CTkFont(family=self.font_body, size=11)).pack(anchor="w", padx=40, pady=(4, 0))
        ctk.CTkButton(win, text="save keys", width=440, height=42, corner_radius=12,
                      fg_color=T.GLITCH, hover_color=T.GLITCH_HOVER, text_color=T.SNOW,
                      font=ctk.CTkFont(family=self.font_body, size=14, weight="bold"),
                      command=save_keys).pack(anchor="w", padx=40, pady=(10, 20))

if __name__ == "__main__":
    app = MarketingApp()
    app.mainloop()