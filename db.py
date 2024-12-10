from pymongo import MongoClient

client = MongoClient("mongodb+srv://test:sparta@cluster0.lf8qu.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["sweet_dessert"]
user_collection = db["users"]

def insert_user(username, email, password):
    if user_collection.find_one({"email": email}):
        return {"status": "error", "message": "Email already registered"}
    user_collection.insert_one({"username": username, "email": email, "password": password})
    return {"status": "success", "message": "User registered successfully"}

def check_user(email, password):
    user = user_collection.find_one({"email": email, "password": password})
    if user:
        return {"status": "success", "message": "Login successful", "username": user["username"]}
    return {"status": "error", "message": "Invalid email or password"}
