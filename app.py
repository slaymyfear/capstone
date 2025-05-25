from flask import Flask, jsonify, render_template, request, url_for
from flask_cors import CORS
from pymongo import MongoClient
from bson.json_util import dumps
import json
import werkzeug
from datetime import datetime
import os
from dotenv import load_dotenv
from bson import ObjectId
werkzeug.cached_property = werkzeug.utils.cached_property

load_dotenv()

app = Flask(__name__)
CORS(app)

# MongoDB Atlas connection
MONGO_URI = os.getenv('MONGODB_URI', "mongodb+srv://whoelsebutv:X39QyOa45NHNWOxc@project.dexlu.mongodb.net/?tls=true")
client = MongoClient(MONGO_URI)
db = client.get_database('capstoneproject')  # Your database name
songs_collection = db["project"]  # Your collection name

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)

app.json_encoder = JSONEncoder

@app.route('/')
def home():
    return render_template('dashboard1.html')

@app.route('/dashboard1')
def dashboard1():
    return render_template('dashboard1.html')

@app.route('/dashboard2')
def dashboard2():
    return render_template('dashboard2.html')

# API Endpoints for Dashboard 1
@app.route('/api/dashboard1/emotion_trends')
def get_emotion_trends():
    pipeline = [
        {"$match": {"Release Year": {"$exists": True}}},
        {"$group": {
            "_id": {
                "year": "$Release Year",
                "emotion": "$dominant_emotion"
            },
            "count": {"$sum": 1}
        }},
        {"$group": {
            "_id": "$_id.year",
            "emotions": {
                "$push": {
                    "emotion": "$_id.emotion",
                    "count": "$count"
                }
            },
            "total": {"$sum": "$count"}
        }},
        {"$project": {
            "year": "$_id",
            "emotions": {
                "$map": {
                    "input": "$emotions",
                    "as": "e",
                    "in": {
                        "emotion": "$$e.emotion",
                        "percentage": {
                            "$divide": ["$$e.count", "$total"]
                        }
                    }
                }
            }
        }},
        {"$sort": {"year": 1}}
    ]
    
    results = list(songs_collection.aggregate(pipeline))
    return jsonify(results)

@app.route('/api/dashboard1/theme_popularity')
def get_theme_popularity():
    pipeline = [
        {
            "$match": {
                "themes": {"$exists": True, "$ne": "---"},
                "Spotify Popularity Rank": {"$exists": True, "$type": "number"}
            }
        },
        {
            "$addFields": {
                "theme_list": {
                    "$map": {
                        "input": {"$split": ["$themes", ","]},
                        "as": "theme",
                        "in": {"$trim": {"input": "$$theme"}}
                    }
                }
            }
        },
        {"$unwind": "$theme_list"},
        {
            "$group": {
                "_id": "$theme_list",
                "avg_popularity": {"$avg": "$Spotify Popularity Rank"},
                "count": {"$sum": 1}
            }
        },
        {
            "$match": {
                "count": {"$gt": 3}  # Only include themes with more than 3 occurrences
            }
        },
        {
            "$sort": {"avg_popularity": -1}
        },
        {
            "$limit": 15
        }
    ]
    
    try:
        results = list(songs_collection.aggregate(pipeline))
        return jsonify(results)
    except Exception as e:
        print("Error in theme_popularity:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard1/emotion_heatmap')
def get_emotion_heatmap():
    pipeline = [
        {"$match": {"Release Year": {"$exists": True}, "dominant_emotion": {"$exists": True}}},
        {"$group": {
            "_id": {
                "year": "$Release Year",
                "emotion": "$dominant_emotion"
            },
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.year": 1, "_id.emotion": 1}}
    ]
    
    results = list(songs_collection.aggregate(pipeline))
    return jsonify(results)

@app.route('/api/dashboard1/emotion_popularity')
def get_emotion_popularity():
    pipeline = [
        {"$match": {"dominant_emotion": {"$exists": True}, "Spotify Popularity Rank": {"$exists": True}}},
        {"$group": {
            "_id": "$dominant_emotion",
            "avg_popularity": {"$avg": "$Spotify Popularity Rank"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"avg_popularity": -1}}
    ]
    
    results = list(songs_collection.aggregate(pipeline))
    return jsonify(results)

@app.route('/api/dashboard1/artists')
def get_artists():
    artists = songs_collection.distinct("Artist")
    return jsonify(artists)

@app.route('/api/emotions-trend')
def get_emotions_trend():
    try:
        year = request.args.get('year', 'all')
        artist = request.args.get('artist', 'all')
        
        match_stage = {}
        if year != 'all':
            match_stage['release_year'] = int(year)
        if artist != 'all':
            match_stage['artist'] = artist
            
        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})
            
        pipeline.extend([
            {
                "$group": {
                    "_id": {
                        "year": "$release_year",
                        "emotion": "$dominant_emotion"
                    },
                    "count": {"$sum": 1}
                }
            },
            {
                "$group": {
                    "_id": "$_id.year",
                    "emotions": {
                        "$push": {
                            "emotion": "$_id.emotion",
                            "count": "$count"
                        }
                    }
                }
            },
            {"$sort": {"_id": 1}}
        ])
        
        data = list(songs_collection.aggregate(pipeline))
        return jsonify(json.loads(dumps(data)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/themes-popularity')
def get_themes_popularity():
    try:
        theme = request.args.get('theme', 'all')
        popularity_range = request.args.get('popularity', 'all')
        
        match_stage = {}
        if theme != 'all':
            match_stage['themes'] = theme
        if popularity_range != 'all':
            if popularity_range == 'high':
                match_stage['popularity'] = {'$gt': 75}
            elif popularity_range == 'medium':
                match_stage['popularity'] = {'$gte': 25, '$lte': 75}
            elif popularity_range == 'low':
                match_stage['popularity'] = {'$lt': 25}
                
        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})
            
        pipeline.extend([
            {
                "$group": {
                    "_id": "$themes",
                    "avgPopularity": {"$avg": "$popularity"}
                }
            },
            {"$sort": {"avgPopularity": -1}}
        ])
        
        data = list(songs_collection.aggregate(pipeline))
        return jsonify(json.loads(dumps(data)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/emotions-heatmap')
def get_emotions_heatmap():
    try:
        year = request.args.get('year', 'all')
        artist = request.args.get('artist', 'all')
        
        match_stage = {}
        if year != 'all':
            match_stage['release_year'] = int(year)
        if artist != 'all':
            match_stage['artist'] = artist
            
        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})
            
        pipeline.append({
            "$group": {
                "_id": {
                    "year": "$release_year",
                    "emotion": "$dominant_emotion"
                },
                "frequency": {"$sum": 1}
            }
        })
        
        data = list(songs_collection.aggregate(pipeline))
        return jsonify(json.loads(dumps(data)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API Endpoints for Dashboard 2
@app.route('/api/popularity-trends')
def get_popularity_trends():
    try:
        artists = request.args.get('artists', '').split(',')
        year_range = request.args.get('yearRange', 'all')
        
        # Build match stage based on filters
        match_stage = {"Artist": {"$in": artists}} if artists and artists[0] else {}
        
        if year_range != 'all':
            current_year = datetime.now().year
            if year_range == 'last5':
                match_stage['Release Year'] = {'$gte': current_year - 5}
            elif year_range == 'last10':
                match_stage['Release Year'] = {'$gte': current_year - 10}
        
        pipeline = [
            {"$match": match_stage},
            {"$project": {
                "Artist": 1,
                "Song Title": 1,
                "Release Year": 1,
                "Spotify Popularity Rank": 1
            }},
            {"$sort": {"Release Year": 1}}
        ]
        
        results = list(songs_collection.aggregate(pipeline))
        
        # Process data for frontend
        artists_data = {}
        for result in results:
            artist = result['Artist']
            if artist not in artists_data:
                artists_data[artist] = {
                    'name': artist,
                    'popularity_data': []
                }
            artists_data[artist]['popularity_data'].append({
                'x': result['Release Year'],
                'y': result['Spotify Popularity Rank'],
                'title': result['Song Title']  # Updated field name
            })
        
        return jsonify({
            'artists': list(artists_data.values())
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/top-producers')
def get_top_producers():
    try:
        artists = request.args.get('artists', '').split(',')
        year_range = request.args.get('yearRange', 'all')
        
        # Basic query to get all matching documents
        query = {"Artist": {"$in": artists}} if artists and artists[0] else {}
        
        if year_range != 'all':
            current_year = datetime.now().year
            if year_range == 'last5':
                query['Release Year'] = {'$gte': current_year - 5}
            elif year_range == 'last10':
                query['Release Year'] = {'$gte': current_year - 10}

        # Get all matching documents
        documents = list(songs_collection.find(query))
        
        # Process producer data in Python
        producer_stats = {}
        for doc in documents:
            producers = str(doc.get('Producers', '')).split(',')
            for producer in producers:
                producer = producer.strip()
                # Replace 'nan' with 'Sounwave'
                if producer.lower() == 'nan':
                    producer = 'Sounwave'
                if producer and producer != '---':
                    if producer not in producer_stats:
                        producer_stats[producer] = {
                            '_id': producer,
                            'avgPopularity': 0,
                            'songCount': 0,
                            'songs': []
                        }
                    
                    producer_stats[producer]['songs'].append({
                        'title': doc.get('Song Title', ''),
                        'popularity': doc.get('Spotify Popularity Rank', 0),
                        'artist': doc.get('Artist', '')
                    })
                    producer_stats[producer]['songCount'] += 1

        # Calculate averages and filter results
        results = []
        for producer, stats in producer_stats.items():
            if stats['songCount'] >= 2:
                total_popularity = sum(song['popularity'] for song in stats['songs'])
                stats['avgPopularity'] = total_popularity / stats['songCount']
                results.append(stats)

        # Sort by average popularity and limit to top 8
        results.sort(key=lambda x: x['avgPopularity'], reverse=True)
        results = results[:8]

        print("Producer Results:", results)  # Debug print
        return jsonify(results)
    except Exception as e:
        print("Error:", str(e))  # Debug print
        return jsonify({"error": str(e)}), 500

@app.route('/api/featured-artists')
def get_featured_artists():
    try:
        artists = request.args.get('artists', '').split(',')
        year_range = request.args.get('yearRange', 'all')
        
        match_stage = {"Artist": {"$in": artists}} if artists and artists[0] else {}
        
        if year_range != 'all':
            current_year = datetime.now().year
            if year_range == 'last5':
                match_stage['Release Year'] = {'$gte': current_year - 5}
            elif year_range == 'last10':
                match_stage['Release Year'] = {'$gte': current_year - 10}
        
        pipeline = [
            {"$match": match_stage},
            # Split the Featured Artists string into an array
            {"$addFields": {
                "FeaturedArray": {
                    "$split": ["$Featured Artists", ", "]
                }
            }},
            {"$unwind": "$FeaturedArray"},
            {"$group": {
                "_id": "$FeaturedArray",
                "avgPopularity": {"$avg": "$Spotify Popularity Rank"},
                "collaborationCount": {"$sum": 1},
                "songs": {"$push": "$Song Title"}
            }},
            {"$match": {
                "collaborationCount": {"$gt": 1},  # Only include artists with more than 1 collaboration
                "_id": {"$ne": "---"}  # Exclude placeholder values
            }},
            {"$sort": {"avgPopularity": -1}},
            {"$limit": 15}
        ]
        
        results = list(songs_collection.aggregate(pipeline))
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/themes-impact')
def get_themes_impact():
    try:
        artists = request.args.get('artists', '').split(',')
        year_range = request.args.get('yearRange', 'all')
        
        # Basic query to get all matching documents
        query = {"Artist": {"$in": artists}} if artists and artists[0] else {}
        
        if year_range != 'all':
            current_year = datetime.now().year
            if year_range == 'last5':
                query['Release Year'] = {'$gte': current_year - 5}
            elif year_range == 'last10':
                query['Release Year'] = {'$gte': current_year - 10}

        # Get all matching documents
        documents = list(songs_collection.find(query))
        
        # Process theme data
        theme_stats = {}
        for doc in documents:
            themes = str(doc.get('themes', '')).split(',')
            for theme in themes:
                theme = theme.strip()
                if theme and theme != '---':
                    if theme not in theme_stats:
                        theme_stats[theme] = {
                            'theme': theme,
                            'avgPopularity': 0,
                            'songCount': 0,
                            'songs': []
                        }
                    
                    theme_stats[theme]['songs'].append({
                        'title': doc.get('Song Title', ''),
                        'popularity': doc.get('Spotify Popularity Rank', 0),
                        'artist': doc.get('Artist', '')
                    })
                    theme_stats[theme]['songCount'] += 1

        # Calculate averages and prepare results
        results = []
        for theme, stats in theme_stats.items():
            if stats['songCount'] >= 3:  # Only include themes with 3 or more songs
                total_popularity = sum(song['popularity'] for song in stats['songs'])
                stats['avgPopularity'] = total_popularity / stats['songCount']
                results.append({
                    'theme': stats['theme'],
                    'avgPopularity': stats['avgPopularity'],
                    'songCount': stats['songCount'],
                    'songs': sorted(stats['songs'], key=lambda x: x['popularity'], reverse=True)[:3]  # Top 3 songs
                })

        # Sort by average popularity
        results.sort(key=lambda x: x['avgPopularity'], reverse=True)
        results = results[:10]  # Top 10 themes

        print("Theme Results:", results)  # Debug print
        return jsonify(results)
    except Exception as e:
        print("Error:", str(e))  # Debug print
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True) 