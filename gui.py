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

        # --- Tab State Memory ---
        self.active_tabs = {}

        # --- Structure Configurations ---
        self.setup_top_menus()
        self.project_tab_bar = ctk.CTkTabview(self, command=self.on_tab_changed)
        self.project_tab_bar.pack(fill="both", expand=True, padx=10, pady=5)
        
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
        if tab_title in self.active_tabs:
            self.project_tab_bar.set(tab_title)
            return

        self.project_tab_bar.add(tab_title)
        tab_frame = self.project_tab_bar.tab(tab_title)

        # Sidebar Left Framework
        sidebar_frame = ctk.CTkFrame(tab_frame, width=160, corner_radius=0)
        sidebar_frame.pack(side="left", fill="y", padx=5, pady=5)

        sidebar_title = ctk.CTkLabel(sidebar_frame, text="ANALYTICS", font=ctk.CTkFont(size=12, weight="bold"))
        sidebar_title.pack(padx=10, pady=15)

        # Core Metrics Sidebar - Wired up to change visual panels instantly
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

        # Main Text Terminal
        display_output = ctk.CTkTextbox(content_workspace, font=ctk.CTkFont(family="Consolas", size=12))
        display_output.pack(fill="both", expand=True, padx=10, pady=10)
        display_output.insert("0.0", f"Workspace ready for: {tab_title}\nEnter a target URL and hit 'Run Audit'.")

        # Cache live object data states uniquely assigned to this workspace
        self.active_tabs[tab_title] = {
            "url_input": url_input,
            "display": display_output,
            "last_report_data": None,
            "current_panel": "Overview"
        }
        
        self.project_tab_bar.set(tab_title)

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
            # Re-render active view panel with fresh dataset metrics
            self.switch_view_panel(project_name, self.active_tabs[project_name]["current_panel"])

    def switch_view_panel(self, project_name, selected_panel):
        """Filters out data views in real-time depending on which sidebar metric is pressed."""
        tab_memory = self.active_tabs.get(project_name, {})
        display_box = tab_memory.get("display")
        report = tab_memory.get("last_report_data")
        
        # Save current active tab category state
        tab_memory["current_panel"] = selected_panel

        if not report:
            display_box.delete("0.0", "end")
            display_box.insert("0.0", f"📌 [{selected_panel.upper()} VIEW PANEL]\nNo active audit loaded yet. Input a URL and click 'Run Audit' to stream live results here.")
            return

        display_box.delete("0.0", "end")
        
        # Switchboard Filtering Protocol
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
        """Compiles 100% of the active scraped data payload into a professional client report with context explanations."""
        tab_data = self.active_tabs.get(project_name, {})
        report_data = tab_data.get("last_report_data")
        display_box = tab_data.get("display")

        if not report_data:
            display_box.insert("end", "\n\n⚠️ Error: No audit data found to export. Run an audit first!")
            return

        filename = f"{project_name.replace(' ', '_')}_Full_SEO_Report.html"
        
        # Extract full layout objects from our background data dictionary
        meta = report_data.get("meta", {})
        perf = report_data.get("performance", {})
        images = report_data.get("images", {})
        links = report_data.get("links", {})
        headings = report_data.get("headings", {})

        # Build human-readable visual loops for all heading tags (H1 - H6)
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
        
        if not heading_html_sections:
            heading_html_sections = "<p class='warning-text'>No heading tags (H1-H6) found on this page layout.</p>"

        # Master Styled Document Template Engine Generation
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
                            <p class="explanation-text"><strong>Significance:</strong> The most critical on-page SEO asset. This is the clickable headline displayed in search engine results. It tells users and search bots exactly what your page is about.</p>
                        </div>
                        
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Title Length</div><div class="value">{meta.get('title_length', 0)} characters</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Search engines truncate titles after roughly 60 characters. Keeping titles under this threshold ensures branding and conversion hooks don't get chopped off into standard '...' symbols.</p>
                        </div>
                        
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Meta Description</div><div class="value">{meta.get('description') or 'MISSING'}</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> The short descriptive text block under your title snippet. While not a direct ranking signal, it acts as ad copy that directly impacts your organic click-through rate (CTR).</p>
                        </div>
                        
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Description Length</div><div class="value">{meta.get('description_length', 0)} characters</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Google truncates descriptions around 155-160 characters. Keeping descriptions concise prevents valuable call-to-action details from vanishing off-screen.</p>
                        </div>
                    </div>

                    <div class="section sec-perf">
                        <h2>⚡ Cloud Speed & UX Diagnostics</h2>
                        
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Google Performance Score</div><div class="value" style="color: #EF4444;"><strong>{perf.get('score', 'N/A')}/100</strong></div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Google's direct optimization metric. Scores below 50 imply heavy visual lag, which severely risks user abandonment and tanks your overall conversion probability.</p>
                        </div>
                        
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Largest Contentful Paint (LCP)</div><div class="value">{perf.get('lcp', 'N/A')}</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> A critical Core Web Vital tracking how long it takes for the primary visual elements of your page to load. A threshold over 2.5 seconds triggers mobile ranking penalties.</p>
                        </div>
                    </div>

                    <div class="section sec-img">
                        <h2>🖼️ Visual Asset Optimization</h2>
                        
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Total Media Image Blocks</div><div class="value">{images.get('total_count', 0)} assets</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Tracked image footprints on the target viewport page. Excess asset load without compression or caching routines scales down bandwidth performance rules.</p>
                        </div>
                        
                        <div class="metric-block">
                            <div class="metric-row">
                                <div class="label">Missing Alternative Text (Alt Tags)</div>
                                <div class="value">
                                    {images.get('missing_alt_count', 0)} vulnerabilities
                                    {" <span class='badge'>Action Needed</span>" if images.get('missing_alt_count', 0) > 0 else " <span class='badge pass'>Optimized</span>"}
                                </div>
                            </div>
                            <p class="explanation-text"><strong>Significance:</strong> Search engine spiders cannot see images; they read alt text to index visual assets. Missing alt tags harm visual search accessibility and represent lost index keyword real estate.</p>
                        </div>
                    </div>

                    <div class="section sec-link">
                        <h2>🔗 Interconnected Links Architecture</h2>
                        
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Internal Site Navigation Links</div><div class="value">{links.get('internal_count', 0)} pathways</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Internal hyperlinks distribute keyword ranking power (link equity) across your site. Healthy inner pathways ensure crawl bots can crawl and index lower tier service segments.</p>
                        </div>
                        
                        <div class="metric-block">
                            <div class="metric-row"><div class="label">Outbound External Connections</div><div class="value">{links.get('external_count', 0)} hooks</div></div>
                            <p class="explanation-text"><strong>Significance:</strong> Hyperlinks pointing outwards from your site. Linking to untrusted or spammy third-party sites can negatively impact your search engine authority status.</p>
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
            
            display_box.insert("end", f"\n\n📤 [Export Completed] Strategy-infused client report generated at '{filename}'!")
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