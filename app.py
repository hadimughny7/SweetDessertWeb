from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename
import os
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

## Menambahkan admin secara manual
admin_email = 'admin@gmail.com'
admin_password = 'admin'

# Mengecek apakah akun admin sudah ada
if not users_collection.find_one({'email': admin_email}):
    users_collection.insert_one({
        'username': 'Admin',
        'email': admin_email,
        'password': admin_password,  
        'role': 'admin'
    })
    print('Admin account created!')
else:
    print('Admin account already exists.')


def login_required(f):
    def wrapped_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('signin'))  # Arahkan ke login jika belum login
        return f(*args, **kwargs)
    
    # Pastikan nama fungsi tetap berbeda
    wrapped_function.__name__ = f.__name__
    return wrapped_function



@app.route('/')
def home():
    if 'user' in session:
        return render_template('index.html', user=session['user'])
    return redirect(url_for('signin'))

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = users_collection.find_one({'email': email})

        if user and user['password'] == password:  # Langsung cocokkan password
            session['user'] = user['username']
            session['role'] = user['role']
            session['user_email'] = user['email']

            success_message = "Login successful!"  # Pesan sukses
            return render_template('login.html', success_message=success_message)

        else:
            error_message = 'Invalid email or password.'  # Pesan error
            return render_template('login.html', error_message=error_message)

    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = 'admin' if email == 'admin@gmail.com' else 'user'  # Role admin jika email admin

        if users_collection.find_one({'email': email}):
            # Jika email sudah ada, tetap di halaman signup dan tampilkan pesan error
            return render_template('signup.html', error_message='Email already exists!')
        else:
            users_collection.insert_one({
                'username': username,
                'email': email,
                'password': password, 
                'role': role
            })
            # Jika berhasil, tampilkan pesan sukses dan tetap di halaman signup
            return render_template('signup.html', success_message='Account successfully created!')
    
    return render_template('signup.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('role', None)  # Hapus role dari sesi
    session.pop('user_email', None)  # Hapus email dari sesi
    return redirect(url_for('signin'))

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if 'role' in session and session['role'] == 'admin':
        if request.method == 'POST':
            # Ambil data dari form
            name = request.form.get('name')
            price = request.form.get('price')
            description = request.form.get('description')
            category = request.form.get('category')
            image = request.files.get('image')

            # Validasi input
            if not name or not price or not description or not category or not image:
                return render_template('admin.html', products=list(products_collection.find()), 
                                       error_message="All fields are required!")
            
            if allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image.save(image_path)

                # Simpan data ke MongoDB
                new_product = {
                    'name': name,
                    'price': price,
                    'description': description,
                    'category': category,
                    'image': image_path
                }
                products_collection.insert_one(new_product)
                return redirect(url_for('admin'))

            return render_template('admin.html', products=list(products_collection.find()), 
                                   error_message="Invalid file format!")

        # GET: Tampilkan halaman admin
        products = list(products_collection.find())
        return render_template('admin.html', products=products)

    return render_template('index.html', error_message='Access denied. Admins only.')


# Rute untuk halaman produk
@app.route("/product")
@login_required
def product():
    products = list(products_collection.find())
    return render_template("product.html", products=products)

# Rute halaman detail produk
@app.route("/product/<product_id>")
@login_required
def product_detail(product_id):
    try:
        product = products_collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            abort(404)
        return render_template('product_detail.html', product=product)
    except Exception as e:
        print(f"Error occurred: {e}")
        abort(404)

# Rute untuk menghapus produk
@app.route('/admin/delete/<string:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if session['role'] != 'admin':
        return redirect(url_for('home'))  # Arahkan ke halaman utama jika bukan admin

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
@login_required
def update_product(product_id):
    if session['role'] != 'admin':
        return redirect(url_for('home'))  # Arahkan ke halaman utama jika bukan admin

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

@app.route("/profile")
@login_required
def profile():
    user_email = session.get('user_email')
    user = users_collection.find_one({"email": user_email})
    print(user)  # Tambahkan log untuk memeriksa apakah user ditemukan
    if user:
        return render_template("profile.html", user=user)
    else:
        # Menangani jika user tidak ditemukan
        return "User not found"
    

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user_email = session.get('user_email')
    if not user_email:
        return redirect(url_for('signin'))
    
    # Ambil data dari form
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')

    # Validasi input (opsional)
    if not username or not email:
        return "Name and email are required!", 400

    # Update database
    user_update = {"username": username, "email": email}
    if password:  # Jika password diisi, tambahkan ke pembaruan
        user_update["password"] = password
 

    result = users_collection.update_one(
        {"email": user_email},
        {"$set": user_update}
    )
    
    if result.modified_count > 0:
        # Update session jika email berubah
        if email != user_email:
            session['user_email'] = email
        return redirect(url_for('profile'))
    else:
        return "No changes made to the profile.", 400



@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

from bson import ObjectId

@app.route('/cart')
def cart():
    cart = session.get('cart', [])  # Ambil cart dari sesi
    products = []

    for item in cart:
        product_id = item.get('product_id')  # Ambil product_id dari cart, bukan _id

        if not product_id:
            continue  # Jika tidak ada product_id, lewati item ini
        
        try:
            # Konversi product_id ke ObjectId untuk pencarian di MongoDB
            product_id = ObjectId(product_id)
        except Exception as e:
            print(f"Invalid product _id format: {product_id}")
            continue  # Lewatkan item dengan format _id yang tidak valid

        # Cari produk berdasarkan _id
        product = products_collection.find_one({'_id': product_id})

        if product:
            # Jika produk ditemukan, tambahkan informasi ke dalam item
            item['name'] = product['name']
            item['price'] = product['price']
            products.append(item)
        else:
            print(f"Product with _id {product_id} not found")

    return render_template('cart.html', products=products)



@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    data = request.get_json()  # Ambil data dalam format JSON
    product_id = data.get('product_id')  # Ambil product_id dari JSON

    if not product_id:
        return jsonify({'message': 'Product ID is required!'}), 400

    # Ambil produk dari database menggunakan product_id
    product = products_collection.find_one({'_id': product_id})  # Mengambil produk berdasarkan ID

    if not product:
        return jsonify({'message': 'Product not found!'}), 404
    cart = session.get('cart', [])

    existing_product = next((item for item in cart if item['product_id'] == product_id), None)

    if existing_product:

        existing_product['quantity'] += 1
    else:

        cart.append({
            'product_id': product_id,
            'name': product['name'],
            'price': product['price'],
            'quantity': 1
        })

    session['cart'] = cart

    return jsonify({'message': 'Product added to cart successfully!'}), 200



@login_required
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
