from flask import Flask, jsonify, render_template, request
from pymongo import MongoClient
import numpy as np
import plotly.express as px
from collections import defaultdict
from datetime import datetime
import os
from bson import json_util
import json

app = Flask(__name__)
client = MongoClient("mongodb+srv://whoelsebutv:X39QyOa45NHNWOxc@project.dexlu.mongodb.net/?tls=true")
db = client["capstoneproject"]

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
app.config['DEBUG'] = True

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/operational_dashboard')
def operational_dashboard():
    return render_template('operational_dashboard.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/analytics_dashboard')
def analytics_dashboard():
    return render_template('analytical_dashboard.html')

@app.route('/dashboard2')
def strategic_dashboard():
    return render_template('dashboard2.html')

# 1. Artist Market Share
@app.route('/api/strategic/artist-market-share')
def artist_market_share():
    try:
        songs = list(db.song.find({}, {"Artist_Name": 1, "Spotify_Popularity_Rank": 1}))
        
        artists = list({s.get("Artist_Name") for s in songs if s.get("Artist_Name")})
        artists.sort()

        if not artists:
            return jsonify({
                "artists": [],
                "song_counts": [],
                "high_popularity_counts": []
            })

        song_counts = [sum(1 for s in songs if s.get("Artist_Name") == a) for a in artists]
        
        pop_ranks = [s.get("Spotify_Popularity_Rank", 0) for s in songs if s.get("Spotify_Popularity_Rank") is not None]
        threshold = np.percentile(pop_ranks, 80) if pop_ranks else 0
        
        high_popularity_counts = [
            sum(1 for s in songs if s.get("Artist_Name") == a and s.get("Spotify_Popularity_Rank", 0) >= threshold)
            for a in artists
        ]

        return jsonify({
            "artists": artists,
            "song_counts": song_counts,
            "high_popularity_counts": high_popularity_counts
        })
    except Exception as e:
        print(f"ERROR: Failed to calculate artist market share: {e}")
        return jsonify({"error": "Failed to retrieve artist market share data"}), 500

# 2. Producer Effectiveness (Updated)
@app.route('/api/strategic/producer-effectiveness')
def producer_effectiveness():
    try:
        songs = list(db.song.find(
            {"Producer_Name": {"$exists": True, "$ne": None}},
            {"Producer_Name": 1, "Artist_Name": 1, "Spotify_Popularity_Rank": 1}
        ))

        # Filter out songs where Producer_Name is NaN or an empty string after fetching
        songs = [s for s in songs if s.get("Producer_Name") is not None and s.get("Producer_Name") != "" and s.get("Producer_Name") == s.get("Producer_Name")] # The last check handles NaN
        
        # Group by producer and calculate stats
        producer_data = defaultdict(lambda: {
            'total_rank': 0,
            'count': 0,
            'artists': set(),
            'artist_counts': defaultdict(int)
        })
        
        for song in songs:
            producer = song.get("Producer_Name")
            artist = song.get("Artist_Name", "Unknown")
            rank = song.get("Spotify_Popularity_Rank", 0)
            
            if producer:
                producer_data[producer]['total_rank'] += rank
                producer_data[producer]['count'] += 1
                producer_data[producer]['artists'].add(artist)
                producer_data[producer]['artist_counts'][artist] += 1
        
        # Prepare response data
        producers = []
        avg_ranks = []
        artist_lists = []
        primary_artists = []
        song_counts = []
        
        for producer, stats in producer_data.items():
            producers.append(producer)
            avg_ranks.append(round(stats['total_rank'] / stats['count'], 2))
            artist_lists.append(list(stats['artists']))
            
            # Find primary artist (most collaborations)
            if stats['artist_counts']:
                primary_artist = max(stats['artist_counts'].items(), key=lambda x: x[1])[0]
                primary_artists.append(primary_artist)
            else:
                primary_artists.append("Unknown")
            
            song_counts.append(stats['count'])
        
        return jsonify({
            "producers": producers,
            "avg_ranks": avg_ranks,
            "primary_artists": primary_artists,
            "artist_lists": artist_lists,
            "song_counts": song_counts
        })
    except Exception as e:
        print(f"ERROR in producer-effectiveness: {e}")
        return jsonify({"error": str(e)}), 500

# 3. Collaboration Network
@app.route('/api/strategic/collaboration-network')
def collaboration_network():
    try:
        songs = list(db.song.find(
            {"Artist_Name": {"$exists": True}},
            {"Artist_Name": 1, "Featured_Artists": 1, "Spotify_Popularity_Rank": 1}
        ))
        
        node_map = {}
        edges = []
        node_id = 1
        
        for song in songs:
            main_artist = song.get("Artist_Name")
            featured = song.get("Featured_Artists", "")
            pop = song.get("Spotify_Popularity_Rank", 0)
            
            if not main_artist:
                continue
                
            if main_artist not in node_map:
                node_map[main_artist] = {
                    "id": node_id,
                    "label": main_artist,
                    "value": pop,  # Directly use popularity for sizing (assuming higher is more popular)
                    "title": f"Artist: {main_artist}<br>Popularity: {pop}"
                }
                node_id += 1
            
            if featured:
                # Split, strip, and filter out any empty strings or 'nan' values
                for f in [x.strip() for x in featured.split(",") if x.strip() and x.strip().lower() != 'nan']:
                    if f not in node_map:
                        node_map[f] = {
                            "id": node_id,
                            "label": f,
                            "value": pop, # Directly use popularity for sizing
                            "title": f"Artist: {f}<br>Popularity: {pop}"
                        }
                        node_id += 1
                    # Add edge from main artist to featured artist
                    edges.append({
                        "from": node_map[main_artist]["id"],
                        "to": node_map[f]["id"],
                        "value": 1 # You can use popularity or a different metric here for edge thickness
                    })
                    # Add edge from featured artist to main artist for bidirectionality
                    edges.append({
                        "from": node_map[f]["id"],
                        "to": node_map[main_artist]["id"],
                        "value": 1
                    })
        
        # Combine duplicate edges (ensure undirected: A-B is same as B-A)
        edge_counter = defaultdict(int)
        for edge in edges:
            # Create a sorted tuple for the key to treat edges as undirected
            key = tuple(sorted((edge["from"], edge["to"])))
            edge_counter[key] += edge.get("value", 1) # Sum values if edges have weight, otherwise just count
        
        unique_edges = [{
            "from": k[0],
            "to": k[1],
            "value": v,
            "title": f"{v} collaboration(s)"
        } for k, v in edge_counter.items()]
        
        return jsonify({
            "nodes": list(node_map.values()),
            "edges": unique_edges
        })
    except Exception as e:
        print(f"ERROR in collaboration-network: {e}")
        print(f"Nodes generated: {list(node_map.values())[:5]}...") # Log first 5 nodes
        print(f"Edges generated: {unique_edges[:5]}...") # Log first 5 edges
        return jsonify({"error": str(e)}), 500

# 4. Label Performance (Stacked Bar Chart)
@app.route('/api/strategic/label-performance')
def label_performance():
    try:
        songs = list(db.song.find(
            {"Label_Name": {"$exists": True, "$ne": None}},
            {"Label_Name": 1, "Spotify_Popularity_Rank": 1}
        ))
        
        labels = sorted(list({s.get("Label_Name") for s in songs if s.get("Label_Name")}))
        
        # Define popularity tiers (Corrected: Higher rank = More Popular)
        tiers = [
            {"name": "Top (76-100)", "min": 76, "max": 100, "color": "#006837"}, # Dark Green
            {"name": "High (51-75)", "min": 51, "max": 75, "color": "#31a354"}, # Medium Green
            {"name": "Medium (26-50)", "min": 26, "max": 50, "color": "#fdc086"}, # Orange-Yellow
            {"name": "Low (0-25)", "min": 0, "max": 25, "color": "#a50f15"}  # Dark Red
        ]
        
        # Calculate counts per tier for each label
        label_data = []
        for label in labels:
            label_songs = [s for s in songs if s.get("Label_Name") == label]
            total_songs = len(label_songs)
            
            if total_songs == 0:
                continue
                
            tier_counts = []
            for tier in tiers:
                count = sum(
                    1 for s in label_songs 
                    if tier["min"] <= (s.get("Spotify_Popularity_Rank") or 100) <= tier["max"]
                )
                percentage = round((count / total_songs) * 100, 1)
                tier_counts.append({
                    "count": count,
                    "percentage": percentage,
                    "color": tier["color"]
                })
            
            label_data.append({
                "label": label,
                "total_songs": total_songs,
                "tiers": tier_counts
            })
        
        # Sort labels by percentage of 'Top' songs (descending) and take top 10
        # Find the index of the 'Top' tier to sort by it
        top_tier_index = next((i for i, tier in enumerate(tiers) if tier["name"].startswith("Top")), 0)
        label_data.sort(key=lambda x: x["tiers"][top_tier_index]["percentage"], reverse=True)
        top_labels = label_data[:10]
        
        return jsonify({
            "labels": [ld["label"] for ld in top_labels],
            "tier_names": [t["name"] for t in tiers],
            "tier_colors": [t["color"] for t in tiers],
            "percentages": [
                [t["percentage"] for t in ld["tiers"]] 
                for ld in top_labels
            ],
            "total_songs_per_label": [ld["total_songs"] for ld in top_labels]
        })
    except Exception as e:
        print(f"ERROR in label-performance: {e}")
        return jsonify({"error": str(e)}), 500

# 4. Artist -> Album -> Emotion (Sunburst Chart Data)
@app.route('/api/strategic/artist-album-emotion')
def artist_album_emotion():
    try:
        pipeline = [
            {"$match": {
                "Artist_Name": {"$exists": True, "$ne": None},
                "Album_Title": {"$exists": True, "$ne": None},
                "dominant_emotion": {"$exists": True, "$ne": None}
            }},
            {"$group": {
                "_id": {
                    "artist": "$Artist_Name",
                    "album": "$Album_Title",
                    "emotion": "$dominant_emotion"
                },
                "count": {"$sum": 1}
            }}
        ]

        artist_filter = request.args.get('artist_name')
        if artist_filter:
            # Add a match stage for the specific artist if provided
            pipeline.insert(0, {"$match": {"Artist_Name": artist_filter}})

        data = list(db.song.aggregate(pipeline))
        print("DEBUG: artist-album-emotion aggregation result:", data)

        # Build flat lists for Plotly Treemap
        labels = []
        parents = []
        values = []
        ids = [] # Add ids list

        # Add root node
        labels.append("All Artists")
        parents.append("")
        values.append(0)
        ids.append("all_artists") # Unique ID for the root

        artist_map = {}
        album_map = {}
        album_emotion_counts = {} # To store emotion counts per album
        
        for row in data:
            artist = row["_id"]["artist"]
            album = row["_id"]["album"]
            emotion = row["_id"]["emotion"]
            count = row["count"]

            # Dynamically create artist_id and album_id based on whether we are filtering or not.
            # If filtering, the 'artist' in row["_id"]["artist"] will be the selected artist.
            # If not filtering, it will be various artists.
            artist_id = f"artist_{artist.replace(' ', '_').replace('/', '_')}"
            album_id = f"album_{artist.replace(' ', '_').replace('/', '_')}_{album.replace(' ', '_').replace('/', '_')}"
            emotion_id = f"emotion_{artist.replace(' ', '_').replace('/', '_')}_{album.replace(' ', '_').replace('/', '_')}_{emotion.replace(' ', '_').replace('/', '_')}"

            # Artist node
            if artist_id not in artist_map:
                labels.append(artist)
                # If we are filtering, the parent of this artist should be 'all_artists'
                # If not filtering, the parent of each artist should still be 'all_artists'
                parents.append("all_artists")
                values.append(0)
                ids.append(artist_id)
                artist_map[artist_id] = len(labels) - 1 # Store index for value updates
                album_map[artist_id] = {}

            # Album node
            if album_id not in album_map[artist_id]:
                labels.append(album)
                parents.append(artist_id)
                values.append(0)
                ids.append(album_id)
                album_map[artist_id][album_id] = len(labels) - 1 # Store index for value updates

            # Emotion node (leaf)
            labels.append(emotion)
            parents.append(album_id)
            values.append(count)
            ids.append(emotion_id)

            # Store emotion counts per album to determine dominant emotion later
            if album_id not in album_emotion_counts:
                album_emotion_counts[album_id] = defaultdict(int)
            album_emotion_counts[album_id][emotion] += count

            # Update album and artist totals
            album_idx = album_map[artist_id][album_id]
            values[album_idx] += count
            
            artist_idx = artist_map[artist_id]
            values[artist_idx] += count
            
            values[0] += count  # Root node total

        # Determine dominant emotion for each album
        album_dominant_emotions = {}
        for album_id, emotions_counts in album_emotion_counts.items():
            if emotions_counts:
                dominant_emotion = max(emotions_counts, key=emotions_counts.get)
                album_dominant_emotions[album_id] = dominant_emotion

        return jsonify({
            "labels": labels,
            "parents": parents,
            "values": values,
            "ids": ids,
            "album_dominant_emotions": album_dominant_emotions # Add dominant emotions
        })

    except Exception as e:
        print(f"ERROR in artist-album-emotion: {e}")
        return jsonify({"error": str(e)}), 500

# Operational Dashboard Endpoints

# 1. Top/Bottom Performers
@app.route('/api/operational/top-performers')
def top_performers():
    try:
        # Fetch necessary song data from MongoDB
        songs = list(db.song.find(
            {},
            {
                "Song_Title": 1,
                "Artist_Name": 1,
                "Spotify_Popularity_Rank": 1,
                "dominant_emotion": 1,
                "Release_Year": 1
            }
        ).sort("Spotify_Popularity_Rank", -1).limit(20)) # Sort by rank descending, limit to top 20

        # Prepare data for jsonify, ensuring all fields are present
        # Add a placeholder for 'trend arrow' and 'daily snapshots' as they require more complex data storage/retrieval
        formatted_songs = []
        for song in songs:
            formatted_songs.append({
                "Song_Title": song.get("Song_Title", "N/A"),
                "Artist_Name": song.get("Artist_Name", "N/A"),
                "Spotify_Popularity_Rank": song.get("Spotify_Popularity_Rank", 0),
                "Dominant_Emotion": song.get("dominant_emotion", "N/A"),
                "Release_Year": song.get("Release_Year", "N/A"),
                "_id": str(song["_id"]) # Convert ObjectId to string for JSON serialization
            })

        return jsonify(formatted_songs)

    except Exception as e:
        print(f"ERROR in top-performers: {e}")
        return jsonify({"error": str(e)}), 500

# 2. Recent Release Performance (Gauge + Trendline)
@app.route('/api/operational/recent-releases-performance')
def recent_releases_performance():
    try:
        # Fetch recent songs, ordered by release year (descending) and then popularity (descending)
        # We will assume a 'Release_Year' field exists in your song collection
        recent_songs = list(db.song.find(
            {"Release_Year": {"$exists": True, "$ne": None}, "Spotify_Popularity_Rank": {"$exists": True, "$ne": None}},
            {"Release_Year": 1, "Spotify_Popularity_Rank": 1}
        ).sort([("Release_Year", -1), ("Spotify_Popularity_Rank", -1)]).limit(5))

        avg_popularity_last_5 = 0
        if recent_songs:
            avg_popularity_last_5 = np.mean([s.get("Spotify_Popularity_Rank", 0) for s in recent_songs])

        # Mock popularity history for trendline (replace with real data if available)
        popularity_history = [
            {"date": "2024-01-01", "popularity": 65},
            {"date": "2024-01-08", "popularity": 68},
            {"date": "2024-01-15", "popularity": 72},
            {"date": "2024-01-22", "popularity": 70},
            {"date": "2024-01-29", "popularity": avg_popularity_last_5}
        ]

        # Mock week-over-week change (replace with real calculation)
        week_over_week_change = None
        if len(popularity_history) >= 2:
            latest_pop = popularity_history[-1]["popularity"]
            previous_pop = popularity_history[-2]["popularity"]
            if previous_pop != 0:
                week_over_week_change = ((latest_pop - previous_pop) / previous_pop) * 100

        return jsonify({
            "avg_popularity_last_5_releases": round(avg_popularity_last_5, 1),
            "popularity_history": popularity_history,
            "week_over_week_change": round(week_over_week_change, 1) if week_over_week_change is not None else None
        })

    except Exception as e:
        print(f"ERROR in recent-releases-performance: {e}")
        return jsonify({"error": str(e)}), 500

# 3. Emotion Distribution (Donut Chart)
@app.route('/api/operational/emotion-distribution')
def emotion_distribution():
    try:
        songs = list(db.song.find(
            {"dominant_emotion": {"$exists": True, "$ne": None}},
            {"dominant_emotion": 1}
        ))

        emotion_counts = defaultdict(int)
        for song in songs:
            emotion = song.get("dominant_emotion")
            if emotion:
                emotion_counts[emotion] += 1

        total_songs_with_emotion = sum(emotion_counts.values())

        emotions = []
        percentages = []
        colors = []
        emotion_colors = {
            "anger": "#DC143C",  # Crimson
            "love": "#E91E63",     # Deep Pink
            "money": "#388E3C",    # Forest Green
            "violence": "#8B0000", # Blood Red
            "community": "#009688", # Teal
            "sadness": "#303F9F",  # Navy Blue
            "hope": "#81D4FA",     # Sky Blue
            "power": "#6A1B9A",    # Royal Purple
            "joy": "#FFEB3B",      # Golden Yellow
            "surprise": "#FFA726", # Orange
            "confidence": "#00ACC1", # Turquoise
            "fear": "#212121",      # Charcoal Black
            "struggle": "#5D4037",  # Rust Brown
            "aspiration": "#B39DDB", # Lavender
            "neutral": "#BDBDBD"   # Light Gray
        } # Add more as needed

        for emotion, count in emotion_counts.items():
            emotions.append(emotion)
            percentages.append(round((count / total_songs_with_emotion) * 100, 1) if total_songs_with_emotion > 0 else 0)
            colors.append(emotion_colors.get(emotion.lower(), "#CCCCCC")) # Default grey for unknown emotions

        return jsonify({
            "emotions": emotions,
            "percentages": percentages,
            "colors": colors
        })

    except Exception as e:
        print(f"ERROR in emotion-distribution: {e}")
        return jsonify({"error": str(e)}), 500


# 4. Urgent Alerts Panel
@app.route('/api/operational/urgent-alerts')
def urgent_alerts():
    try:
        alerts = []

        # 1. Low Popularity Alert (simplified, as no daily historical data)
        low_rank_threshold = 45
        low_popularity_songs = list(db.song.find(
            {"Spotify_Popularity_Rank": {"$lt": low_rank_threshold}},
            {"Song_Title": 1, "Artist_Name": 1, "Spotify_Popularity_Rank": 1}
        ).sort("Spotify_Popularity_Rank", 1).limit(5)) # Get up to 5 lowest ranked

        for song in low_popularity_songs:
            alerts.append({
                "type": "warning",
                "message": f"⚠️ {song.get("Artist_Name", "N/A")}'s song '<b>{song.get("Song_Title", "N/A")}</b>' has a low rank (now rank={song.get("Spotify_Popularity_Rank", "N/A")})"
            })

        # 2. High Potential Upcoming Release Alert (Leveraging existing logic from upcoming releases)
        # Re-using the logic to calculate producer_avg_ranks
        producer_data = defaultdict(lambda: {'total_rank': 0, 'count': 0})
        for song in db.song.find({"Producer_Name": {"$exists": True, "$ne": None}}, {"Producer_Name": 1, "Spotify_Popularity_Rank": 1}):
            producer = song.get("Producer_Name")
            rank = song.get("Spotify_Popularity_Rank", 0)
            if producer and isinstance(rank, (int, float)):
                producer_data[producer]['total_rank'] += rank
                producer_data[producer]['count'] += 1
        producer_avg_ranks = {p: s['total_rank'] / s['count'] for p, s in producer_data.items() if s['count'] > 0}

        current_year = datetime.now().year # Assuming current year for defining 'upcoming'
        high_potential_upcoming = list(db.song.find(
            {"Release_Year": {"$gte": current_year}},
            {
                "Song_Title": 1, "Artist_Name": 1, "Producer_Name": 1, "Album_Title": 1
            }
        ))
        
        for song in high_potential_upcoming:
            producers = song.get("Producer_Name", "")
            producer_list = [p.strip() for p in producers.split(",") if p.strip()]
            
            is_high_potential = False
            producer_avg_rank_str = "N/A"
            for p in producer_list:
                avg_rank = producer_avg_ranks.get(p, 0)
                if avg_rank >= 70:
                    is_high_potential = True
                    producer_avg_rank_str = str(round(avg_rank, 1))
                    break
            
            if is_high_potential:
                alerts.append({
                    "type": "info",
                    "message": f"🎯 Upcoming: <b>{song.get("Album_Title", "N/A")}</b> by {song.get("Artist_Name", "N/A")} (Producer: {song.get("Producer_Name", "N/A")}, avg. rank={producer_avg_rank_str})"
                })

        return jsonify(alerts)

    except Exception as e:
        print(f"ERROR in urgent-alerts: {e}")
        return jsonify({"error": str(e)}), 500

# 5. Artist Activity Timeline (Gantt Style)
@app.route('/api/operational/artist-activity-timeline')
def artist_activity_timeline():
    try:
        # Fetch necessary song data from MongoDB, focusing on album information
        songs = list(db.song.find(
            {"Release_Year": {"$exists": True, "$ne": None}, "Artist_Name": {"$exists": True, "$ne": None}, "Album_Title": {"$exists": True, "$ne": None}},
            {
                "Artist_Name": 1,
                "Album_Title": 1,
                "Release_Year": 1,
                "Spotify_Popularity_Rank": 1
            }
        ))

        # Group songs by artist and album to create album activities
        album_activities = defaultdict(lambda: {
            'songs': [],
            'release_years': [],
            'popularities': []
        })

        for song in songs:
            artist = song.get("Artist_Name")
            album = song.get("Album_Title")
            release_year = song.get("Release_Year")
            popularity = song.get("Spotify_Popularity_Rank")

            if artist and album and release_year is not None:
                key = (artist, album) # Use tuple as key for unique album activities
                album_activities[key]['songs'].append(song.get("Song_Title", "N/A"))
                album_activities[key]['release_years'].append(release_year)
                if popularity is not None: # Only add if not None
                    album_activities[key]['popularities'].append(popularity)

        formatted_activities = []
        unique_id = 1
        for (artist, album), data in album_activities.items():
            # Determine the primary release year for the album (e.g., the minimum year found)
            album_release_year = min(data['release_years']) if data['release_years'] else "N/A"
            
            # Calculate average popularity for the album
            average_popularity = round(sum(data['popularities']) / len(data['popularities']), 1) if data['popularities'] else 0

            # Filter out 'N/A' song titles before joining for songs_list
            valid_songs = [s for s in data['songs'] if s != "N/A"]

            formatted_activities.append({
                "id": unique_id, # Unique ID for timeline item
                "artist": artist,
                "album_title": album,
                "release_year": album_release_year,
                "average_popularity": average_popularity,
                "song_count": len(data['songs']),
                "songs_list": ", ".join(valid_songs) # Optional: list of songs in the album
            })
            unique_id += 1

        return jsonify(formatted_activities)

    except Exception as e:
        print(f"ERROR in artist-activity-timeline: {e}")
        return jsonify({"error": str(e)}), 500

# Add the new API endpoints from the second file
@app.route('/api/artists')
def get_artists():
    artists = db["artist"].distinct("Artist_Name")
    artists = sorted([a for a in artists if a])
    return jsonify(artists)

@app.route('/api/years')
def get_years():
    years = db["song"].distinct("Release_Year")
    return jsonify(sorted([year for year in years if year is not None]))

@app.route('/api/labels')
def get_labels():
    labels = db["song"].distinct("Label_Name")
    return jsonify(sorted([label for label in labels if label is not None]))

@app.route('/api/artists/metrics')
def get_artist_metrics():
    # Get artist performance metrics
    artist_metrics = list(db["song"].aggregate([
        {"$match": {"Artist_Name": {"$ne": None, "$exists": True}}},
        {
            "$lookup": {
                "from": "song_featured_artist",
                "localField": "Song_Title",
                "foreignField": "Song_Title",
                "as": "featured_artists"
            }
        },
        {
            "$group": {
                "_id": "$Artist_Name",
                "total_songs": {"$sum": 1},
                "avg_popularity": {"$avg": "$Spotify_Popularity_Rank"},
                "collaborations": {"$sum": {"$size": "$featured_artists"}},
                "genres": {"$addToSet": "$Genre_Name"},
                "min_release_year": {"$min": "$Release_Year"},
                "max_release_year": {"$max": "$Release_Year"}
            }
        },
        {
            "$addFields": {
                "years_active": {
                    "$cond": [
                        {"$eq": ["$min_release_year", "$max_release_year"]},
                        1,
                        {"$subtract": ["$max_release_year", "$min_release_year"]} 
                    ]
                }
            }
        },
        {
            "$addFields": {
                "avg_songs_per_year": {
                    "$cond": [
                        {"$eq": ["$years_active", 0]},
                        "$total_songs", 
                        {"$divide": ["$total_songs", "$years_active"]} 
                    ]
                }
            }
        }
    ]))

    # Get emotion distribution
    emotion_metrics = list(db["song"].aggregate([
        {
            "$group": {
                "_id": {
                    "artist": "$Artist_Name",
                    "emotion": "$dominant_emotion"
                },
                "count": {"$sum": 1}
            }
        }
    ]))

    # Get theme distribution
    theme_metrics = list(db["song_theme"].aggregate([
        {
            "$lookup": {
                "from": "song",
                "localField": "Song_Title",
                "foreignField": "Song_Title",
                "as": "song_info"
            }
        },
        {
            "$unwind": "$song_info"
        },
        {
            "$group": {
                "_id": {
                    "artist": "$song_info.Artist_Name",
                    "theme": "$Theme_Name"
                },
                "count": {"$sum": 1}
            }
        }
    ]))

    # Get collaboration network
    collaboration_network = list(db["song_featured_artist"].aggregate([
        {
            "$lookup": {
                "from": "song",
                "localField": "Song_Title",
                "foreignField": "Song_Title",
                "as": "song_info"
            }
        },
        {
            "$unwind": "$song_info"
        },
        {
            "$group": {
                "_id": {
                    "main_artist": "$song_info.Artist_Name",
                    "featured_artist": "$Artist_Name"
                },
                "collaboration_count": {"$sum": 1},
                "avg_popularity": {"$avg": "$song_info.Spotify_Popularity_Rank"}
            }
        }
    ]))

    # Get artist popularity over time (per year)
    artist_popularity_over_time = list(db["song"].aggregate([
        {"$match": {"Artist_Name": {"$ne": None, "$exists": True}, "Release_Year": {"$ne": None, "$exists": True}}},
        {
            "$group": {
                "_id": {
                    "artist": "$Artist_Name",
                    "year": "$Release_Year"
                },
                "avg_popularity": {"$avg": "$Spotify_Popularity_Rank"}
            }
        },
        {"$sort": {"_id.artist": 1, "_id.year": 1}}
    ]))

    # Get label and location impact
    label_location_popularity = list(db["song"].aggregate([
        {"$match": {"Label_Name": {"$ne": None, "$exists": True}, "Location_Name": {"$ne": None, "$exists": True}}},
        {
            "$group": {
                "_id": {
                    "label": "$Label_Name",
                    "location": "$Location_Name"
                },
                "avg_popularity": {"$avg": "$Spotify_Popularity_Rank"}
            }
        },
        {"$sort": {"_id.label": 1, "_id.location": 1}}
    ]))

    return jsonify(json.loads(json_util.dumps({
        "performance": artist_metrics,
        "emotions": emotion_metrics,
        "themes": theme_metrics,
        "collaborations": collaboration_network,
        "artist_popularity_over_time": artist_popularity_over_time,
        "label_location_popularity": label_location_popularity
    })))

@app.route('/api/artists/filter')
def filter_artists():
    artists = request.args.getlist('artists')
    year_range = request.args.get('year_range')
    popularity_threshold = request.args.get('popularity_threshold')
    
    base_match_stage = {}
    if artists:
        base_match_stage["Artist_Name"] = {"$in": artists}
    if year_range:
        start_year, end_year = map(int, year_range.split('-'))
        base_match_stage["Release_Year"] = {"$gte": start_year, "$lte": end_year}
    if popularity_threshold:
        base_match_stage["Spotify_Popularity_Rank"] = {"$lte": int(popularity_threshold)}

    # Define a reusable prefix for pipelines that need the base match
    pipeline_prefix = []
    if base_match_stage:
        pipeline_prefix.append({"$match": base_match_stage})

    # Artist Performance Metrics
    artist_metrics_pipeline = pipeline_prefix + [
        {
            "$lookup": {
                "from": "song_featured_artist",
                "localField": "Song_Title",
                "foreignField": "Song_Title",
                "as": "featured_artists"
            }
        },
        {
            "$group": {
                "_id": "$Artist_Name",
                "total_songs": {"$sum": 1},
                "avg_popularity": {"$avg": "$Spotify_Popularity_Rank"},
                "collaborations": {"$sum": {"$size": "$featured_artists"}},
                "genres": {"$addToSet": "$Genre_Name"},
                "min_release_year": {"$min": "$Release_Year"},
                "max_release_year": {"$max": "$Release_Year"}
            }
        },
        {
            "$addFields": {
                "years_active": {
                    "$cond": [
                        {"$eq": ["$min_release_year", "$max_release_year"]},
                        1,
                        {"$subtract": ["$max_release_year", "$min_release_year"]} 
                    ]
                }
            }
        },
        {
            "$addFields": {
                "avg_songs_per_year": {
                    "$cond": [
                        {"$eq": ["$years_active", 0]},
                        "$total_songs", 
                        {"$divide": ["$total_songs", "$years_active"]} 
                    ]
                }
            }
        }
    ]
    filtered_artist_metrics = list(db["song"].aggregate(artist_metrics_pipeline))

    # Artist Popularity Over Time (per year)
    artist_popularity_over_time_pipeline = pipeline_prefix + [
        {"$group": {
            "_id": {
                "artist": "$Artist_Name",
                "year": "$Release_Year"
            },
            "avg_popularity": {"$avg": "$Spotify_Popularity_Rank"}
        }},
        {"$sort": {"_id.artist": 1, "_id.year": 1}}
    ]
    filtered_artist_popularity_over_time = list(db["song"].aggregate(artist_popularity_over_time_pipeline))

    # Label and Location Impact
    label_location_popularity_pipeline = pipeline_prefix + [
        {"$group": {
            "_id": {
                "label": "$Label_Name",
                "location": "$Location_Name"
            },
            "avg_popularity": {"$avg": "$Spotify_Popularity_Rank"}
        }},
        {"$sort": {"_id.label": 1, "_id.location": 1}}
    ]
    filtered_label_location_popularity = list(db["song"].aggregate(label_location_popularity_pipeline))

    # Collaboration Network (needs to join with song to get artist_name for filtering)
    collaboration_network_pipeline = [
        {
            "$lookup": {
                "from": "song",
                "localField": "Song_Title",
                "foreignField": "Song_Title",
                "as": "song_info"
            }
        },
        {"$unwind": "$song_info"}
    ]
    # Apply base filters to song_info if artist filter is present
    if base_match_stage:
        collaboration_network_pipeline.append({"$match": {"song_info.Artist_Name": base_match_stage.get("Artist_Name", {"$ne": None})}})
        if "Release_Year" in base_match_stage:
             collaboration_network_pipeline.append({"$match": {"song_info.Release_Year": base_match_stage["Release_Year"]}})
        if "Spotify_Popularity_Rank" in base_match_stage:
             collaboration_network_pipeline.append({"$match": {"song_info.Spotify_Popularity_Rank": base_match_stage["Spotify_Popularity_Rank"]}})

    collaboration_network_pipeline.extend([
        {
            "$group": {
                "_id": {
                    "main_artist": "$song_info.Artist_Name",
                    "featured_artist": "$Artist_Name"
                },
                "collaboration_count": {"$sum": 1},
                "avg_popularity": {"$avg": "$song_info.Spotify_Popularity_Rank"}
            }
        }
    ])
    filtered_collaboration_network = list(db["song_featured_artist"].aggregate(collaboration_network_pipeline))

    # Emotion Distribution (needs filtering by Artist_Name if specified)
    emotion_metrics_pipeline = pipeline_prefix + [
        {"$group": {
            "_id": {
                "artist": "$Artist_Name",
                "emotion": "$dominant_emotion"
            },
            "count": {"$sum": 1}
        }}
    ]
    filtered_emotion_metrics = list(db["song"].aggregate(emotion_metrics_pipeline))

    # Theme Distribution (needs filtering by Artist_Name if specified)
    theme_metrics_pipeline = [
        {
            "$lookup": {
                "from": "song",
                "localField": "Song_Title",
                "foreignField": "Song_Title",
                "as": "song_info"
            }
        },
        {"$unwind": "$song_info"}
    ]
    # Apply base filters to song_info if artist filter is present
    if base_match_stage:
        theme_metrics_pipeline.append({"$match": {"song_info.Artist_Name": base_match_stage.get("Artist_Name", {"$ne": None})}})
        if "Release_Year" in base_match_stage:
             theme_metrics_pipeline.append({"$match": {"song_info.Release_Year": base_match_stage["Release_Year"]}})
        if "Spotify_Popularity_Rank" in base_match_stage:
             theme_metrics_pipeline.append({"$match": {"song_info.Spotify_Popularity_Rank": base_match_stage["Spotify_Popularity_Rank"]}})

    theme_metrics_pipeline.extend([
        {"$group": {
            "_id": {
                "artist": "$song_info.Artist_Name",
                "theme": "$Theme_Name"
            },
            "count": {"$sum": 1}
        }}
    ])
    filtered_theme_metrics = list(db["song_theme"].aggregate(theme_metrics_pipeline))

    return jsonify(json.loads(json_util.dumps({
        "performance": filtered_artist_metrics,
        "emotions": filtered_emotion_metrics,
        "themes": filtered_theme_metrics,
        "collaborations": filtered_collaboration_network,
        "artist_popularity_over_time": filtered_artist_popularity_over_time,
        "label_location_popularity": filtered_label_location_popularity
    })))

@app.route('/api/health')
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
