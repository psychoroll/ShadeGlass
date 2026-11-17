import tkinter as tk
import customtkinter as ctk
import sqlite3
import json
import os
import threading
import queue
import webbrowser  # Added to support web routing links safely
import re
import html
import requests    # Added for fallback backend validation references
from urllib.parse import urlparse
from requests.auth import HTTPBasicAuth

# Import pipeline components
from engine import audit_url, load_api_keys, CONFIG_FILE
from database import save_new_audit, initialize_database

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def fmt_num(value):
    """1234567 -> '1,234,567'; anything that isn't a number is shown as-is."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, str) and value.isdigit():
        return f"{int(value):,}"
    return "N/A" if value is None else str(value)


def describe_trend(trend):
    """{'from': 0.22, 'to': 0.21, ...} -> 'down 0.01 (0.22 in 2025-10 → 0.21 in 2026-10)'"""
    if not trend:
        return "Not enough history yet"
    change = trend["change"]
    direction = "up" if change > 0 else "down" if change < 0 else "flat"
    return f"{direction} {abs(change):.2f} ({trend['from']} in {trend['from_date'][:7]} → {trend['to']} in {trend['to_date'][:7]})"

class MarketingApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        initialize_database()

        # --- Window Settings ---
        self.title("ShadeGlass")
        self.geometry("1100x700")
        self.minimum_size = (900, 600)

        # --- Tab State & Custom Workspace Memory ---
        self.active_tabs = {}       # Tracks individual project data payloads and frame elements [cite: 71]
        self.tab_buttons = {}       # Tracks references to top bar UI elements for clean state updates
        self.current_visible_tab = None

        # Worker threads hand finished audits back to the Tk thread through this queue
        self._ui_queue = queue.Queue()
        self.after(100, self._poll_ui_queue)

        # --- 1. Global Top Menus ---
        self.setup_top_menus()

        # --- 2. Custom Left-Aligned Tab Control Bar Framework ---
        # Master container for the tab navigation system across the top header row
        self.top_tab_bar_frame = ctk.CTkFrame(self, height=45, corner_radius=0, fg_color=("gray90", "gray10"))
        self.top_tab_bar_frame.pack(fill="x", side="top", padx=0, pady=0)

        # Container inside the top bar that packs buttons horizontally from the left
        self.tabs_container = ctk.CTkFrame(self.top_tab_bar_frame, fg_color="transparent")
        self.tabs_container.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Quick action button to launch new browser-like workspace blocks [cite: 622]
        self.add_tab_btn = ctk.CTkButton(self.top_tab_bar_frame, text="+ New Project", width=100, command=self.prompt_new_tab)
        self.add_tab_btn.pack(side="right", padx=10, pady=8)

        # --- 3. Master Area for Main Dashboard Content Panels ---
        self.main_workspace_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_workspace_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Deploy initial default client staging tab view [cite: 80]
        self.add_new_project_tab("Default Workspace")

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
        """Generates a comprehensive left-aligned tab button widget and isolated workspace panel frame."""
        if tab_title in self.active_tabs:
            self.focus_project_tab(tab_title)
            return

        # 1. Create a Hidden Workspace Frame for This Project
        tab_frame = ctk.CTkFrame(self.main_workspace_container, fg_color="transparent")
        
        # Sidebar Left Framework inside the project workspace
        sidebar_frame = ctk.CTkFrame(tab_frame, width=160, corner_radius=0)
        sidebar_frame.pack(side="left", fill="y", padx=5, pady=5)

        sidebar_title = ctk.CTkLabel(sidebar_frame, text="ANALYTICS", font=ctk.CTkFont(size=12, weight="bold"))
        sidebar_title.pack(padx=10, pady=15)

        # Core Metrics Sidebar - Track buttons in a local dictionary
        modules = ["Overview", "On-Page SEO", "Performance", "Backlinks & Tech", "Traffic Analytics"]
        sidebar_btns = {}  # <--- Added to track sidebar elements
        for mod in modules:
            btn = ctk.CTkButton(
                sidebar_frame, 
                text=mod, 
                fg_color="transparent", 
                text_color=("gray10", "gray90"), 
                hover_color=("gray70", "gray30"), 
                anchor="w",
                command=lambda m=mod, t=tab_title: self.switch_view_panel(t, m)
            )
            btn.pack(fill="x", padx=10, pady=2)
            sidebar_btns[mod] = btn  # <--- Store the reference

        # Content Output Window Right Frame
        content_workspace = ctk.CTkFrame(tab_frame, fg_color=("gray95", "gray15"))
        content_workspace.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        header_controls = ctk.CTkFrame(content_workspace, height=50)
        header_controls.pack(fill="x", padx=10, pady=10)

        url_input = ctk.CTkEntry(header_controls, placeholder_text="Enter competitor or client URL here...")
        url_input.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        url_input.bind("<Return>", lambda event, t=tab_title: self.trigger_live_audit(t))

        run_btn = ctk.CTkButton(header_controls, text="Run Audit", width=100, command=lambda t=tab_title: self.trigger_live_audit(t))
        run_btn.pack(side="left", padx=5, pady=10)

        export_btn = ctk.CTkButton(
            header_controls, 
            text="📤 Export", 
            width=90, 
            fg_color="#2b7a3e", 
            hover_color="#1e542b",
            command=lambda t=tab_title: self.trigger_report_export(t)
        )
        export_btn.pack(side="left", padx=5, pady=10)

        # Main Display Text Terminal Panel
        display_output = ctk.CTkTextbox(content_workspace, font=ctk.CTkFont(family="Consolas", size=12))
        display_output.pack(fill="both", expand=True, padx=10, pady=10)
        display_output.insert("0.0", f"Workspace ready for: {tab_title}\nEnter a target URL and hit 'Run Audit'.")

        # Cache layout memory pointers and tracking state objects
        self.active_tabs[tab_title] = {
            "master_frame": tab_frame,
            "url_input": url_input,
            "display": display_output,
            "last_report_data": None,
            "current_panel": "Overview",
            "run_btn": run_btn,             # <--- Added
            "export_btn": export_btn,       # <--- Added
            "sidebar_btns": sidebar_btns    # <--- Added
        }

        # 2. Build and Render the Left-Aligned Navigation Tab Widget Item
        self.render_tab_button_widget(tab_title)
        
        # Shift immediate screen visibility focus directly to this new instance
        self.focus_project_tab(tab_title)

    def render_tab_button_widget(self, tab_title):
        """Constructs an aligned horizontal frame container pairing a name link with a rename tool."""
        widget_wrapper = ctk.CTkFrame(self.tabs_container, fg_color="transparent")
        widget_wrapper.pack(side="left", padx=3, pady=4) # Left aligned stacking pipeline

        # Tab Selection Click Button Element
        text_clicker = ctk.CTkButton(
            widget_wrapper, 
            text=tab_title, 
            width=135, 
            height=28, 
            fg_color=("gray80", "gray25"), 
            text_color=("gray10", "gray90"),
            command=lambda t=tab_title: self.focus_project_tab(t)
        )
        text_clicker.pack(side="left")

        # Miniature Editing Pencil Icon Button ✏️ (Replaced old gear element)
        pencil_modifier = ctk.CTkButton(
            widget_wrapper, 
            text="✏️", 
            width=26, 
            height=28, 
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            text_color=("gray10", "gray90"),
            command=lambda t=tab_title: self.prompt_rename_tab(t)
        )
        pencil_modifier.pack(side="left", padx=(2, 0))

        # Maintain references for real-time dynamic switching operations
        self.tab_buttons[tab_title] = {
            "wrapper": widget_wrapper,
            "clicker": text_clicker,
            "editor": pencil_modifier
        }

    def focus_project_tab(self, tab_title):
        """Manages frame stack indexing states to display the visible target tab workspace."""
        if self.current_visible_tab == tab_title:
            return

        # Demote coloring of current tab button frame layer
        if self.current_visible_tab and self.current_visible_tab in self.active_tabs:
            self.active_tabs[self.current_visible_tab]["master_frame"].pack_forget()
            if self.current_visible_tab in self.tab_buttons:
                self.tab_buttons[self.current_visible_tab]["clicker"].configure(fg_color=("gray80", "gray25"))

        # Elevate targeted project window to grid alignment
        self.current_visible_tab = tab_title
        self.active_tabs[tab_title]["master_frame"].pack(fill="both", expand=True)
        self.tab_buttons[tab_title]["clicker"].configure(fg_color=("#1f538d", "#1f538d")) # High contrast focus color

    def prompt_rename_tab(self, old_title):
        """Launches a fast string modal loop window to mutate project workspace signatures."""
        dialog = ctk.CTkInputDialog(text=f"Modify nickname signature for '{old_title}':", title="Rename Workspace")
        new_title = dialog.get_input()
        
        if not new_title or new_title.strip() == "" or new_title.strip() == old_title:
            return
            
        new_title = new_title.strip()

        if new_title in self.active_tabs:
            # Prevent namespace collisons across open project tracks
            tk.messagebox.showwarning("Naming Conflict", f"A project workspace labeled '{new_title}' is already active.")
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

        display_box = tab_data["display"]
        target_url = tab_data["url_input"].get().strip()

        if not target_url:
            display_box.delete("0.0", "end")
            display_box.insert("0.0", "⚠️ Error: Please enter a target URL before running an audit loop.")
            return

        # The first successful check renames the tab to the site's domain (e.g. "website.com"),
        # so save that first audit under the domain name too.
        if not tab_data.get("first_check_done"):
            domain = self.domain_from_url(target_url)
            if domain:
                project_name = self._unique_tab_name(domain, tab_data)

        tab_data["audit_running"] = True
        tab_data["run_btn"].configure(state="disabled")
        display_box.delete("0.0", "end")
        display_box.insert("0.0", f"📡 Contacting {target_url} from the outside...\nParsing structural HTML nodes & fetching cloud performance indexes. Please wait...")

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
                    tab_data["display"].delete("0.0", "end")
                    tab_data["display"].insert("0.0", f"❌ Could not display results: {e}")
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_ui_queue)

    def _finish_audit(self, tab_data, report):
        tab_data["audit_running"] = False
        tab_data["run_btn"].configure(state="normal")

        if "error" in report:
            tab_data["display"].delete("0.0", "end")
            tab_data["display"].insert("0.0", f"❌ Crawl Blocked:\n{report['error']}")
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

        if not report:
            display_box.delete("0.0", "end")
            display_box.insert("0.0", f"📌 [{selected_panel.upper()} VIEW PANEL]\nNo active audit loaded yet. Input a URL and click 'Run Audit' to stream live results here.")
            return

        display_box.delete("0.0", "end")
        
        if selected_panel == "Overview":
            view_text = (
                f"📊 GLOBAL SITE APPRAISAL OVERVIEW\n"
                f"====================================================================\n"
                f"Target Website Address : {report['target_url']}\n"
                f"Mobile Speed Score     : {report['performance']['score']}  (desktop: {report['performance'].get('desktop_score', 'N/A')})\n"
                f"Image Assets Evaluated : {report['images']['total_count']} elements\n"
                f"Total Internal Links   : {report['links']['internal_count']} routing paths\n"
                f"====================================================================\n\n"
                f"💡 Quick Strategy Insights:\n"
                f" • Go to the 'On-Page SEO' panel to review meta tag strategy formatting.\n"
                f" • Go to the 'Performance' panel to resolve loading speed bottlenecks."
            )
        
        elif selected_panel == "On-Page SEO":
            headings_block = report["headings"]
            h1_list = "\n   ├── ".join(headings_block.get("h1", [])) or "None Tagged"
            h2_list = "\n   ├── ".join(headings_block.get("h2", [])[:5]) or "None Tagged"
            
            view_text = (
                f"📝 TECHNICAL ON-PAGE SEO COMPLIANCE\n"
                f"====================================================================\n"
                f"🔹 META DATA VALUES\n"
                f" ├── Meta Title       : {report['meta']['title'] or 'MISSING'}\n"
                f" ├── Title Length     : {report['meta']['title_length']} characters (Ideal: 50-60)\n"
                f" ├── Meta Description : {report['meta']['description'] or 'MISSING'}\n"
                f" └── Desc Length      : {report['meta']['description_length']} characters (Ideal: 150-160)\n\n"
                f"🔹 HEADER NODE STRUCTURE HIERARCHY\n"
                f" H1 Headings Found:\n   ├── {h1_list}\n\n"
                f" H2 Headings Found (Sample):\n   ├── {h2_list}\n\n"
                f"🔹 IMAGES OPTIMIZATION AUDIT\n"
                f" ├── Total Tracked Images : {report['images']['total_count']}\n"
                f" └── Missing ALT Tags     : {report['images']['missing_alt_count']} VULNERABILITIES"
            )

        elif selected_panel == "Performance":
            perf = report["performance"]
            view_text = (
                f"⚡ GOOGLE PAGESPEED (MOBILE FIRST)\n"
                f"====================================================================\n"
                f" ├── Mobile Performance Score  : {perf['score']}   ← what Google ranks on\n"
                f" └── Desktop Performance Score : {perf.get('desktop_score', 'N/A')}\n\n"
                f"🔹 LAB TEST (MOBILE)\n"
                f" ├── Largest Contentful Paint (LCP) : {perf.get('lcp', 'N/A')}   (good: under 2.5 s)\n"
                f" ├── Cumulative Layout Shift (CLS)  : {perf.get('cls', 'N/A')}   (good: under 0.1)\n"
                f" ├── First Contentful Paint (FCP)   : {perf.get('fcp', 'N/A')}   (good: under 1.8 s)\n"
                f" ├── Total Blocking Time (TBT)      : {perf.get('tbt', 'N/A')}   (good: under 200 ms)\n"
                f" └── Speed Index                    : {perf.get('speed_index', 'N/A')}   (good: under 3.4 s)\n\n"
            )

            field = perf.get("field_data")
            if field and field.get("metrics"):
                view_text += f"🔹 REAL VISITORS, LAST 28 DAYS ({field['source']}) — overall: {field['overall']}\n"
                items = list(field["metrics"].items())
                for i, (label, m) in enumerate(items):
                    branch = "└──" if i == len(items) - 1 else "├──"
                    view_text += f" {branch} {label:<26}: {m['value']}  [{m['rating']}]\n"
                view_text += "\n"
            elif "field_data" in perf:
                view_text += "🔹 REAL VISITORS\n └── Not enough Chrome traffic for Google to report real-user data.\n\n"

            fixes = perf.get("fixes") or []
            if fixes:
                view_text += "🔧 TOP FIXES GOOGLE SUGGESTS (biggest gains first)\n"
                for i, fix in enumerate(fixes):
                    branch = "└──" if i == len(fixes) - 1 else "├──"
                    detail = f" — {fix['detail']}" if fix.get("detail") else ""
                    view_text += f" {branch} {fix['title']}{detail}\n"
                view_text += "\n"

            view_text += f"Status: {perf['api_status_log']}"

        elif selected_panel == "Backlinks & Tech":
            dfs = report.get("dataforseo", {})
            view_text = (
                f"🔗 LINKS\n"
                f"====================================================================\n"
                f"🔹 ON THIS PAGE\n"
                f" ├── Internal links : {report['links']['internal_count']}\n"
                f" └── External links : {report['links']['external_count']}\n\n"
                f"🔹 BACKLINK PROFILE (DataForSEO — other sites linking to this domain)\n"
            )
            if dfs.get("status") == "success":
                view_text += (
                    f" ├── Total backlinks          : {fmt_num(dfs.get('backlinks'))}\n"
                    f" ├── Referring domains        : {fmt_num(dfs.get('referring_domains'))}"
                    f"  ({fmt_num(dfs.get('referring_domains_nofollow'))} nofollow)\n"
                    f" ├── Unique main domains      : {fmt_num(dfs.get('referring_main_domains'))}\n"
                    f" ├── Broken backlinks         : {fmt_num(dfs.get('broken_backlinks'))}"
                    f"   (links to pages that no longer exist; worth redirecting)\n"
                    f" └── First seen by DataForSEO : {dfs.get('first_seen') or 'N/A'}\n"
                )
            else:
                view_text += f" └── {dfs.get('error', 'Not configured.')}\n"

        elif selected_panel == "Traffic Analytics":
            opr_metrics = report.get("open_pagerank", {})
            dfs_metrics = report.get("dataforseo", {})
            
            view_text = "📊 DOMAIN AUTHORITY & TRUST\n====================================================================\n\n"
            
            view_text += "🔵 DATAFORSEO:\n"
            if dfs_metrics.get("status") == "success":
                view_text += (
                    f" ├── Domain Rank          : {fmt_num(dfs_metrics.get('rank'))} / 1000   (higher is better)\n"
                    f" ├── Backlink Spam Score  : {dfs_metrics.get('backlinks_spam_score')} / 100   (average for linking sites; over 30 needs a look)\n"
                    f" └── Site Spam Score      : {dfs_metrics.get('target_spam_score')} / 100   (this domain itself)\n\n"
                )
            else:
                view_text += f" └── Status: {dfs_metrics.get('error', 'Not configured.')}\n\n"

            view_text += "🟢 OPENPAGERANK:\n"
            if opr_metrics.get("status") == "success":
                view_text += (
                    f" ├── PageRank Score    : {opr_metrics.get('score')} / 10   (higher is better)\n"
                    f" ├── Global Position   : #{fmt_num(opr_metrics.get('rank'))}   (lower is better)\n"
                    f" ├── Referring Domains : {fmt_num(opr_metrics.get('referring_domains'))}\n"
                    f" └── Trend (up to 12 mo): {describe_trend(opr_metrics.get('trend'))}\n\n"
                )
            else:
                view_text += f" └── Status: {opr_metrics.get('error', 'Not configured or offline.')}\n\n"

            view_text += "====================================================================\n💡 Strategy Tip: Use these metrics to determine domain trustworthiness and backlink viability."

        display_box.insert("0.0", view_text)

    def trigger_report_export(self, project_name):
        tab_data = self.active_tabs.get(project_name, {})
        report_data = tab_data.get("last_report_data")
        display_box = tab_data.get("display")

        if not report_data:
            display_box.insert("end", "\n\n⚠️ Error: No audit data found to export. Run an audit first!")
            return

        filename = f"{project_name.replace(' ', '_')}_Full_SEO_Report.html"

        # --- 0. Escape everything that goes into the HTML ---
        # Titles, descriptions and headings come from third-party sites and must
        # never be written into the report as raw markup.
        def escape_all(value):
            if isinstance(value, str):
                return html.escape(value, quote=True)
            if isinstance(value, dict):
                return {k: escape_all(v) for k, v in value.items()}
            if isinstance(value, list):
                return [escape_all(v) for v in value]
            return value

        report_data = escape_all(report_data)
        project_name = html.escape(project_name, quote=True)

        # --- 1. Extract all data payloads from the dictionary ---
        meta = report_data.get("meta", {})
        perf = report_data.get("performance", {})
        images = report_data.get("images", {})
        links = report_data.get("links", {})
        headings = report_data.get("headings", {})
        opr_metrics = report_data.get("open_pagerank", {})
        dfs_metrics = report_data.get("dataforseo", {})

        # Only show numbers when a lookup actually succeeded; otherwise show why it didn't.
        def lookup_status(metrics):
            status = metrics.get("status")
            if status == "success":
                return True, "Connected", "#10B981"           # Green
            if status == "skipped" or not metrics:
                return False, "Not configured", "#94A3B8"     # Grey
            if status == "not_found":
                return False, "Not in index yet", "#94A3B8"   # Grey
            return False, f"Failed: {metrics.get('error', 'Unknown error')}", "#EF4444"  # Red

        def unavailable_or(ok, text):
            return text if ok else "Unavailable"

        def row(label, value, style=""):
            style_attr = f' style="{style}"' if style else ""
            return f'<div class="metric-row"><div class="label">{label}</div><div class="value"{style_attr}>{value}</div></div>'

        dfs_ok, dfs_status_text, dfs_status_color = lookup_status(dfs_metrics)
        opr_ok, opr_status_text, opr_status_color = lookup_status(opr_metrics)
        dfs_rank = unavailable_or(dfs_ok, f"{fmt_num(dfs_metrics.get('rank'))} / 1000")
        dfs_spam = unavailable_or(dfs_ok, f"{dfs_metrics.get('backlinks_spam_score', 'N/A')} / 100")
        dfs_site_spam = unavailable_or(dfs_ok, f"{dfs_metrics.get('target_spam_score', 'N/A')} / 100")
        opr_score = unavailable_or(opr_ok, f"{opr_metrics.get('score', 'N/A')} / 10")
        opr_rank = unavailable_or(opr_ok, f"#{fmt_num(opr_metrics.get('rank'))}")
        opr_ref_domains = unavailable_or(opr_ok, fmt_num(opr_metrics.get('referring_domains')))
        opr_trend = unavailable_or(opr_ok, describe_trend(opr_metrics.get('trend')))

        # Backlink profile (DataForSEO)
        if dfs_ok:
            backlink_html = (
                '<h3>Backlink Profile (other sites linking to this domain)</h3><div class="metric-block">'
                + row("Total Backlinks", fmt_num(dfs_metrics.get("backlinks")))
                + row("Referring Domains", f"{fmt_num(dfs_metrics.get('referring_domains'))} ({fmt_num(dfs_metrics.get('referring_domains_nofollow'))} nofollow)")
                + row("Unique Main Domains", fmt_num(dfs_metrics.get("referring_main_domains")))
                + row("Broken Backlinks", fmt_num(dfs_metrics.get("broken_backlinks")))
                + row("First Seen", dfs_metrics.get("first_seen") or "N/A")
                + '<p class="explanation-text"><strong>Significance:</strong> Links from many different, relevant domains are one of the strongest ranking signals. Broken backlinks point at pages that no longer exist; redirecting them recovers lost authority.</p></div>'
            )
        else:
            backlink_html = f'<h3>Backlink Profile</h3><div class="metric-block"><p class="explanation-text">DataForSEO: {dfs_status_text}</p></div>'

        # --- 2. Dynamic Formatting Logic ---
        def score_color(score_text):
            """'85/100' -> green/amber/red; status strings like 'Not Configured' -> grey."""
            match = re.match(r"^(\d+)/100$", str(score_text))
            if not match:
                return "#94A3B8"
            value = int(match.group(1))
            return "#10B981" if value >= 90 else "#F59E0B" if value >= 50 else "#EF4444"

        # engine.py already formats real scores as "85/100"; anything else is a status string.
        perf_score_display = str(perf.get('score', 'N/A'))
        perf_color = score_color(perf_score_display)
        desktop_score_display = str(perf.get('desktop_score', 'N/A'))
        desktop_color = score_color(desktop_score_display)

        lab_rows = "".join(
            row(label, perf.get(key, "N/A"))
            for label, key in [("Cumulative Layout Shift (CLS)", "cls"), ("First Contentful Paint (FCP)", "fcp"),
                               ("Total Blocking Time (TBT)", "tbt"), ("Speed Index", "speed_index")]
            if key in perf
        )

        field = perf.get("field_data")
        if field and field.get("metrics"):
            rating_colors = {"FAST": "#10B981", "AVERAGE": "#F59E0B", "SLOW": "#EF4444"}
            field_rows = "".join(
                row(label, f"{m['value']} · {m['rating'].title()}", f"color: {rating_colors.get(m['rating'], '#0F172A')};")
                for label, m in field["metrics"].items()
            )
            field_html = (
                f'<h3>Real Visitors, Last 28 Days ({field["source"]})</h3><div class="metric-block">{field_rows}'
                '<p class="explanation-text"><strong>Significance:</strong> Measured on real Chrome users rather than a test run. This is the data Google actually uses for its page experience ranking signal.</p></div>'
            )
        elif "field_data" in perf:
            field_html = '<h3>Real Visitors</h3><div class="metric-block"><p class="explanation-text">Not enough Chrome traffic for Google to report real-user data for this site yet.</p></div>'
        else:
            field_html = ""

        fixes = perf.get("fixes") or []
        if fixes:
            fix_items = "".join(f"<li>{f['title']}{(' — ' + f['detail']) if f.get('detail') else ''}</li>" for f in fixes)
            fixes_html = f'<h3>Top Fixes Google Suggests</h3><div class="metric-block"><ul>{fix_items}</ul><p class="explanation-text"><strong>Significance:</strong> Ordered by estimated loading-time savings, biggest first.</p></div>'
        else:
            fixes_html = ""

        # --- 3. Build dynamic DOM structure layout ---
        heading_html_sections = ""
        for tag_type in sorted(headings.keys()):
            tag_list = headings.get(tag_type, [])
            if tag_list:
                heading_html_sections += f"<h3>{tag_type.upper()} Elements ({len(tag_list)})</h3>"
                heading_html_sections += f"<p class='explanation-text'>Header tags structure your content. <strong>H1s</strong> act as the book title and should include core target keywords. <strong>H2s</strong> function like book chapters. A broken or non-existent heading hierarchy confuses search engine web crawlers.</p><ul>"
                for text in tag_list:
                    heading_html_sections += f"<li>{text}</li>"  # already escaped above
                heading_html_sections += "</ul>"
        
        if not heading_html_sections:
            heading_html_sections = "<p class='warning-text'>No heading tags (H1-H6) found on this page layout.</p>"

        # --- 4. Master Styled Document Template ---
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Comprehensive Marketing Appraisal - {project_name}</title>
            <style>
                body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; margin: 0; padding: 40px; color: #2C3E50; background-color: #F8F9FA; line-height: 1.6; }}
                .report-card {{ background: #FFFFFF; padding: 50px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); max-width: 900px; margin: 0 auto; border: 1px solid #E2E8F0; }}
                .header {{ border-bottom: 4px solid #3B82F6; padding-bottom: 25px; margin-bottom: 40px; }}
                .header h1 {{ margin: 0; color: #1E3A8A; font-size: 34px; font-weight: 800; letter-spacing: -0.5px; }}
                .header p {{ margin: 8px 0 0 0; color: #64748B; font-size: 15px; }}
                .grid-2 {{ display: grid; grid-template-columns: 1fr; gap: 25px; margin-bottom: 30px; }}
                .section {{ background: #F1F5F9; padding: 25px; border-radius: 10px; border-left: 6px solid #64748B; height: fit-content; }}
                .sec-meta {{ border-left-color: #3B82F6; }}
                .sec-perf {{ border-left-color: #EF4444; }}
                .sec-img {{ border-left-color: #F59E0B; }}
                .sec-link {{ border-left-color: #10B981; }}
                .sec-structure {{ border-left-color: #8B5CF6; }}
                .sec-traffic {{ border-left-color: #0EA5E9; }}
                h2 {{ margin-top: 0; font-size: 22px; color: #0F172A; font-weight: 700; border-bottom: 1px solid #CBD5E1; padding-bottom: 10px; margin-bottom: 15px; }}
                h3 {{ font-size: 14px; color: #475569; margin-top: 20px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}
                .metric-block {{ background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 15px; margin-bottom: 15px; }}
                .metric-row {{ display: flex; justify-content: space-between; font-size: 15px; font-weight: 600; border-bottom: 1px solid #F1F5F9; padding-bottom: 5px; margin-bottom: 5px; }}
                .label {{ color: #475569; }}
                .value {{ color: #0F172A; text-align: right; word-break: break-all; max-width: 70%; }}
                .explanation-text {{ margin: 5px 0 0 0; color: #64748B; font-size: 13px; line-height: 1.4; font-style: italic; font-weight: 400; }}
                ul {{ margin: 10px 0 0 0; padding-left: 20px; color: #334155; font-size: 13px; }}
                li {{ margin-bottom: 6px; font-family: monospace; background: #FFF; padding: 4px 8px; border-radius: 4px; border: 1px solid #E2E8F0; list-style-type: none; }}
                .badge {{ background: #EF4444; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; }}
                .badge.pass {{ background: #10B981; }}
                .warning-text {{ color: #B45309; font-style: italic; font-size: 13px; }}
                @media print {{ body {{ background: #FFF; padding: 0; }} .report-card {{ box-shadow: none; border: none; max-width: 100%; padding: 0; }} .section {{ margin-bottom: 25px; page-break-inside: avoid; }} }}
            </style>
        </head>
        <body>
            <div class="report-card">
                <div class="header">
                    <h1>Marketing Appraisal & Digital Strategy Audit</h1>
                    <p>Workspace Client Profile: <strong>{project_name.upper()}</strong></p>
                    <p>Target Scan Domain: <a href="{report_data['target_url']}" target="_blank" style="color: #3B82F6; text-decoration: none; font-weight: 600;">{report_data['target_url']}</a></p>
                </div>

                <div class="grid-2">
                    <div class="section sec-meta">
                        <h2>📝 Meta Tag Infrastructure</h2>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Meta Title</div><div class="value">{meta.get('title') or 'MISSING'}</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> The most critical on-page SEO asset. This is the clickable headline displayed in search engine results.</p>
                        </div>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Title Length</div><div class="value">{meta.get('title_length', 0)} characters</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Search engines truncate titles after roughly 60 characters.</p>
                        </div>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Meta Description</div><div class="value">{meta.get('description') or 'MISSING'}</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Acts as ad copy that directly impacts your organic click-through rate (CTR).</p>
                        </div>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Description Length</div><div class="value">{meta.get('description_length', 0)} characters</div></div>
                        </div>
                    </div>

                    <div class="section sec-perf">
                        <h2>⚡ Cloud Speed & UX Diagnostics</h2>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Mobile Performance Score</div><div class="value" style="color: {perf_color};"><strong>{perf_score_display}</strong></div></div>
                            <div class="metric-row"><div class="label">Desktop Performance Score</div><div class="value" style="color: {desktop_color};"><strong>{desktop_score_display}</strong></div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Google ranks sites on their mobile version, so the mobile score is the one that counts. Scores below 50 imply heavy visual lag.</p>
                        </div>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Largest Contentful Paint (LCP)</div><div class="value">{perf.get('lcp', 'N/A')}</div></div>
                            {lab_rows}
                            <p class="explanation-text"><strong>Significance:</strong> Lab test on a simulated mid-range phone. Good targets: LCP under 2.5 s, CLS under 0.1, FCP under 1.8 s, TBT under 200 ms.</p>
                        </div>
                        {field_html}
                        {fixes_html}
                    </div>

                    <div class="section sec-traffic">
                        <h2>📈 Domain Authority & Trust</h2>

                        <h3>DataForSEO Engine</h3>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Domain Rank</div><div class="value">{dfs_rank}</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> DataForSEO's measure of backlink strength, from 0 to 1000. Higher numbers mean a stronger, more trusted link profile.</p>
                        </div>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Backlink Spam Score</div><div class="value">{dfs_spam}</div></div>
                            <div class="metric-row"><div class="label">Site Spam Score</div><div class="value">{dfs_site_spam}</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> The backlink score is the average spamminess of the sites linking here; the site score rates this domain itself. Scores above 30 are worth reviewing for low-quality or toxic links.</p>
                        </div>
                        <div class="metric-block">
                            <p class="explanation-text" style="font-style: normal; font-weight: 600;">
                                🛰️ API Sync Status: <span style="color: {dfs_status_color};">{dfs_status_text}</span>
                            </p>
                        </div>

                        <h3>OpenPageRank Engine</h3>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">PageRank Score</div><div class="value">{opr_score}</div></div>
                            <div class="metric-row"><div class="label">Global Position</div><div class="value">{opr_rank}</div></div>
                            <div class="metric-row"><div class="label">Referring Domains</div><div class="value">{opr_ref_domains}</div></div>
                            <div class="metric-row"><div class="label">Trend (up to 12 months)</div><div class="value">{opr_trend}</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> A 0–10 authority score based on links from across the web (higher is better). Global position ranks every domain it tracks, so lower is better.</p>
                            <p class="explanation-text" style="font-style: normal; font-weight: 600; margin-top: 10px;">
                                📡 API Sync Status: <span style="color: {opr_status_color};">{opr_status_text}</span>
                            </p>
                        </div>
                    </div>

                    <div class="section sec-img">
                        <h2>🖼️ Visual Asset Optimization</h2>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Total Media Image Blocks</div><div class="value">{images.get('total_count', 0)} assets</div></div>
                        </div>
                        <div class="metric-block">
                            <div class="metric-row">
                                <div class="label">Missing Alternative Text (Alt Tags)</div>
                                <div class="value">
                                    {images.get('missing_alt_count', 0)} vulnerabilities
                                    {" <span class='badge'>Action Needed</span>" if images.get('missing_alt_count', 0) > 0 else " <span class='badge pass'>Optimized</span>"}
                                </div>
                            </div>
                            <p class="explanation-text"><strong>Significance:</strong> Search engine spiders cannot see images; they read alt text to index visual assets.</p>
                        </div>
                    </div>

                    <div class="section sec-link">
                        <h2>🔗 Links & Backlinks</h2>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Internal Site Navigation Links</div><div class="value">{links.get('internal_count', 0)} pathways</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Internal hyperlinks distribute keyword ranking power across your site.</p>
                        </div>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Outbound External Connections</div><div class="value">{links.get('external_count', 0)} hooks</div></div>
                        </div>
                        {backlink_html}
                    </div>

                    <div class="section sec-structure">
                        <h2>🏗️ Scraped Code Tag Hierarchy Map (DOM Layout)</h2>
                        {heading_html_sections}
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
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
            
            display_box.insert("end", f"\n\n📤 [Export Completed] Strategy report built at:\n{absolute_file_path}")
        except Exception as e:
            display_box.insert("end", f"\n\n❌ Export Failed: {str(e)}")
    
    def prompt_new_tab(self):
        dialog = ctk.CTkInputDialog(text="Enter Project Name:", title="Create Workspace")
        name = dialog.get_input()
        if name and name.strip():
            self.add_new_project_tab(name.strip())

    def on_tab_changed(self):
        pass

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
        """Launches an isolated secondary configuration window..."""


    def open_settings_popup(self):
        """Launches an isolated secondary configuration window to manage API tokens safely with registration navigation links."""
        settings_win = ctk.CTkToplevel(self)
        settings_win.title("Configure API Hooks")
        settings_win.geometry("500x600") # Increased height to accommodate the new input labels
        settings_win.attributes("-topmost", True)

        def open_link(url):
            webbrowser.open_new_tab(url)

        # ----------------- GOOGLE PAGESPEED CONFIG SECTION -----------------
        google_label = ctk.CTkLabel(settings_win, text="Google PageSpeed", font=("Arial", 12, "bold"))
        google_label.pack(pady=(20, 2))
        
        google_link = ctk.CTkLabel(settings_win, text="👉 Get Free PageSpeed Key", text_color="#1f538d", cursor="hand2")
        google_link.pack(pady=(0, 5))
        google_link.bind("<Button-1>", lambda e: open_link("https://developers.google.com/speed/docs/insights/v5/get-started"))

        # Dedicated Input Label
        ctk.CTkLabel(settings_win, text="API Key:").pack(anchor="w", padx=75)
        google_entry = ctk.CTkEntry(settings_win, width=350, show="*")
        google_entry.pack(pady=(0, 5))

        # ----------------- OPENPAGERANK CONFIG SECTION -----------------
        opr_label = ctk.CTkLabel(settings_win, text="OpenPageRank", font=("Arial", 12, "bold"))
        opr_label.pack(pady=(15, 2))
        
        opr_link = ctk.CTkLabel(settings_win, text="👉 Create Free OpenPageRank Account", text_color="#1f538d", cursor="hand2")
        opr_link.pack(pady=(0, 5))
        opr_link.bind("<Button-1>", lambda e: open_link("https://openpagerank.keywordseverywhere.com/"))

        # Dedicated Input Label
        ctk.CTkLabel(settings_win, text="API Key:").pack(anchor="w", padx=75)
        opr_entry = ctk.CTkEntry(settings_win, width=350, show="*")
        opr_entry.pack(pady=(0, 5))

        # ----------------- DATAFORSEO CONFIG SECTION -----------------
        dfs_label = ctk.CTkLabel(settings_win, text="DataForSEO", font=("Arial", 12, "bold"))
        dfs_label.pack(pady=(15, 2))
        
        dfs_link = ctk.CTkLabel(settings_win, text="👉 Create DataForSEO Account", text_color="#1f538d", cursor="hand2")
        dfs_link.pack(pady=(0, 5))
        dfs_link.bind("<Button-1>", lambda e: open_link("https://dataforseo.com/"))

        # Dedicated Input Labels for Login and Password
        ctk.CTkLabel(settings_win, text="API Login ID:").pack(anchor="w", padx=75)
        dfs_login_entry = ctk.CTkEntry(settings_win, width=350, placeholder_text="API Login ID")
        dfs_login_entry.pack(pady=(0, 5))
        
        ctk.CTkLabel(settings_win, text="API Password:").pack(anchor="w", padx=75)
        dfs_pass_entry = ctk.CTkEntry(settings_win, width=350, show="*", placeholder_text="API Password")
        dfs_pass_entry.pack(pady=(0, 5))

        # ----------------- DATA MANAGEMENT -----------------
        # Pre-populate keys dynamically if config.json exists
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    current_keys = json.load(f)
                    google_entry.insert(0, current_keys.get("google_pagespeed_key", ""))
                    opr_entry.insert(0, current_keys.get("open_pagerank_key", ""))
                    dfs_login_entry.insert(0, current_keys.get("dataforseo_login", ""))
                    dfs_pass_entry.insert(0, current_keys.get("dataforseo_password", ""))
            except Exception:
                pass

        # Save logic capturing all four fields
        def save_keys():
            payload = {
                "google_pagespeed_key": google_entry.get().strip(),
                "open_pagerank_key": opr_entry.get().strip(),
                "dataforseo_login": dfs_login_entry.get().strip(),
                "dataforseo_password": dfs_pass_entry.get().strip()
            }
            with open("config.json", "w") as f:
                json.dump(payload, f, indent=4)
            settings_win.destroy()

        save_btn = ctk.CTkButton(settings_win, text="Save All Keys Securely", command=save_keys, fg_color="#24a0ed")
        save_btn.pack(pady=25)


if __name__ == "__main__":
    app = MarketingApp()
    app.mainloop()