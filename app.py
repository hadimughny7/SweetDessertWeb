from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename
import os
from bson.errors import InvalidId
import json

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
invoices_collection = db['invoices']
cart_collection = db['carts']

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
    # Mengambil hanya 4 produk dari koleksi 'products'
    products = products_collection.find().limit(4)  # Menambahkan limit(4) untuk mengambil 4 produk pertama

    if 'user' in session:
        # Menampilkan halaman utama dengan data produk dan informasi user
        return render_template('index.html', user=session['user'], current_page='home', products=products)
    
    # Jika user belum login, arahkan ke halaman login
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

    return render_template('login.html',current_page='signin')


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
    
    return render_template('signup.html', current_page='signup')


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
        return render_template('admin.html', products=products, current_page='admin')

    return render_template('index.html', error_message='Access denied. Admins only.')


# Rute untuk halaman produk
@app.route("/product")
@login_required
def product():
    products = list(products_collection.find())
    return render_template("product.html", products=products,current_page='product')

# Rute halaman detail produk
@app.route("/product/<product_id>")
@login_required
def product_detail(product_id):
    try:
        product = products_collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            abort(404)
        return render_template('product_detail.html', product=product ,current_page='product_detail')
    except Exception as e:
        print(f"Error occurred: {e}")
        abort(404)

@app.route('/products/<category>', methods=['GET'])
@login_required
def products_by_category(category):
    print("Kategori yang dipilih:", category)  # Debug kategori dari URL
    products = list(products_collection.find({"category": category}))
    print("Produk ditemukan:", products)  # Debug hasil query
    return render_template('category.html', products=products, category=category)




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
    user = users_collection.find_one({"email": user_email}, )
    print(user)  # Tambahkan log untuk memeriksa apakah user ditemukan
    if user:
        return render_template("profile.html", user=user, current_page='profile')
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
    return render_template("about.html", current_page='about')

@app.route("/contact")
def contact():
    return render_template("contact.html", current_page='contact')

from bson import ObjectId

@app.route('/cart')
@login_required
def cart():
    user_email = session.get('user_email')
    
    if not user_email:
        return redirect(url_for('signin'))  # Jika email pengguna tidak ada di session, redirect ke login
    
    # Ambil cart berdasarkan user_email dari database
    cart_data = cart_collection.find_one({'user_email': user_email})

    if not cart_data:
        return render_template('cart.html', products=[], total_price=0)

    cart = cart_data.get('cart', [])
    products = []
    total_price = 0

    for item in cart:
        product_id = item.get('product_id')

        if not product_id:
            continue

        try:
            product_id = ObjectId(product_id)
        except Exception as e:
            continue

        product = products_collection.find_one({'_id': product_id})

        if product:
            # Konversi price dan quantity menjadi angka
            price = int(product['price'])  # Pastikan price adalah integer
            quantity = int(item.get('quantity', 1))  # Pastikan quantity adalah integer
            
            subtotal_price = price * quantity
            total_price += subtotal_price

            item['name'] = product['name']
            item['price'] = price
            item['quantity'] = quantity
            item['subtotal_price'] = subtotal_price
            products.append(item)
    
    return render_template('cart.html', products=products, total_price=total_price, current_page='cart')




@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    data = request.get_json()
    product_id = data.get('product_id')

    if not product_id:
        return jsonify({'message': 'Product ID is required!'}), 400

    product = products_collection.find_one({'_id': ObjectId(product_id)})

    if not product:
        return jsonify({'message': 'Product not found!'}), 404

    # Ambil cart dari database berdasarkan email pengguna
    user_email = session['user_email']
    cart_data = cart_collection.find_one({'user_email': user_email})

    if cart_data:
        cart = cart_data.get('cart', [])
    else:
        cart = []

    # Cek apakah produk sudah ada dalam cart
    existing_product = next((item for item in cart if item['product_id'] == product_id), None)

    if existing_product:
        existing_product['quantity'] += 1  # Tambahkan quantity jika produk sudah ada
    else:
        cart.append({
            'product_id': product_id,
            'name': product['name'],
            'price': product['price'],
            'quantity': 1
        })

    # Simpan cart ke database berdasarkan email pengguna
    cart_collection.update_one(
        {'user_email': user_email},
        {'$set': {'cart': cart}},
        upsert=True  # Jika tidak ada, buat baru
    )

    return jsonify({'message': 'Product added to cart successfully!'}), 200



@app.route('/update_cart_quantity', methods=['POST'])
@login_required
def update_cart_quantity():
    data = request.get_json()
    product_id = data.get('product_id')
    new_quantity = data.get('quantity')

    if not product_id or not isinstance(new_quantity, int) or new_quantity <= 0:
        return jsonify({'message': 'Invalid product ID or quantity!'}), 400

    # Ambil email pengguna dari sesi
    user_email = session['user_email']

    # Ambil data cart pengguna dari database
    cart_data = cart_collection.find_one({'user_email': user_email})

    if not cart_data:
        return jsonify({'message': 'Cart not found!'}), 404

    cart = cart_data.get('cart', [])

    # Perbarui quantity produk dalam cart
    for product in cart:
        if product['product_id'] == product_id:
            product['quantity'] = new_quantity
            break
    else:
        return jsonify({'message': 'Product not found in cart!'}), 404

    # Simpan perubahan ke database
    cart_collection.update_one(
        {'user_email': user_email},
        {'$set': {'cart': cart}}
    )

    return jsonify({'message': 'Quantity updated successfully!'}), 200

@app.route('/get_cart', methods=['GET'])
@login_required
def get_cart():
    if 'user_email' not in session:
        return jsonify({"error": "User not logged in"}), 400  # Tangani jika user_email tidak ada dalam session
     
    user_email = session['user_email']
    cart_data = cart_collection.find_one({'user_email': user_email}, {'_id': 0, 'cart': 1})
    if cart_data and 'cart' in cart_data:
        return jsonify(cart_data['cart']), 200  # Kembalikan cart jika ada
    return jsonify([]), 200  # Jika cart tidak ada, kembalikan array kosong


# Route untuk menghapus item dari keranjang
@app.route('/remove_from_cart', methods=['POST'])
@login_required
def remove_from_cart():
    data = request.get_json()
    product_id = data.get('product_id')

    if not product_id:
        return jsonify({'message': 'Product ID is required!'}), 400

    user_email = session['user_email']
    cart_data = cart_collection.find_one({'user_email': user_email})

    if not cart_data:
        return jsonify({'message': 'Cart not found!'}), 404

    # Hapus item dari keranjang
    cart = cart_data.get('cart', [])
    updated_cart = [item for item in cart if item['product_id'] != product_id]

    # Update keranjang di database
    cart_collection.update_one(
        {'user_email': user_email},
        {'$set': {'cart': updated_cart}}
    )

    return jsonify({'message': 'Product removed from cart successfully!'}), 200


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

    return render_template('checkout.html', product=product, quantity=quantity, total_price=total_price, subtotal_price=subtotal_price, current_page='checkout')

@app.route('/checkout_cart', methods=['GET', 'POST'])
@login_required
def checkout_cart():
    user_email = session.get('user_email')
    if not user_email:
        return redirect(url_for('signin'))  # Redirect if not logged in
    
    # Get cart data based on the user's email
    cart_data = cart_collection.find_one({'user_email': user_email})
    
    if not cart_data or not cart_data.get('cart'):
        return render_template('cart_empty.html')  # Show empty cart page if no cart items
    
    cart = cart_data.get('cart', [])
    total_price = 0
    order_details = []

    # Loop through each item in the cart to fetch product details and calculate the total
    for item in cart:
        product_id = item.get('product_id')
        product = products_collection.find_one({'_id': ObjectId(product_id)})
        if product:
            price = int(product['price'])
            quantity = int(item.get('quantity', 1))
            subtotal_price = price * quantity
            total_price += subtotal_price

            # Prepare order details for this item
            order_details.append({
                'product_name': product['name'],
                'quantity': quantity,
                'price': price,
                'subtotal_price': subtotal_price
            })
    
    # Prepare the order object
    order = {
        'user_email': user_email,
        'total_price': total_price,
        'order_details': order_details  # List of products in the cart
    }

    # Handle POST request (when user clicks "Place Order")
    if request.method == 'POST':
        payment_method = request.form.get('paymentMethod')
        # Perform additional actions like saving the order to the database or processing payment
        return render_template('checkout_cart.html', cart=cart, total_price=total_price, payment_method=payment_method, order=order, current_page='checkout_cart')

    # For GET request (default behavior)
    return render_template('checkout_cart.html', cart=cart, total_price=total_price, order=order, current_page='checkout_cart')



@app.route('/invoice', methods=['POST'])
def invoice():
    # Mengambil data dari form
    name = request.form.get('name')
    table_number = request.form.get('tableNumber')
    phone_number = request.form.get('phoneNumber')
    email_address = request.form.get('emailAddress')
    payment_method = request.form.get('paymentMethod')

    # Ambil semua produk yang dipesan
    product_names = request.form.getlist('product_name')
    quantities = request.form.getlist('quantity')
    subtotal_prices = request.form.getlist('subtotal_price')
    
    # Menghitung total harga
    order_details = []
    total_price = 0
    
    for i in range(len(product_names)):
        product_name = product_names[i]
        quantity = int(quantities[i])
        subtotal_price = int(subtotal_prices[i])
        
        order_details.append({
            'product_name': product_name,
            'quantity': quantity,
            'subtotal_price': subtotal_price
        })
        
        total_price += subtotal_price

    # Simpan data invoice ke database
    invoice_data = {
        'name': name,
        'table_number': table_number,
        'phone_number': phone_number,
        'email_address': email_address,
        'payment_method': payment_method,
        'order_details': order_details,
        'total_price': total_price
    }
    
    invoices_collection.insert_one(invoice_data)

    # Kirim data ke template invoice.html
    return render_template(
        'invoice.html',
        name=name,
        table_number=table_number,
        phone_number=phone_number,
        email_address=email_address,
        payment_method=payment_method,
        order_details=order_details,
        total_price=total_price,
        current_page='invoice'
    )

@app.route('/admin/invoices')
@login_required
def admin_invoices():
    if 'role' in session and session['role'] == 'admin':
        invoices = list(invoices_collection.find())
        return render_template('admin_invoices.html', invoices=invoices, current_page='admin_invoices')
    return render_template('index.html', error_message='Access denied. Admins only.')



@app.route('/admin/users')
@login_required
def users():
    if 'role' in session and session['role'] == 'admin':
        users = list(users_collection.find())
        return render_template('users.html', users=users, current_page='users')
    return render_template('index.html', error_message='Access denied. Admins only.')






if __name__ == "__main__":
    app.run(debug=True)
