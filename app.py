from shiny import *
from utils.ee_utils import forest_loss, forest_map_leaflet
from shinywidgets import output_widget, render_widget, register_widget
import ipyleaflet as leaflet

# Define the UI
app_ui = ui.page_fluid(
    ui.panel_title("Forest App"),
    ui.layout_sidebar(
        ui.panel_sidebar(
            # Input fields
            ui.input_text('country', "Country:", ""),
            ui.input_action_button('calculate', "Calculate forest loss"),
            ui.input_select('year', "Select year:", list(range(2001, 2023))),
            ui.input_action_button('generate', "Show forest loss map")
        ),

        ui.panel_main(
            # Output for plot image
            output_widget('plot_widget'),
            output_widget('map_widget')
        )
    )
)

def server(input, output, session):
    @output
    @render_widget
    def plot_widget():
        if input.calculate():
            fig = forest_loss(input.country(), maxPixels = 1e9)
            return fig
    
    #map = leaflet.Map(zoom=4)
    #register_widget("map", map)
    
    @output
    @render_widget
    def map_widget():
        if input.generate():
            map = forest_map_leaflet(input.country(), int(input.year()))
            return map
            
# Create the Shiny app
app = App(app_ui, server)
