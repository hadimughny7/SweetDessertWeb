from flask import Flask, request, render_template, jsonify, redirect, url_for
import db

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        data = request.form
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")

        if not username or not email or not password:
            return jsonify({'msg': 'Email and password are required'})

        result = db.insert_user(username, email, password)
        if result["status"] == "success":
            return redirect(url_for('home'))  
        return jsonify(result)

    return render_template("signup.html")

@app.route("/signin", methods=["POST"])
def signin():
    data = request.form
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({'msg': 'Invalid email or password'})

    result = db.check_user(email, password)
    if result["status"] == "success":
        return redirect(url_for('index'))  
    return jsonify(result)

@app.route("/index")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
