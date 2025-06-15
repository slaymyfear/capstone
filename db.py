import pandas as pd
from pymongo import MongoClient
import numpy as np

# Load CSV
df = pd.read_csv("send.csv")

# Normalize column names to match your relational schema
df.rename(columns={
    "Song Title": "Song_Title",
    "Artist": "Artist_Name",
    "Album Title": "Album_Title",
    "Release Year": "Release_Year",
    "Genre": "Genre_Name",
    "Recording Location": "Location_Name",
    "Spotify Popularity Rank": "Spotify_Popularity_Rank",
    "Featured Artists": "Featured_Artists",
    "Producers": "Producer_Name",
    "Label": "Label_Name",
    "Lyrics": "Lyrics",
    "themes": "Theme_Name"
}, inplace=True)

# Clean Label_Name column: remove trailing colons, numbers in parentheses, and strip whitespace
df['Label_Name'] = df['Label_Name'].astype(str).str.replace(r'\s*\(\d+\)|:\s*$', '', regex=True).str.strip()

# Convert NaN, empty strings, or whitespace-only strings in relevant columns to None for proper MongoDB storage
df['dominant_emotion'] = df['dominant_emotion'].replace({np.nan: None}).apply(lambda x: None if isinstance(x, str) and x.strip() == '' else x)
df['Theme_Name'] = df['Theme_Name'].replace({np.nan: None}).apply(lambda x: None if isinstance(x, str) and x.strip() == '' else x)

# Scale Spotify Popularity Rank to 0-100 range if it's not already
# Assuming current values are between 0 and 1, multiply by 100
if df["Spotify_Popularity_Rank"].max() <= 1:
    df["Spotify_Popularity_Rank"] = df["Spotify_Popularity_Rank"] * 100

# Setup MongoDB connection
client = MongoClient("mongodb+srv://whoelsebutv:X39QyOa45NHNWOxc@project.dexlu.mongodb.net/?tls=true")
db = client["capstoneproject"]

# Define collection names
collections = [
    "song", "album", "artist", "song_featured_artist", "genre", "label", 
    "producer", "song_producer", "recording_location", 
    "emotion", "theme", "song_theme"
]

# Clear collections to avoid duplicates
for col in collections:
    db[col].delete_many({})

# Create Recording Location IDs
df["Location_ID"] = df["Location_Name"].astype("category").cat.codes + 1

# Insert unique Albums
album_records = df[["Album_Title", "Release_Year", "Label_Name"]].drop_duplicates()
db["album"].insert_many(album_records.to_dict("records"))

# Insert unique Genres
genre_records = df[["Genre_Name"]].drop_duplicates()
db["genre"].insert_many(genre_records.to_dict("records"))

# Insert unique Labels
label_records = df[["Label_Name"]].drop_duplicates()
db["label"].insert_many(label_records.to_dict("records"))

# Insert unique Emotions
emotion_records = df[["dominant_emotion"]].dropna().drop_duplicates()
emotion_records.rename(columns={"dominant_emotion": "Emotion_Name"}, inplace=True)
db["emotion"].insert_many(emotion_records.to_dict("records"))

# Insert unique Recording Locations
location_records = df[["Location_ID", "Location_Name"]].drop_duplicates()
db["recording_location"].insert_many(location_records.to_dict("records"))

# Insert unique Themes
theme_records = df[["Theme_Name"]].dropna().drop_duplicates()
db["theme"].insert_many(theme_records.to_dict("records"))

# Insert unique Artists
artist_records = df[["Artist_Name"]].dropna().drop_duplicates()
db["artist"].insert_many(artist_records.to_dict("records"))

# Insert unique Producers
producer_records = df[["Producer_Name"]].dropna().drop_duplicates()
db["producer"].insert_many(producer_records.to_dict("records"))

# Insert Songs
song_fields = [
    "Song_Title", "Release_Year", "Spotify_Popularity_Rank", "Lyrics",
    "dominant_emotion", "Album_Title", "Genre_Name", "Label_Name", "Location_Name", "Artist_Name", "Producer_Name", "Featured_Artists"
]
song_records = df[song_fields].drop_duplicates().to_dict("records")
db["song"].insert_many(song_records)

# Insert Song_Featured_Artist (split on comma)
featured_artist_records = []
for _, row in df.iterrows():
    if pd.notna(row["Featured_Artists"]):
        for artist in str(row["Featured_Artists"]).split(","):
            featured_artist_records.append({
                "Song_Title": row["Song_Title"],
                "Artist_Name": artist.strip()
            })
if featured_artist_records:
    db["song_featured_artist"].insert_many(featured_artist_records)

# Insert Song_Producer
song_producer_records = df[["Song_Title", "Producer_Name"]].dropna().drop_duplicates().to_dict("records")
db["song_producer"].insert_many(song_producer_records)

# Insert Song_Theme
song_theme_records = df[["Song_Title", "Theme_Name"]].dropna().drop_duplicates().to_dict("records")
db["song_theme"].insert_many(song_theme_records)

print("✅ Data successfully inserted into MongoDB.")
