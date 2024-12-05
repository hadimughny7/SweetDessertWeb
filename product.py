import os
from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename

app = Flask(__name__)


UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


os.makedirs(UPLOAD_FOLDER, exist_ok=True)


client = MongoClient("mongodb+srv://test:sparta@cluster0.lf8qu.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client['sweet_dessert']
products_collection = db['products']


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def product_page():
    products = list(products_collection.find())
    return render_template('product.html', products=products)


@app.route('/admin', methods=['GET', 'POST'])
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        product_name = request.form['name']
        product_price = request.form['price']

        if 'image' not in request.files:
            return 'No image file part', 400

        image_file = request.files['image']
        if image_file.filename == '':
            return 'No selected image file', 400

        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)

            new_product = {
                "name": product_name,
                "price": product_price,
                "image": image_path
            }
            products_collection.insert_one(new_product)
            return redirect(url_for('admin'))

    products = list(products_collection.find())
    return render_template('admin.html', products=products)


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


@app.route('/admin/update/<string:product_id>', methods=['GET', 'POST'])
def update_product(product_id):
    product = products_collection.find_one({"_id": ObjectId(product_id)})
    if not product:
        return 'Product not found', 404

    if request.method == 'POST':
        updated_name = request.form['name']
        updated_price = request.form['price']
        
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(image_path)
                
                if 'image' in product:
                    try:
                        os.remove(product['image'])
                    except FileNotFoundError:
                        pass

                product['image'] = image_path

        updated_data = {
            "name": updated_name,
            "price": updated_price,
            "image": product['image']
        }
        products_collection.update_one({"_id": ObjectId(product_id)}, {"$set": updated_data})
        return redirect(url_for('admin'))

    return render_template('edit_product.html', product=product)


if __name__ == '__main__':
    app.run(debug=True)
