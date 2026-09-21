import os
from pymongo import MongoClient
from dotenv import load_dotenv
import datetime

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DB_NAME")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
invoices_collection = db['invoices']

invoices = invoices_collection.find({"created_at": {"$exists": False}})
count = 0
for inv in invoices:
    # generation_time is timezone aware, let's make it naive to match datetime.now() behavior in app
    naive_dt = inv['_id'].generation_time.replace(tzinfo=None)
    invoices_collection.update_one({"_id": inv['_id']}, {"$set": {"created_at": naive_dt}})
    count += 1
print(f"Updated {count} invoices.")
