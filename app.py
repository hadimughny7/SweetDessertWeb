import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename
from bson.errors import InvalidId

app = Flask(__name__)

# Konfigurasi untuk upload file
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Koneksi MongoDB
client = MongoClient("mongodb+srv://test:sparta@cluster0.lf8qu.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client['sweet_dessert']
products_collection = db['products']
users_collection = db['users']

# Konfigurasi session
app.secret_key = 'test'  # Gantilah dengan string yang lebih aman

# Fungsi validasi file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Rute Homepage
@app.route("/")
def home():
    return render_template("index.html")

# Rute untuk halaman produk
@app.route("/product")
def product():
    products = list(products_collection.find())
    return render_template("product.html", products=products)

# Rute halaman detail produk
@app.route("/product/<product_id>")
def product_detail(product_id):
    try:
        product = products_collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            abort(404)
        return render_template('product_detail.html', product=product)
    except Exception as e:
        print(f"Error occurred: {e}")
        abort(404)

# Rute untuk halaman admin
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        product_name = request.form['name']
        product_price = request.form['price']
        product_description = request.form['description']
        product_category = request.form['category']

        if 'image' not in request.files or request.files['image'].filename == '':
            return 'No image file part or selected', 400

        image_file = request.files['image']
        if allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)

            new_product = {
                "name": product_name,
                "price": product_price,
                "description": product_description,
                "category": product_category,
                "image": image_path
            }
            products_collection.insert_one(new_product)
            return redirect(url_for('admin'))

    products = list(products_collection.find())
    return render_template('admin.html', products=products)

# Rute untuk menghapus produk
@app.route('/admin/delete/<string:product_id>', methods=['POST'])
def delete_product(product_id):
    product = products_collection.find_one({"_id": ObjectId(product_id)})
    if product:
        if 'image' in product:
            try:
                os.remove(product['image'])
            except FileNotFoundError:
                pass
        products_collection.delete_one({"_id": ObjectId(product_id)})
    return redirect(url_for('admin'))

# Rute untuk memperbarui produk
@app.route('/admin/update/<string:product_id>', methods=['GET', 'POST'])
def update_product(product_id):
    product = products_collection.find_one({"_id": ObjectId(product_id)})
    if not product:
        return 'Product not found', 404

    if request.method == 'POST':
        updated_name = request.form['name']
        updated_price = request.form['price']
        updated_description = request.form['description']
        updated_category = request.form['category']

        if 'image' in request.files:
            image_file = request.files['image']
            if allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(image_path)
                try:
                    os.remove(product['image'])
                except FileNotFoundError:
                    pass
                product['image'] = image_path

        updated_data = {
            "name": updated_name,
            "price": updated_price,
            "description": updated_description,
            "category": updated_category,
            "image": product['image']
        }
        products_collection.update_one({"_id": ObjectId(product_id)}, {"$set": updated_data})
        return redirect(url_for('admin'))

    return render_template('edit_product.html', product=product)

# Rute untuk halaman signup
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        data = request.form
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")

        if not username or not email or not password:
            return render_template("signup.html", error_message='All fields are required.')

        existing_user = users_collection.find_one({"email": email})
        if existing_user:
            return render_template("signup.html", error_message='Email already exists.')

        users_collection.insert_one({"username": username, "email": email, "password": password})
        return render_template("signup.html", success_message='Account successfully created!')

    return render_template("signup.html")

# Rute untuk halaman signin
@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        data = request.form
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return render_template("login.html", error_message='Email and password are required.')

        user = users_collection.find_one({"email": email, "password": password})
        if user:
            session['user_email'] = user['email']
            return render_template("login.html", success_message='Login successful!')  # Kirim pesan sukses

        return render_template("login.html", error_message='Invalid email or password.')  # Kirim pesan error

    return render_template("login.html")


# Rute untuk halaman profil
@app.route("/profile")
def profile():
    # Cek apakah user sudah login dengan memeriksa session
    if 'user_email' not in session:
        return redirect(url_for('signin'))  # Arahkan ke halaman login jika belum login

    # Ambil data pengguna dari session atau database
    user_email = session['user_email']
    user = users_collection.find_one({"email": user_email})

    return render_template("profile.html", user=user)

# Rute untuk logout
@app.route("/logout")
def logout():
    session.pop('user_email', None)  # Menghapus session ketika logout
    return redirect(url_for('home'))  # Arahkan ke halaman utama setelah logout

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/cart")
def cart():
    return render_template("cart.html")

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = request.form.get('product_id')
    # Logika untuk menambahkan produk ke keranjang
    cart = session.get('cart', [])
    cart.append(product_id)
    session['cart'] = cart
    return jsonify({'message': 'Product added to cart successfully!'})

@app.route('/checkout', methods=["GET", "POST"])
def checkout():
    product_id = request.args.get('product_id')
    if not product_id:
        return "Product ID is required", 400

    try:
        # Validasi ObjectId
        product_id = ObjectId(product_id)
    except (InvalidId, ValueError):
        return "Invalid product ID", 400

    product = products_collection.find_one({"_id": product_id})
    if not product:
        return "Product not found", 404

    try:
        quantity = int(request.args.get('quantity', 1))  # Default quantity to 1
    except ValueError:
        return "Invalid quantity value", 400

    subtotal_price = int(product['price']) * quantity
    total_price = subtotal_price

    return render_template('checkout.html', product=product, quantity=quantity, total_price=total_price, subtotal_price=subtotal_price)

@app.route('/invoice', methods=['POST'])
def invoice():
    name = request.form.get('name')
    table_number = request.form.get('tableNumber')
    phone_number = request.form.get('phoneNumber')
    email_address = request.form.get('emailAddress')
    payment_method = request.form.get('paymentMethod')
    
    # Simpan atau olah data sesuai kebutuhan

    # Kirim data ke template invoice.html
    return render_template(
        'invoice.html', 
        name=name, 
        table_number=table_number, 
        phone_number=phone_number, 
        email_address=email_address, 
        payment_method=payment_method, 
        product_name=request.form.get('product_name'),
        quantity=int(request.form.get('quantity', 1)),
        subtotal_price=int(request.form.get('subtotal_price', 0)),
        total_price=int(request.form.get('total_price', 0))
    )

if __name__ == "__main__":
    app.run(debug=True)
