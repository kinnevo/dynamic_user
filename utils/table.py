from nicegui import ui
import pandas as pd
import markdown

class ProjectComparisonApp:
    def __init__(self):
        self.projects = []
        self.features = []
        self.format_type = "markdown"
        self.comparison_data = {}
        self.setup_ui()

    def setup_ui(self):
        ui.markdown("# Project Comparison Table Generator")
        
        with ui.card().classes('w-full'):
            ui.markdown("## Enter Projects")
            ui.markdown("Add your projects one by one:")
            
            with ui.row():
                self.project_input = ui.input(label="Project Name").classes('w-8/12')
                ui.button("Add Project", on_click=self.add_project).classes('mt-5')
            
            with ui.expansion("Current Projects", icon="list").classes('w-full'):
                self.project_list = ui.markdown("*No projects added yet*")
        
        with ui.card().classes('w-full mt-4'):
            ui.markdown("## Add Features")
            ui.markdown("Add up to 5 common features for comparison:")
            
            with ui.row():
                self.feature_input = ui.input(label="Feature Name").classes('w-8/12')
                ui.button("Add Feature", on_click=self.add_feature).classes('mt-5')
            
            with ui.expansion("Current Features", icon="list").classes('w-full'):
                self.feature_list = ui.markdown("*No features added yet*")
        
        with ui.card().classes('w-full mt-4'):
            ui.markdown("## Set Feature Values")
            self.feature_grid = ui.element('div')
            ui.button("Update Values", on_click=self.update_values).classes('mt-2')
        
        with ui.card().classes('w-full mt-4'):
            ui.markdown("## Output Format")
            
            with ui.row():
                ui.radio(["markdown", "html"], value="markdown").props('label="Select Format"')
            
            ui.button("Generate Comparison Table", on_click=self.generate_table).classes('mt-2')
        
        with ui.card().classes('w-full mt-4'):
            ui.markdown("## Result")
            self.output_container = ui.element('div')
            self.result_display = ui.html("").classes('w-full')
            self.copy_button = ui.button("Copy to Clipboard", on_click=self.copy_to_clipboard).classes('mt-2')
            self.copy_button.disable()
    
    def add_project(self):
        project = self.project_input.value
        if project and project not in self.projects:
            self.projects.append(project)
            self.project_input.value = ""
            self.update_project_list()
            self.update_feature_grid()
    
    def add_feature(self):
        feature = self.feature_input.value
        if feature and feature not in self.features and len(self.features) < 5:
            self.features.append(feature)
            self.feature_input.value = ""
            self.update_feature_list()
            self.update_feature_grid()
    
    def update_project_list(self):
        if not self.projects:
            self.project_list.content = "*No projects added yet*"
        else:
            projects_md = "- " + "\n- ".join(self.projects)
            self.project_list.content = projects_md
    
    def update_feature_list(self):
        if not self.features:
            self.feature_list.content = "*No features added yet*"
        else:
            features_md = "- " + "\n- ".join(self.features)
            self.feature_list.content = features_md
    
    def update_feature_grid(self):
        self.feature_grid.clear()
        
        if not self.projects or not self.features:
            with self.feature_grid:
                ui.label("Add both projects and features to define their relationships")
            return
        
        # Initialize comparison data if needed
        for project in self.projects:
            if project not in self.comparison_data:
                self.comparison_data[project] = {}
        
        with self.feature_grid:
            # Create header row
            with ui.row().classes('w-full font-bold'):
                ui.label("Project").classes('w-3/12')
                for feature in self.features:
                    ui.label(feature).classes('w-2/12 text-center')
            
            # Create data rows with checkboxes
            for project in self.projects:
                with ui.row().classes('w-full'):
                    ui.label(project).classes('w-3/12')
                    for feature in self.features:
                        # Initialize if not exists
                        if feature not in self.comparison_data[project]:
                            self.comparison_data[project][feature] = False
                        
                        # Create a checkbox for each project-feature combination
                        ui.checkbox("", value=self.comparison_data[project][feature], 
                                    on_change=lambda e, p=project, f=feature: self.toggle_feature(p, f, e.value)
                                   ).classes('w-2/12 flex justify-center')
    
    def toggle_feature(self, project, feature, value):
        self.comparison_data[project][feature] = value
    
    def update_values(self):
        # Values are continuously updated via toggle_feature
        ui.notify("Values updated!")
    
    def set_format(self, format_type):
        self.format_type = format_type
    
    def generate_table(self):
        if not self.projects or not self.features:
            ui.notify("Add projects and features first!", type="negative")
            return
        
        # Generate table based on selected format
        if self.format_type == "markdown":
            table = self.generate_markdown_table()
        else:  # HTML
            table = self.generate_html_table()
        
        # Display the result
        self.result = table
        
        if self.format_type == "markdown":
            # Convert markdown to HTML for display
            html_content = markdown.markdown(table)
            self.result_display.content = f"<div class='border p-4 bg-gray-50'>{html_content}</div>"
        else:
            self.result_display.content = f"<div class='border p-4 bg-gray-50'>{table}</div>"
        
        # Show the raw code below
        self.output_container.clear()
        with self.output_container:
            ui.markdown("### Raw Code (Copy this)")
            ui.code(table, language=self.format_type).classes('w-full')
        
        self.copy_button.enable()
    
    def generate_markdown_table(self):
        # Create header row
        header = "| Project | " + " | ".join(self.features) + " |"
        separator = "| " + " | ".join(["---"] * (len(self.features) + 1)) + " |"
        
        # Create data rows
        rows = []
        for project in self.projects:
            row_cells = [project]
            for feature in self.features:
                value = self.comparison_data.get(project, {}).get(feature, False)
                row_cells.append("✅" if value else "❌")
            rows.append("| " + " | ".join(row_cells) + " |")
        
        # Combine all parts
        table = "\n".join([header, separator] + rows)
        return table
    
    def generate_html_table(self):
        # Start the HTML table
        html = [
            "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse;'>",
            "  <thead>",
            "    <tr>",
            f"      <th>Project</th>",
        ]
        
        # Add feature headers
        for feature in self.features:
            html.append(f"      <th>{feature}</th>")
        
        html.append("    </tr>")
        html.append("  </thead>")
        html.append("  <tbody>")
        
        # Add data rows
        for project in self.projects:
            html.append("    <tr>")
            html.append(f"      <td>{project}</td>")
            
            for feature in self.features:
                value = self.comparison_data.get(project, {}).get(feature, False)
                icon = "✅" if value else "❌"
                html.append(f"      <td align='center'>{icon}</td>")
            
            html.append("    </tr>")
        
        # Close the table
        html.append("  </tbody>")
        html.append("</table>")
        
        return "\n".join(html)
    
    def copy_to_clipboard(self):
        ui.run_javascript(f"""
            navigator.clipboard.writeText(`{self.result}`).then(function() {{
                console.log('Text copied to clipboard');
            }})
            .catch(function(error) {{
                console.error('Error copying text: ', error);
            }});
        """)
        ui.notify("Copied to clipboard!")

# Initialize the app
def init():
    app = ProjectComparisonApp()
    ui.run()

if __name__ in {"__main__", "__mp_main__"}:
    app = ProjectComparisonApp()
    ui.run()