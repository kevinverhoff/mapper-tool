import streamlit as st
import osmnx as ox
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from streamlit_searchbox import st_searchbox
import re

st.set_page_config(layout="wide", page_title="City Map Builder")

st.title("City Map Builder")

# -----------------------------
# Style Palettes
# -----------------------------
styles = {

    "Cyberpunk": {
        "bg": "#0d1117",
        "streets": "#2ec4ff",
        "bike": "#ff00ff",
        "walk": "#39ff14",
        "rail": "#ffa600",
        "buildings": "#AAAAAA",
        "residential": "#CCCCCC",
        "parks": "#0b3d2e"
    },

    "Fantasy": {
        "bg": "#1f1b16",
        "streets": "#d4af37",
        "bike": "#7f00ff",
        "walk": "#4caf50",
        "rail": "#c19a6b",
        "buildings": "#8b6f47",
        "residential": "#bfa27a",
        "parks": "#355e3b"
    },

    "Steampunk": {
        "bg": "#2b1b12",
        "streets": "#b87333",
        "bike": "#d4af37",
        "walk": "#c49a6c",
        "rail": "#8b5a2b",
        "buildings": "#5a4633",
        "residential": "#7a614a",
        "parks": "#4a5d23"
    },

    "Pirate": {
        "bg": "#0a1628",
        "streets": "#e8c87a",
        "bike": "#c0392b",
        "walk": "#d4a96a",
        "rail": "#f0e68c",
        "buildings": "#4a3728",
        "residential": "#6b4e3d",
        "parks": "#1a4a3a"
    },

    "Solarpunk": {
        "bg": "#f4f7e8",
        "streets": '#819A7A',
        "bike": "#e76f51",
        "walk": '#44A57C',
        "rail": '#CEC917',
        "buildings": '#2C715F',
        "residential": '#1D271C',
        "parks": '#274637'
    }

}

def is_dark(hex_color):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return luminance < 0.5

US_STATES = {
    "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut",
    "Delaware","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa",
    "Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts","Michigan",
    "Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada","New Hampshire",
    "New Jersey","New Mexico","New York","North Carolina","North Dakota","Ohio",
    "Oklahoma","Oregon","Pennsylvania","Rhode Island","South Carolina","South Dakota",
    "Tennessee","Texas","Utah","Vermont","Virginia","Washington","West Virginia",
    "Wisconsin","Wyoming","District of Columbia"
}

# -----------------------------
# Names
# -----------------------------

def clean_city_name(display_name: str) -> str:
    segments = [s.strip() for s in display_name.split(",")]

    # Drop zip codes, "United States", and pure country names
    filtered = [
    s for s in segments
    if not re.match(r"^\d{4,6}$", s)
    and s not in ("United States", "USA")
    ]

    first = filtered[0] if filtered else segments[0]

    #us cities and counties
    try:
        # Find the state — last segment that matches a known US state
        state = next(
            (s for s in reversed(filtered) if s in US_STATES),
            None
        )

        # If the first segment already contains "County" and matches the second segment minus "County",
        # it's a county-only result — just keep first + state
        if state and state != first:
            return f"{first}, {state}"
        last = filtered[-1] if filtered else segments[0]
        return f"{first}, {last}"
    except:
        return display_name

# -----------------------------
# Cached fetch functions
# -----------------------------
@st.cache_data(show_spinner=False)
def fetch_walk(city):
    return ox.graph_to_gdfs(ox.graph_from_place(city, network_type="walk"), nodes=False)

@st.cache_data(show_spinner=False)
def fetch_bike(city):
    return ox.graph_to_gdfs(ox.graph_from_place(city, network_type="bike"), nodes=False)

@st.cache_data(show_spinner=False)
def fetch_drive(city):
    return ox.graph_to_gdfs(ox.graph_from_place(city, network_type="drive"), nodes=False)

@st.cache_data(show_spinner=False)
def fetch_buildings(city):
    return ox.features_from_place(city, tags={"building": True})

@st.cache_data(show_spinner=False)
def fetch_parks(city):
    return ox.features_from_place(city, tags={"leisure": "park"})

@st.cache_data(show_spinner=False)
def fetch_rail(city):
    return ox.features_from_place(city, tags={"railway": True})

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:

    # City search
    st.markdown("### City")

    @st.cache_data(ttl=600)
    def search_cities(query: str):
        if not query or len(query) < 2:
            return []
        try:
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 8, "addressdetails": 1},
                headers={"User-Agent": "CityMapBuilder https://map-builder.streamlit.app"},
                timeout=10
            )
            results = response.json()
            return [r["display_name"] for r in results] 
        except Exception as e:
            st.text(e)
            return []

    city = st_searchbox(
        search_cities,
        label="Enter city name",
        placeholder="e.g. Greencastle, Indiana",
        default="Greencastle, Indiana",
        key="city_search"
    )

    if not city:
        city = "Greencastle, Indiana"

    # Map style
    st.markdown("### Map Style")

    map_style = st.selectbox(
        "Choose a style",
        ["Cyberpunk", "Fantasy", "Steampunk", "Pirate", "Solarpunk"]
    )

    # Feature selection
    st.markdown("### Map Layers")

    options = ["Streets", "Bike Network", "Walking Paths", "Rail Lines", "Buildings (non-residential)", "Residential Structures", "Parks"]
    selected = st.multiselect("Select layers", options=options, default=options)

    # Legend
    st.markdown("### Legend")

    legend_location = st.selectbox(
        "Legend Corner",
        ["lower left", "lower right", "upper left", "upper right"],
        index=0
    )

    # Map title
    st.markdown("### Map Title")

    map_title = st.text_input("Title", value=clean_city_name(city) if city else "")

    # Generate button
    st.markdown("###")

    st.markdown(
        """
        <style>
        div.stButton > button:first-child {
            background-color: #3C7A4A; /* Desired fill color */
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
        }
        div.stButton > button:hover {
            background-color: #45a049; /* Hover effect */
        }
        </style>
        """,
        unsafe_allow_html=True
)

    generate = st.button("Generate Map", use_container_width=True)

    # Buy me a coffee
    st.markdown("---")
    st.text('If you like this sort of thing, you can support it by buying me a coffee. Any and all contributions are much appreciated.')
    st.markdown(
        '<a href="https://www.buymeacoffee.com/wZyLoMV" target="_blank" '
        'style="display: inline-block; padding: 12px 20px; background-color: #ffdd00; '
        'color: black; text-align: center; border-radius: 5px; text-decoration: none; '
        'font-weight: bold; width: 100%;">☕ Buy me a coffee</a>',
        unsafe_allow_html=True
    )

# -----------------------------
# Derived state
# -----------------------------
include_streets     = "Streets" in selected
include_bike        = "Bike Network" in selected
include_walk        = "Walking Paths" in selected
include_rail        = "Rail Lines" in selected
include_buildings   = "Buildings (non-residential)" in selected
include_residential = "Residential Structures" in selected
include_parks       = "Parks" in selected

palette    = styles[map_style]
text_color = "#ffffff" if is_dark(palette["bg"]) else "#111111"

# -----------------------------
# Generate Map
# -----------------------------
if generate:

    with st.spinner("Downloading map data...(this may take a minute)"):

        try:
            fetch_map = {
                "walk":      (fetch_walk,      include_walk),
                "bike":      (fetch_bike,      include_bike),
                "drive":     (fetch_drive,     include_streets),
                "buildings": (fetch_buildings, include_buildings or include_residential),
                "parks":     (fetch_parks,     include_parks),
                "rail":      (fetch_rail,      include_rail),
            }

            results = {}
            with ThreadPoolExecutor() as executor:
                futures = {
                    executor.submit(fn, city): key
                    for key, (fn, should_fetch) in fetch_map.items()
                    if should_fetch
                }
                for future in as_completed(futures):
                    key = futures[future]
                    results[key] = future.result()

            walk_edges  = results.get("walk")
            bike_edges  = results.get("bike")
            drive_edges = results.get("drive")

            all_buildings = results.get("buildings")
            if all_buildings is not None and not all_buildings.empty:
                buildings   = all_buildings[~all_buildings["building"].isin(["house", "residential"])] if include_buildings else None
                residential = all_buildings[all_buildings["building"].isin(["house", "residential"])]  if include_residential else None
            else:
                buildings = residential = None

            parks = results.get("parks")
            rail  = results.get("rail")

        except Exception as e:
            st.error(f"Error downloading data: {e}")
            st.stop()

    # -----------------------------
    # Plot Map
    # -----------------------------
    fig, ax = plt.subplots(figsize=(12, 12), facecolor=palette["bg"])
    ax.set_facecolor(palette["bg"])

    if parks is not None and not parks.empty:
        parks.plot(ax=ax, color=palette["parks"], linewidth=0)

    if buildings is not None and not buildings.empty:
        buildings.plot(ax=ax, color=palette["buildings"], linewidth=0.1)

    if residential is not None and not residential.empty:
        residential.plot(ax=ax, color=palette["residential"], linewidth=0.1)

    if drive_edges is not None:
        drive_edges.plot(ax=ax, linewidth=0.5, color=palette["streets"], alpha=0.3)

    if bike_edges is not None:
        bike_edges.plot(ax=ax, linewidth=2, color=palette["bike"])

    if walk_edges is not None:
        walk_edges.plot(ax=ax, linewidth=1.2, color=palette["walk"])

    if rail is not None and not rail.empty:
        rail.plot(ax=ax, linewidth=1.4, color=palette["rail"])

    ax.set_axis_off()

    # Legend
    legend_elements = []

    if include_streets:
        legend_elements.append(Line2D([0], [0], color=palette["streets"], lw=2, label="Streets"))
    if include_bike:
        legend_elements.append(Line2D([0], [0], color=palette["bike"], lw=2, label="Bike Network"))
    if include_walk:
        legend_elements.append(Line2D([0], [0], color=palette["walk"], lw=2, label="Walking Paths"))
    if include_rail:
        legend_elements.append(Line2D([0], [0], color=palette["rail"], lw=2, label="Rail"))
    if include_buildings:
        legend_elements.append(Line2D([0], [0], color=palette["buildings"], lw=2, label="Buildings"))
    if include_residential:
        legend_elements.append(Line2D([0], [0], color=palette["residential"], lw=2, label="Residential"))
    if include_parks:
        legend_elements.append(Line2D([0], [0], color=palette["parks"], lw=2, label="Parks"))

    if legend_elements:
        legend = ax.legend(handles=legend_elements, loc=legend_location, frameon=False)
        for text in legend.get_texts():
            text.set_color(text_color)

    plt.title(map_title, fontsize=18, weight="bold", pad=20, color=text_color)

    plt.tight_layout()

    st.pyplot(fig)