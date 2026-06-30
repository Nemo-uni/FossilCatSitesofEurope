import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Fossil Cat Sites of Europe", layout="wide")
st.title("🗺️ Fossil Cats in Europe")
st.write(
    "This app loads the Excel workbook and plots approximate fossil site locations for every entry on a map. "
    "Coordinates are loaded from a location lookup file and fallback to country centroids when needed."
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
    df = pd.read_excel("Fossil cats in europe.xlsx", engine="openpyxl")
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


df = load_data()
missing = df[df["latitude"].isna()]

st.subheader("Map of fossil cat sites")
if df["latitude"].notna().any():
    st.map(df.loc[df["latitude"].notna(), ["latitude", "longitude"]])
else:
    st.warning("No coordinates could be assigned from the workbook locations.")

st.markdown(
    f"**Total rows:** {len(df)}  \\"
    f"**Mapped points:** {df['latitude'].notna().sum()}  \\"
    f"**Missing points:** {len(missing)}"
)

with st.expander("Show raw data and location status"):
    st.write(df)

if not missing.empty:
    st.warning(
        "Some entries could not be assigned coordinates. The map shows all rows where latitude/longitude exist."
    )
    st.write(missing[["Species", "Location", "Age", "Figure reference number"]])
