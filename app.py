from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort, flash
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
from os.path import join, dirname
from dotenv import load_dotenv
from bson.errors import InvalidId
from datetime import datetime, timedelta

def get_wib_now():
    return datetime.utcnow() + timedelta(hours=7)

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
    products = list(products_collection.find({'is_recommended': True, 'is_available': {'$ne': False}}))
    return render_template('index.html', current_page='home', products=products)

@app.route('/menus')
def all_menus():
    products = list(products_collection.find({'is_available': {'$ne': False}}))
    return render_template('all_menus.html', current_page='menus', products=products)


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
                    'image': image_path,
                    'is_recommended': False,
                    'is_available': True
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


@app.route('/admin/toggle_recommended/<string:product_id>', methods=['POST'])
@login_required
def toggle_recommended(product_id):
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    is_recommended = data.get('is_recommended', False)
    
    products_collection.update_one({"_id": ObjectId(product_id)}, {"$set": {"is_recommended": is_recommended}})
    return jsonify({'success': True})


@app.route('/admin/toggle_availability/<string:product_id>', methods=['POST'])
@login_required
def toggle_availability(product_id):
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    is_available = data.get('is_available', True)
    
    products_collection.update_one({"_id": ObjectId(product_id)}, {"$set": {"is_available": is_available}})
    return jsonify({'success': True})


@app.route('/admin/set_all_available', methods=['POST'])
@login_required
def set_all_available():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    products_collection.update_many({}, {"$set": {"is_available": True}})
    return jsonify({'success': True})


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
        products = list(products_collection.find({'is_available': {'$ne': False}}))
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

    now = get_wib_now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    
    today_count = invoices_collection.count_documents({
        "created_at": {"$gte": start_of_day, "$lt": end_of_day}
    })
    next_seq = today_count + 1
    order_id = f"ORD-{now.strftime('%y%m%d')}-{next_seq:03d}"

    invoice_data = {
        'order_id': order_id,
        'name': customer_name,
        'table_number': 'POS',
        'phone_number': '-',
        'email_address': '-',
        'payment_method': payment_method,
        'order_details': order_details,
        'total_price': total_price,
        'cash_received': cash_received,
        'change': change,
        'source': 'POS',
        'created_at': now
    }
    
    invoices_collection.insert_one(invoice_data)
    return jsonify({'message': 'POS transaction successful!', 'order_id': order_id}), 200


@app.route('/admin/invoices')
@login_required
def admin_invoices():
    if session.get('role') == 'admin':
        filter_type = request.args.get('filter', 'day')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = {}
        now = get_wib_now()

        if filter_type == 'day':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query['created_at'] = {'$gte': start}
        elif filter_type == 'week':
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            query['created_at'] = {'$gte': start}
        elif filter_type == 'month':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            query['created_at'] = {'$gte': start}
        elif filter_type == 'custom':
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                    query['created_at'] = {'$gte': start, '$lte': end}
                except ValueError:
                    pass
            elif start_date:
                try:
                    start = datetime.strptime(start_date, '%Y-%m-%d')
                    end = start.replace(hour=23, minute=59, second=59)
                    query['created_at'] = {'$gte': start, '$lte': end}
                except ValueError:
                    pass
            elif end_date:
                try:
                    end = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                    query['created_at'] = {'$lte': end}
                except ValueError:
                    pass

        invoices = list(invoices_collection.find(query).sort("created_at", -1))
        return render_template('admin_invoices.html', invoices=invoices, current_page='admin_invoices', filter_type=filter_type, start_date=start_date, end_date=end_date)
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

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('Access denied. Admins only.', 'error')
        return redirect(url_for('home'))

    filter_type = request.args.get('filter', 'month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = {}
    now = get_wib_now()

    if filter_type == 'day':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query['created_at'] = {'$gte': start}
        period_label = 'Hari Ini'
    elif filter_type == 'week':
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        query['created_at'] = {'$gte': start}
        period_label = 'Minggu Ini'
    elif filter_type == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        query['created_at'] = {'$gte': start}
        period_label = 'Bulan Ini'
    elif filter_type == 'custom':
        period_label = 'Custom'
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                query['created_at'] = {'$gte': start, '$lte': end_dt}
                period_label = f'{start_date} s/d {end_date}'
            except ValueError:
                pass
        elif start_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = start.replace(hour=23, minute=59, second=59)
                query['created_at'] = {'$gte': start, '$lte': end_dt}
                period_label = start_date
            except ValueError:
                pass
    else:
        period_label = 'Semua Waktu'

    invoices = list(invoices_collection.find(query))

    # --- Summary Stats ---
    total_revenue = sum(inv.get('total_price', 0) for inv in invoices)
    total_transactions = len(invoices)
    avg_transaction = total_revenue / total_transactions if total_transactions > 0 else 0

    # --- Best Selling Products ---
    product_sales = {}
    for inv in invoices:
        for item in inv.get('order_details', []):
            name = item.get('product_name', 'Unknown')
            qty = item.get('quantity', 0)
            price = item.get('price', 0)
            if name in product_sales:
                product_sales[name]['qty'] += qty
                product_sales[name]['revenue'] += qty * price
            else:
                product_sales[name] = {'qty': qty, 'revenue': qty * price}

    best_sellers = sorted(product_sales.items(), key=lambda x: x[1]['qty'], reverse=True)[:10]

    # --- Payment Method Breakdown ---
    payment_methods = {}
    for inv in invoices:
        method = inv.get('payment_method', 'Unknown')
        if method in payment_methods:
            payment_methods[method]['count'] += 1
            payment_methods[method]['total'] += inv.get('total_price', 0)
        else:
            payment_methods[method] = {'count': 1, 'total': inv.get('total_price', 0)}

    # --- Daily Sales Trend (for chart) ---
    daily_sales = {}
    for inv in invoices:
        date_key = inv.get('created_at')
        if date_key:
            day_str = date_key.strftime('%Y-%m-%d')
            if day_str in daily_sales:
                daily_sales[day_str]['revenue'] += inv.get('total_price', 0)
                daily_sales[day_str]['count'] += 1
            else:
                daily_sales[day_str] = {'revenue': inv.get('total_price', 0), 'count': 1}

    sorted_daily = sorted(daily_sales.items(), key=lambda x: x[0])
    chart_labels = [d[0] for d in sorted_daily]
    chart_revenue = [d[1]['revenue'] for d in sorted_daily]
    chart_count = [d[1]['count'] for d in sorted_daily]

    # --- Source Breakdown (POS vs Online) ---
    source_breakdown = {}
    for inv in invoices:
        source = inv.get('source', 'Online')
        if source in source_breakdown:
            source_breakdown[source]['count'] += 1
            source_breakdown[source]['total'] += inv.get('total_price', 0)
        else:
            source_breakdown[source] = {'count': 1, 'total': inv.get('total_price', 0)}

    # --- Hourly Distribution ---
    hourly_dist = [0] * 24
    for inv in invoices:
        dt = inv.get('created_at')
        if dt:
            hourly_dist[dt.hour] += 1

    return render_template('admin_dashboard.html',
        current_page='dashboard',
        filter_type=filter_type,
        start_date=start_date,
        end_date=end_date,
        period_label=period_label,
        total_revenue=total_revenue,
        total_transactions=total_transactions,
        avg_transaction=avg_transaction,
        best_sellers=best_sellers,
        payment_methods=payment_methods,
        chart_labels=chart_labels,
        chart_revenue=chart_revenue,
        chart_count=chart_count,
        source_breakdown=source_breakdown,
        hourly_dist=hourly_dist
    )


if __name__ == "__main__":
    app.run(debug=True)
