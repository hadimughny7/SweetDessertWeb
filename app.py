from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort, flash
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
from os.path import join, dirname
from dotenv import load_dotenv
from bson.errors import InvalidId

app = Flask(__name__)

# Konfigurasi untuk upload file
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

MONGODB_URI = os.environ.get("MONGODB_URI")
DB_NAME =  os.environ.get("DB_NAME")

client = MongoClient(MONGODB_URI)
db = client[DB_NAME]

products_collection = db['products']
users_collection = db['users']
invoices_collection = db['invoices']

# Konfigurasi session
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_key_123")

# Fungsi validasi file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

## Menambahkan admin secara manual
admin_email = 'admin@gmail.com'
admin_password_plain = 'admin'

admin_user = users_collection.find_one({'email': admin_email})
if not admin_user:
    users_collection.insert_one({
        'username': 'Admin',
        'email': admin_email,
        'password': generate_password_hash(admin_password_plain),  
        'role': 'admin'
    })
    print('Admin account created!')
elif not admin_user['password'].startswith('scrypt:') and not admin_user['password'].startswith('pbkdf2:'):
    # Hash existing plain text password
    users_collection.update_one({'email': admin_email}, {'$set': {'password': generate_password_hash(admin_password_plain)}})
    print('Admin account updated with hashed password.')


def login_required(f):
    def wrapped_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please login as staff to access this page.', 'warning')
            return redirect(url_for('staff_login'))
        return f(*args, **kwargs)
    wrapped_function.__name__ = f.__name__
    return wrapped_function


# ==========================================
# CUSTOMER FACING ROUTES (PUBLIC CATALOG)
# ==========================================

@app.route('/')
def home():
    products = list(products_collection.find())
    return render_template('index.html', current_page='home', products=products)


# ==========================================
# STAFF & ADMIN ROUTES (MANAGEMENT & POS)
# ==========================================

@app.route('/staff', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = users_collection.find_one({'email': email})

        # Check if user exists and password matches
        is_valid = False
        if user:
            if user['password'].startswith('scrypt:') or user['password'].startswith('pbkdf2:'):
                is_valid = check_password_hash(user['password'], password)
            else:
                # Fallback for old plain text passwords, then upgrade it
                if user['password'] == password:
                    is_valid = True
                    users_collection.update_one({'email': email}, {'$set': {'password': generate_password_hash(password)}})

        if is_valid:
            session['user'] = user['username']
            session['role'] = user['role']
            session['user_email'] = user['email']
            flash("Staff login successful!", "success")
            return redirect(url_for('admin')) # Redirect directly to Dashboard for staff
        else:
            flash('Invalid email or password.', 'error')
            return redirect(url_for('staff_login'))

    return render_template('login.html', current_page='staff')



@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('staff_login'))


@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if session.get('role') == 'admin':
        if request.method == 'POST':
            name = request.form.get('name')
            price = request.form.get('price')
            description = request.form.get('description')
            category = request.form.get('category')
            image = request.files.get('image')

            if not name or not price or not description or not category or not image:
                flash('All fields are required!', 'error')
                return redirect(url_for('admin'))
            
            if allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image.save(image_path)

                new_product = {
                    'name': name,
                    'price': price,
                    'description': description,
                    'category': category,
                    'image': image_path
                }
                products_collection.insert_one(new_product)
                flash('Product added successfully!', 'success')
                return redirect(url_for('admin'))

            flash('Invalid file format!', 'error')
            return redirect(url_for('admin'))

        products = list(products_collection.find())
        return render_template('admin.html', products=products, current_page='admin')

    flash('Access denied. Admins only.', 'error')
    return redirect(url_for('home'))


@app.route('/admin/delete/<string:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if session.get('role') != 'admin':
        return redirect(url_for('home'))

    product = products_collection.find_one({"_id": ObjectId(product_id)})
    if product:
        if 'image' in product:
            try:
                os.remove(product['image'])
            except FileNotFoundError:
                pass
        products_collection.delete_one({"_id": ObjectId(product_id)})
        flash('Product deleted successfully!', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/update/<string:product_id>', methods=['GET', 'POST'])
@login_required
def update_product(product_id):
    if session.get('role') != 'admin':
        return redirect(url_for('home'))

    product = products_collection.find_one({"_id": ObjectId(product_id)})
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('admin'))

    if request.method == 'POST':
        updated_name = request.form['name']
        updated_price = request.form['price']
        updated_description = request.form['description']
        updated_category = request.form['category']

        updated_data = {
            "name": updated_name,
            "price": updated_price,
            "description": updated_description,
            "category": updated_category
        }

        if 'image' in request.files and request.files['image'].filename != '':
            image_file = request.files['image']
            if allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(image_path)
                try:
                    if 'image' in product:
                        os.remove(product['image'])
                except FileNotFoundError:
                    pass
                updated_data['image'] = image_path

        products_collection.update_one({"_id": ObjectId(product_id)}, {"$set": updated_data})
        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin'))

    return render_template('edit_product.html', product=product, current_page='admin')


@app.route("/profile")
@login_required
def profile():
    user = users_collection.find_one({"email": session.get('user_email')})
    if user:
        return render_template("profile.html", user=user, current_page='profile')
    return "User not found", 404
    

@app.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    user_email = session.get('user_email')
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')

    if not username or not email:
        flash('Name and email are required!', 'error')
        return redirect(url_for('profile'))

    user_update = {"username": username, "email": email}
    if password:
        user_update["password"] = generate_password_hash(password)
 
    result = users_collection.update_one(
        {"email": user_email},
        {"$set": user_update}
    )
    
    if result.modified_count > 0 or email != user_email:
        if email != user_email:
            session['user_email'] = email
        flash('Profile updated successfully!', 'success')
    else:
        flash('No changes made to the profile.', 'info')
        
    return redirect(url_for('profile'))


@app.route('/admin/pos')
@login_required
def pos():
    if session.get('role') == 'admin':
        products = list(products_collection.find())
        return render_template('pos.html', products=products, current_page='pos')
    flash('Access denied. Admins only.', 'error')
    return redirect(url_for('home'))


@app.route('/api/pos/checkout', methods=['POST'])
@login_required
def api_pos_checkout():
    if session.get('role') != 'admin':
        return jsonify({'message': 'Access denied'}), 403

    data = request.get_json()
    order_details = data.get('order_details', [])
    total_price = data.get('total_price', 0)
    customer_name = data.get('customer_name', 'Customer POS')
    payment_method = data.get('payment_method', 'Cash')
    cash_received = data.get('cash_received', 0)
    change = data.get('change', 0)

    if not order_details or total_price <= 0:
        return jsonify({'message': 'Order is empty or invalid'}), 400

    invoice_data = {
        'name': customer_name,
        'table_number': 'POS',
        'phone_number': '-',
        'email_address': '-',
        'payment_method': payment_method,
        'order_details': order_details,
        'total_price': total_price,
        'cash_received': cash_received,
        'change': change,
        'source': 'POS'
    }
    
    invoices_collection.insert_one(invoice_data)
    return jsonify({'message': 'POS transaction successful!'}), 200


@app.route('/admin/invoices')
@login_required
def admin_invoices():
    if session.get('role') == 'admin':
        invoices = list(invoices_collection.find())
        return render_template('admin_invoices.html', invoices=invoices, current_page='admin_invoices')
    flash('Access denied. Admins only.', 'error')
    return redirect(url_for('home'))


@app.route('/admin/users')
@login_required
def users():
    if session.get('role') == 'admin':
        users_list = list(users_collection.find())
        return render_template('users.html', users=users_list, current_page='users')
    flash('Access denied. Admins only.', 'error')
    return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(debug=True)
