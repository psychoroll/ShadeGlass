import tkinter as tk
import customtkinter as ctk
import sqlite3
import json
import os
import threading

# Import pipeline components
from engine import audit_url, load_api_keys, CONFIG_FILE
from database import save_new_audit, initialize_database

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

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

        # --- 1. Global Top Menus ---
        self.setup_top_menus()

        # --- 2. Custom Left-Aligned Tab Control Bar Framework ---
        # Master container for the tab navigation system across the top header row [cite: 846]
        self.top_tab_bar_frame = ctk.CTkFrame(self, height=45, corner_radius=0, fg_color=("gray90", "gray10"))
        self.top_tab_bar_frame.pack(fill="x", side="top", padx=0, pady=0)

        # Container inside the top bar that packs buttons horizontally from the left
        self.tabs_container = ctk.CTkFrame(self.top_tab_bar_frame, fg_color="transparent")
        self.tabs_container.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Quick action action button to launch new browser-like workspace blocks [cite: 622]
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
        settings_menu.add_command(label="Configure API Hooks", command=self.open_settings_window)
        menu_bar.add_cascade(label="Settings", menu=settings_menu)
        
        self.config(menu=menu_bar)

    def add_new_project_tab(self, tab_title):
        """Generates a comprehensive left-aligned tab button widget and isolated workspace panel frame."""
        if tab_title in self.active_tabs:
            self.focus_project_tab(tab_title)
            return

        # 1. Create a Hidden Workspace Frame for This Project [cite: 621, 624]
        tab_frame = ctk.CTkFrame(self.main_workspace_container, fg_color="transparent")
        
        # Sidebar Left Framework inside the project workspace [cite: 587]
        sidebar_frame = ctk.CTkFrame(tab_frame, width=160, corner_radius=0)
        sidebar_frame.pack(side="left", fill="y", padx=5, pady=5)

        sidebar_title = ctk.CTkLabel(sidebar_frame, text="ANALYTICS", font=ctk.CTkFont(size=12, weight="bold"))
        sidebar_title.pack(padx=10, pady=15)

        # Core Metrics Sidebar - Wired up to switch sub-panels instantly [cite: 632]
        modules = ["Overview", "On-Page SEO", "Performance", "Backlinks & Tech"]
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

        # Content Output Window Right Frame
        content_workspace = ctk.CTkFrame(tab_frame, fg_color=("gray95", "gray15"))
        content_workspace.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        header_controls = ctk.CTkFrame(content_workspace, height=50)
        header_controls.pack(fill="x", padx=10, pady=10)

        url_input = ctk.CTkEntry(header_controls, placeholder_text="Enter competitor or client URL here...")
        url_input.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        url_input.bind("<Return>", lambda event, t=tab_title: self.trigger_live_audit(t)) # [cite: 826]

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

        # Cache layout memory pointers and tracking state objects [cite: 631]
        self.active_tabs[tab_title] = {
            "master_frame": tab_frame,
            "url_input": url_input,
            "display": display_output,
            "last_report_data": None,
            "current_panel": "Overview"
        }

        # 2. Build and Render the Left-Aligned Navigation Tab Widget Item [cite: 847, 850]
        self.render_tab_button_widget(tab_title)
        
        # Shift immediate screen visibility focus directly to this new instance [cite: 631]
        self.focus_project_tab(tab_title)

    def render_tab_button_widget(self, tab_title):
        """Constructs an aligned horizontal frame container pairing a name link with a rename tool."""
        widget_wrapper = ctk.CTkFrame(self.tabs_container, fg_color="transparent")
        widget_wrapper.pack(side="left", padx=3, pady=4) # Left aligned stacking pipeline [cite: 850]

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

        # Miniature Editing Pencil Icon Button ✏️ (Replaced old gear element) [cite: 847, 852]
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

        # Demote coloring of current tab button frame layer [cite: 851]
        if self.current_visible_tab and self.current_visible_tab in self.active_tabs:
            self.active_tabs[self.current_visible_tab]["master_frame"].pack_forget()
            if self.current_visible_tab in self.tab_buttons:
                self.tab_buttons[self.current_visible_tab]["clicker"].configure(fg_color=("gray80", "gray25"))

        # Elevate targeted project window to grid alignment [cite: 851]
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

        # 1. Pivot Data Reference Maps [cite: 854]
        self.active_tabs[new_title] = self.active_tabs.pop(old_title)
        self.tab_buttons[new_title] = self.tab_buttons.pop(old_title)

        # 2. Re-wire Dynamic Callback Logic Inside UI Elements [cite: 854]
        button_refs = self.tab_buttons[new_title]
        button_refs["clicker"].configure(text=new_title, command=lambda t=new_title: self.focus_project_tab(t))
        button_refs["editor"].configure(command=lambda t=new_title: self.prompt_rename_tab_dialog(t))
        
        # 3. Update Title String Labels for the Context Panels Loop
        url_input = self.active_tabs[new_title]["url_input"]
        url_input.unbind("<Return>")
        url_input.bind("<Return>", lambda event, t=new_title: self.trigger_live_audit(t))
        
        # If renamed tab was current, sync global visible key values
        if self.current_visible_tab == old_title:
            self.current_visible_tab = new_title

        print(f"Successfully pivoted track context mapping elements from '{old_title}' into '{new_title}'.")

    def trigger_live_audit(self, project_name):
        worker_thread = threading.Thread(target=self._async_audit_worker, args=(project_name,))
        worker_thread.daemon = True
        worker_thread.start()

    def _async_audit_worker(self, project_name):
        url_box = self.active_tabs[project_name]["url_input"]
        display_box = self.active_tabs[project_name]["display"]
        target_url = url_box.get().strip()

        if not target_url:
            display_box.delete("0.0", "end")
            display_box.insert("0.0", "⚠️ Error: Please enter a target URL before running an audit loop.")
            return

        display_box.delete("0.0", "end")
        display_box.insert("0.0", f"📡 Contacting {target_url} from the outside...\nParsing structural HTML nodes & fetching cloud performance indexes. Please wait...")

        report = audit_url(target_url)

        if "error" in report:
            display_box.delete("0.0", "end")
            display_box.insert("0.0", f"❌ Crawl Blocked:\n{report['error']}")
        else:
            save_new_audit(project_name, target_url, report)
            self.active_tabs[project_name]["last_report_data"] = report
            self.switch_view_panel(project_name, self.active_tabs[project_name]["current_panel"])

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
                f"Google UX Speed Score  : {report['performance']['score']}\n"
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
            view_text = (
                f"⚡ GOOGLE PERFORMANCE ENGINE & CLOUD METRICS\n"
                f"====================================================================\n"
                f" ├── Core Web Vitals Performance Score : {report['performance']['score']}\n"
                f" ├── Largest Contentful Paint (LCP)    : {report['performance']['lcp']}\n"
                f" └── Google Cloud Engine Status Log    : {report['performance']['api_status_log']}\n\n"
                f"💡 Marketing Analysis:\n"
                f" If LCP scores exceed 2.5 seconds, the page is taking too long to compile\n"
                f" primary visuals, increasing user drop-off. Compress images and clean\n"
                f" up render-blocking JavaScript files."
            )

        elif selected_panel == "Backlinks & Tech":
            view_text = (
                f"🔗 LINK ARCHITECTURE & TECHNICAL EXTENSIONS (THE OUTSIDE)\n"
                f"====================================================================\n"
                f" ├── Internal Navigation Hyperlinks : {report['links']['internal_count']} endpoints\n"
                f" └── Outbound External Escapes      : {report['links']['external_count']} marketing tracking hooks\n\n"
                f"🛠️ EXTENSIBLE BACKEND HOOKS STAGING\n"
                f" [Semrush / Ahrefs Domain Authority Integration Loop]\n"
                f"   ├── Status: Ready to execute.\n"
                f"   └── Setup: Paste your Semrush developer token into top Settings menu to pull link metrics."
            )

        display_box.insert("0.0", view_text)

    def trigger_report_export(self, project_name):
        tab_data = self.active_tabs.get(project_name, {})
        report_data = tab_data.get("last_report_data")
        display_box = tab_data.get("display")

        if not report_data:
            display_box.insert("end", "\n\n⚠️ Error: No audit data found to export. Run an audit first!")
            return

        filename = f"{project_name.replace(' ', '_')}_Full_SEO_Report.html"
        meta = report_data.get("meta", {})
        perf = report_data.get("performance", {})
        images = report_data.get("images", {})
        links = report_data.get("links", {})
        headings = report_data.get("headings", {})

        heading_html_sections = ""
        for tag_type in sorted(headings.keys()):
            tag_list = headings.get(tag_type, [])
            if tag_list:
                heading_html_sections += f"<h3>{tag_type.upper()} Elements ({len(tag_list)})</h3>"
                heading_html_sections += f"<p class='explanation-text'>Header tags structure your content. <strong>H1s</strong> act as the book title and should include core target keywords. <strong>H2s</strong> function like book chapters. A broken or non-existent heading hierarchy confuses search engine web crawlers.</p><ul>"
                for text in tag_list:
                    safe_text = text.replace("<", "&lt;").replace(">", "&gt;")
                    heading_html_sections += f"<li>{safe_text}</li>"
                heading_html_sections += "</ul>"

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
                .grid-2 {{ display: grid; grid-template-columns: 1fr; gap: 25px; margin-bottom: 30px; }}
                .section {{ background: #F1F5F9; padding: 25px; border-radius: 10px; border-left: 6px solid #64748B; height: fit-content; }}
                .sec-meta {{ border-left-color: #3B82F6; }}
                .sec-perf {{ border-left-color: #EF4444; }}
                .sec-img {{ border-left-color: #F59E0B; }}
                .sec-link {{ border-left-color: #10B981; }}
                .sec-structure {{ border-left-color: #8B5CF6; }}
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
                            <p class="explanation-text"><strong>Significance:</strong> The most critical on-page SEO asset. This is the clickable headline displayed in search results.</p>
                        </div>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Title Length</div><div class="value">{meta.get('title_length', 0)} characters</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Search engines truncate titles after roughly 60 characters.</p>
                        </div>
                    </div>
                    <div class="section sec-perf">
                        <h2>⚡ Cloud Speed & UX Diagnostics</h2>
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Google Performance Score</div><div class="value" style="color: #EF4444;"><strong>{perf.get('score', 'N/A')}/100</strong></div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Google's direct optimization metric. Scores below 50 imply heavy visual lag.</p>
                        </div>
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
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            import webbrowser
            webbrowser.open(filename)
            display_box.insert("end", f"\n\n📤 [Export Completed] Strategy report card built at '{filename}'!")
        except Exception as e:
            display_box.insert("end", f"\n\n❌ Export Failed: {str(e)}")

    def open_settings_window(self):
        settings_win = ctk.CTkToplevel(self)
        settings_win.title("API Key Configuration Engine")
        settings_win.geometry("450x300")
        settings_win.attributes("-topmost", True)

        lbl = ctk.CTkLabel(settings_win, text="Configure External API Key Hooks", font=ctk.CTkFont(size=14, weight="bold"))
        lbl.pack(pady=15)

        ctk.CTkLabel(settings_win, text="Google PageSpeed Insights Token:").pack(anchor="w", padx=30)
        key_input = ctk.CTkEntry(settings_win, width=380, show="*")
        key_input.pack(pady=5, padx=30)

        saved_keys = load_api_keys()
        key_input.insert(0, saved_keys.get("google_pagespeed", ""))

        save_btn = ctk.CTkButton(settings_win, text="Save Keys Securely", command=lambda: self.save_api_keys(key_input.get(), settings_win))
        save_btn.pack(pady=20)

    def save_api_keys(self, entry_value, setup_window):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"google_pagespeed": entry_value.strip()}, f, indent=4)
        except Exception as e:
            print(f"Failed to save keys: {e}")
        setup_window.destroy()

    def prompt_new_tab(self):
        dialog = ctk.CTkInputDialog(text="Enter Project Name:", title="Create Workspace")
        name = dialog.get_input()
        if name and name.strip():
            self.add_new_project_tab(name.strip())

    def on_tab_changed(self):
        pass

if __name__ == "__main__":
    app = MarketingApp()
    app.mainloop()