from flask import Flask, request, render_template, jsonify, redirect, url_for
import db

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")  # Ganti 'login.html' menjadi 'index.html'

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
           success_message = "Account successfully created!"
           return render_template("signup.html", success_message=success_message)
        return render_template("signup.html", error_message=result["message"])

    return render_template("signup.html")

@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        data = request.form
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            error_message = "Email and password are required."
            return render_template("login.html", error_message=error_message)

        result = db.check_user(email, password)
        if result["status"] == "success":
            success_message = "Login successful!"
            return render_template("login.html", success_message=success_message)

        error_message = result["message"]
        return render_template("login.html", error_message=error_message)

    return render_template("login.html")


if __name__ == "__main__":
    app.run(debug=True)
