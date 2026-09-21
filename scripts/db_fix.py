import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME = os.environ.get("DB_NAME")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

products_collection = db['products']
users_collection = db['users']

print("Updating products descriptions...")
products = products_collection.find()
for p in products:
    desc = p.get('description', '')
    if len(desc) > 60:
        # Truncate to first sentence or max 60 chars
        first_sentence = desc.split('.')[0]
        if len(first_sentence) > 60:
            short_desc = first_sentence[:57] + '...'
        else:
            short_desc = first_sentence + '.'
            
        products_collection.update_one({'_id': p['_id']}, {'$set': {'description': short_desc}})
        print(f"Truncated: {p['name']}")

print("Deleting all users except admin...")
result = users_collection.delete_many({'email': {'$ne': 'admin@gmail.com'}})
print(f"Deleted {result.deleted_count} non-admin users.")

print("Done.")
