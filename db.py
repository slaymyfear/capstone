import pandas as pd
from pymongo import MongoClient

# Read CSV
df = pd.read_csv("send.csv")
data = df.to_dict("records")  # Convert to JSON-like list

# Dump into MongoDB
client = MongoClient("mongodb+srv://whoelsebutv:X39QyOa45NHNWOxc@project.dexlu.mongodb.net/?tls=true")
db = client["capstoneproject"]  # Database name
db["project"].insert_many(data)  # BAM. Done.