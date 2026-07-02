import html
import json
import re
from pathlib import Path

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="Fossil Cat Sites of Europe", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background-color: #d9b38c;
        color: #000000;
    }
    .stMarkdown, .stTextInput, .stSelectbox, .stDataFrame, .stCaption, .stWarning, .stInfo {
        color: #000000;
    }
    .stButton > button {
        background-color: #d9b38c;
        color: #000000;
        border: 1px solid #000000;
    }
    .stButton > button:hover {
        background-color: #c79d6b;
        color: #000000;
        border: 1px solid #000000;
    }
    div[data-testid="stSelectbox"] > div {
        background-color: #d9b38c;
        color: #000000;
        border: 1px solid #000000;
    }
    div[data-testid="stSelectbox"] > div:hover {
        background-color: #c79d6b;
        border: 1px solid #000000;
    }
    div[data-testid="stSelectbox"] [data-baseweb="select"] {
        background-color: #d9b38c;
        color: #000000;
    }
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
        background-color: #d9b38c;
        color: #000000;
    }
    div[data-testid="stSelectbox"] [data-baseweb="select"] span {
        color: #000000;
    }
    div[data-testid="stSelectbox"] [data-baseweb="menu"] {
        background-color: #d9b38c;
        color: #000000;
    }
    div[data-testid="stSelectbox"] [data-baseweb="menu"] div {
        background-color: #d9b38c;
        color: #000000;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<h1 style="display:flex; align-items:center; gap:10px; margin-bottom:0;">'
    '<img src="https://raw.githubusercontent.com/Nemo-uni/FossilCatSitesofEurope/main/Fossil%20cats.jpg" '
    'alt="Fossil cats" width="48" height="48" style="border-radius:6px;">'
    'Fossil Cats in Europe</h1>',
    unsafe_allow_html=True,
)
st.write(
    "This app loads the Excel workbook and plots approximate fossil site locations for every entry on a map. "
    "Hover a point to see the species and age information for that location."
)

COUNTRY_COORDS = {
    "France": (46.603354, 1.888334),
    "Italy": (41.87194, 12.56738),
    "Germany": (51.165691, 10.451526),
    "Greece": (39.074208, 21.824312),
    "Spain": (40.463667, -3.74922),
    "Portugal": (39.399872, -8.224454),
    "Belgium": (50.503887, 4.469936),
    "Czech Republic": (49.817492, 15.472962),
    "Romania": (45.943161, 24.96676),
    "Ukraine": (48.379433, 31.16558),
    "Moldova": (47.411631, 28.369885),
    "Georgia": (41.7151, 44.8271),
    "Bosnia and Herzegovina": (43.915886, 17.679076),
    "Crimea": (45.1739773, 33.336804),
}

LOCATION_COORDS_FILE = Path("location_coords.json")


def normalize_location(location: str) -> str:
    if not isinstance(location, str):
        return ""
    clean = location.replace("’", "'").replace("“", '"').replace("”", '"')
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def load_location_coords() -> dict[str, tuple[float, float]]:
    if not LOCATION_COORDS_FILE.exists():
        return {}

    raw = json.loads(LOCATION_COORDS_FILE.read_text(encoding="utf-8"))
    normalized = {}
    for key, value in raw.items():
        normalized[normalize_location(key).lower()] = tuple(value) if value and value[0] is not None else None
    return normalized


def get_country_centroid(location: str) -> tuple[float, float] | None:
    text = normalize_location(location).lower()
    if not text:
        return None
    for name, coords in COUNTRY_COORDS.items():
        if name.lower() in text:
            return coords
    if "iberia" in text:
        return COUNTRY_COORDS["Spain"]
    if "crimea" in text:
        return COUNTRY_COORDS["Crimea"]
    return None


@st.cache_data
def load_data() -> pd.DataFrame:
    csv_path = Path("Fossil cats in europe.csv")
    excel_path = Path("Fossil cats in europe.xlsx")
    if csv_path.exists():
        df = pd.read_csv(csv_path)
    elif excel_path.exists():
        try:
            df = pd.read_excel(excel_path, engine="openpyxl")
        except ImportError as exc:
            raise FileNotFoundError(
                "Could not open the Excel workbook because openpyxl is not installed. "
                "Please add 'Fossil cats in europe.csv' to the repo or install openpyxl."
            ) from exc
    else:
        raise FileNotFoundError(
            "Data file not found. Add 'Fossil cats in europe.csv' or 'Fossil cats in europe.xlsx' to the repo."
        )

    df.columns = [col.strip() for col in df.columns]
    df["Location"] = df.get("Location", df.get("Location ", "")).astype(str)

    location_coords = load_location_coords()

    def map_location(location: str):
        key = normalize_location(location).lower()
        if key in location_coords and location_coords[key] is not None:
            return location_coords[key]
        return get_country_centroid(location)

    coords = df["Location"].apply(map_location)
    df[["latitude", "longitude"]] = pd.DataFrame(coords.tolist(), index=df.index)

    return df


def parse_age(age_value: str) -> float | None:
    if not isinstance(age_value, str):
        return None
    age_str = age_value.strip().replace(",", ".")
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", age_str)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def age_range_label_to_bounds(label: str) -> tuple[float, float] | None:
    if label == "All ages":
        return None
    parts = label.split("-")
    if len(parts) != 2:
        return None
    try:
        low = float(parts[0].replace(",", "."))
        high = float(parts[1].split()[0].replace(",", "."))
        return low, high
    except ValueError:
        return None


df = load_data()
df["age_ma"] = df["Age"].apply(parse_age)

age_options = [
    "All ages",
    "0,00-0,99 Ma",
    "1,00-1,99 Ma",
    "2,00-2,99 Ma",
    "3,00-3,99 Ma",
    "4,00-4,99 Ma",
]
if "selected_age" not in st.session_state:
    st.session_state.selected_age = "All ages"
if "show_details_dialog" not in st.session_state:
    st.session_state.show_details_dialog = False

st.markdown("#### Filter by age range")
cols = st.columns(len(age_options))
for label, col in zip(age_options, cols):
    if col.button(label, key=f"age_btn_{label}"):
        st.session_state.selected_age = label

selected_age = st.session_state.selected_age
st.markdown(f"**Selected range:** {selected_age}")

species_options = ["All species"] + sorted(
    set(
        str(value).strip()
        for value in df["Species"].dropna().unique()
        if str(value).strip()
    )
)
if "selected_species" not in st.session_state:
    st.session_state.selected_species = "All species"
if "histogram_species" not in st.session_state:
    st.session_state.histogram_species = "All species"

st.markdown("#### Filter by species")
for i in range(0, len(species_options), 4):
    row_options = species_options[i : i + 4]
    cols = st.columns(len(row_options))
    for label, col in zip(row_options, cols):
        if col.button(label, key=f"species_btn_{label}"):
            st.session_state.selected_species = label

selected_species = st.session_state.selected_species
st.markdown(f"**Selected species:** {selected_species}")

if selected_species != "All species":
    df = df[df["Species"].astype(str).str.strip() == selected_species]

range_bounds = age_range_label_to_bounds(selected_age)
if range_bounds is not None:
    low, high = range_bounds
    df = df[df["age_ma"].between(low, high, inclusive="both")]

missing = df[df["latitude"].isna()]

st.subheader("Map of fossil cat sites")
plot_df = df[df["latitude"].notna()].copy()
if not plot_df.empty:
    plot_df = (
        plot_df.groupby(["Location", "latitude", "longitude"], as_index=False)
        .agg(
            Species=("Species", lambda x: "<br/>".join(sorted(set(str(v).strip() for v in x if pd.notna(v))))),
            Age=("Age", lambda x: "<br/>".join(sorted(set(str(v).strip() for v in x if pd.notna(v))))),
        )
    )
    plot_df["tooltip"] = plot_df.apply(
        lambda r: f"<b>Location:</b> {r.Location}",
        axis=1,
    )

    tooltip = {
        "html": "{tooltip}",
        "style": {"backgroundColor": "#333", "color": "white", "padding": "10px", "borderRadius": "5px"},
    }

    view_state = pdk.ViewState(
        latitude=plot_df["latitude"].mean(),
        longitude=plot_df["longitude"].mean(),
        zoom=3,
        pitch=0,
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=plot_df,
        id="fossil-site-points",
        get_position="[longitude, latitude]",
        get_fill_color="[255, 110, 89, 180]",
        get_radius=16,
        radius_units="pixels",
        radius_min_pixels=8,
        radius_max_pixels=24,
        pickable=True,
        auto_highlight=True,
    )

    def find_selected_point_payload(value):
        if isinstance(value, dict):
            if any(key in value for key in ("Location", "Species", "Age", "latitude", "longitude", "Latitude", "Longitude")):
                return value
            for nested_value in value.values():
                found = find_selected_point_payload(nested_value)
                if found is not None:
                    return found
        if isinstance(value, list):
            for item in value:
                found = find_selected_point_payload(item)
                if found is not None:
                    return found
        return None

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
    )
    event = st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="map_chart")

    if event is not None and getattr(event, "selection", None) is not None:
        selection = event.selection
        selected_point = find_selected_point_payload(selection)

        if selected_point is not None:
            location_value = selected_point.get("Location") or selected_point.get("location") or "Unknown"
            species_value = selected_point.get("Species") or selected_point.get("species") or ""
            age_value = selected_point.get("Age") or selected_point.get("age") or "Unknown"
            longitude_value = selected_point.get("Longitude")
            if longitude_value is None:
                longitude_value = selected_point.get("longitude")
            latitude_value = selected_point.get("Latitude")
            if latitude_value is None:
                latitude_value = selected_point.get("latitude")

            matching_row = None
            if location_value != "Unknown":
                matching_row = plot_df.loc[plot_df["Location"] == location_value]
                if not matching_row.empty:
                    matching_row = matching_row.iloc[0]

            if matching_row is not None:
                st.session_state.selected_point_data = {
                    "Location": matching_row.get("Location", location_value),
                    "Species": matching_row.get("Species", species_value),
                    "Age": matching_row.get("Age", age_value),
                    "longitude": matching_row.get("longitude", longitude_value),
                    "latitude": matching_row.get("latitude", latitude_value),
                }
            else:
                st.session_state.selected_point_data = {
                    "Location": location_value,
                    "Species": species_value,
                    "Age": age_value,
                    "longitude": longitude_value,
                    "latitude": latitude_value,
                }
            st.session_state.show_details_dialog = True

    stored_selection = st.session_state.get("selected_point_data")
    if stored_selection is not None and st.session_state.get("show_details_dialog"):
        selected_point_data = stored_selection

        @st.dialog(f"Location: {selected_point_data.get('Location', 'Unknown')}")
        def show_selected_location_dialog():
            location_text = html.escape(str(selected_point_data.get("Location", "Unknown")))
            species_text = [html.escape(line.strip()) for line in str(selected_point_data.get("Species", "")).split("<br/>") if line.strip()]
            age_text = html.escape(str(selected_point_data.get("Age", "Unknown")))

            species_html = "".join(
                f"<li>{line}</li>" for line in species_text
            ) or "<li>Unknown</li>"

            st.markdown(
                f"""
                <div style="background-color:#7a4a1f; color:white; padding:12px; border-radius:8px; border:1px solid #4d2f12;">
                    <p style="margin:0 0 6px 0;"><strong>Location:</strong> {location_text}</p>
                    <p style="margin:0 0 6px 0;"><strong>Species:</strong></p>
                    <ul style="margin:0 0 6px 0; padding-left:20px; color:white;">{species_html}</ul>
                    <p style="margin:0;"><strong>Age:</strong> {age_text}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        show_selected_location_dialog()
        st.session_state.show_details_dialog = False
else:
    view_state = pdk.ViewState(
        latitude=50,
        longitude=10,
        zoom=3,
        pitch=0,
    )
    deck = pdk.Deck(
        layers=[],
        initial_view_state=view_state,
    )
    st.pydeck_chart(deck)
    st.warning("No coordinates could be assigned from the workbook locations.")

st.markdown(
    f"**Total rows:** {len(df)}  \\"
    f"**Mapped points:** {df['latitude'].notna().sum()}  \\"
    f"**Missing points:** {len(missing)}"
)

st.subheader("Fossil abundance by age")
st.selectbox(
    "Species for histogram",
    options=["All species"] + sorted(
        set(
            str(value).strip()
            for value in df["Species"].dropna().unique()
            if str(value).strip()
        )
    ),
    key="histogram_species",
)

histogram_data = df.copy()
if st.session_state.histogram_species != "All species":
    histogram_data = histogram_data[
        histogram_data["Species"].astype(str).str.strip() == st.session_state.histogram_species
    ]

age_histogram = histogram_data["age_ma"].dropna()
if not age_histogram.empty:
    max_age = float(age_histogram.max())
    bin_width = 0.5
    bins = [0.0]
    while bins[-1] < max_age + bin_width:
        bins.append(bins[-1] + bin_width)

    histogram_df = (
        pd.DataFrame({"age_ma": age_histogram})
        .assign(age_bin=lambda x: pd.cut(x["age_ma"], bins=bins, include_lowest=True))
        .groupby("age_bin")
        .size()
        .reset_index(name="fossil_abundance")
    )
    histogram_df["age_bin_label"] = histogram_df["age_bin"].apply(
        lambda value: f"{value.left:.2f}-{value.right:.2f} Ma" if pd.notna(value) else "Unknown"
    )

    histogram_chart = (
        alt.Chart(histogram_df)
        .mark_bar(color="#8b5a2b", opacity=0.95)
        .encode(
            x=alt.X(
                "age_bin_label:N",
                title="Age (Ma)",
                sort=histogram_df["age_bin_label"].tolist(),
            ),
            y=alt.Y("fossil_abundance:Q", title="Fossil abundance"),
            tooltip=["age_bin_label", "fossil_abundance"],
        )
        .properties(
            title=alt.TitleParams("Fossil abundance by age", color="#000000", fontSize=16),
            background="#b8864f",
            width=700,
            height=300,
        )
        .configure_view(strokeWidth=2, stroke="#7a4a1f")
        .configure_title(color="#000000")
        .configure_axis(
            labelColor="#000000",
            titleColor="#000000",
            gridColor="#8b5a2b",
            domainColor="#000000",
            tickColor="#000000",
        )
        .configure_axisX(labelAngle=0)
        .configure_legend(titleColor="#000000", labelColor="#000000")
    )
    st.altair_chart(histogram_chart, use_container_width=True)
else:
    st.info("No age values available for the selected histogram filter.")

with st.expander("Show raw data and location status"):
    st.write(df)

if not missing.empty:
    st.warning(
        "Some entries could not be assigned coordinates. The map shows all rows where latitude/longitude exist."
    )
    st.write(missing[["Species", "Location", "Age", "Figure reference number"]])

st.markdown("---")
st.caption(
    'Madurell-Malapeira J. (2025) "A critical review of the Pliocene and Pleistocene European Felidae fossil record", '
    'Bollettino SPI Vol. 64 (1), pp. 133-163 (doi: 10.4435/BSPI.2025.08)'
)
