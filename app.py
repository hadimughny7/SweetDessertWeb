from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
from bson import ObjectId

app = Flask(__name__)

# Setup MongoDB
client = MongoClient("mongodb+srv://test:sparta@cluster0.lf8qu.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client['sweet_dessert']
products_collection = db['products']

@app.route('/')
def product_page():
    # Ambil data produk dari database
    products = list(products_collection.find())
    return render_template('product.html', products=products)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        # Tambahkan produk baru
        product_name = request.form['name']
        product_price = request.form['price']
        product_image = request.form['image']
        
        # Simpan ke database
        new_product = {
            "name": product_name,
            "price": product_price,
            "image": product_image
        }
        products_collection.insert_one(new_product)
        return redirect(url_for('admin'))

    # Ambil semua produk untuk halaman admin
    products = list(products_collection.find())
    return render_template('admin.html', products=products)

@app.route('/admin/delete/<string:product_id>', methods=['POST'])
def delete_product(product_id):
    # Hapus produk berdasarkan ID
    products_collection.delete_one({"_id": ObjectId(product_id)})
    return redirect(url_for('admin'))

@app.route('/admin/update/<string:product_id>', methods=['GET', 'POST'])
def update_product(product_id):
    if request.method == 'POST':
        # Update produk berdasarkan ID
        updated_data = {
            "name": request.form['name'],
            "price": request.form['price'],
            "image": request.form['image']
        }
        products_collection.update_one({"_id": ObjectId(product_id)}, {"$set": updated_data})
        return redirect(url_for('admin'))

    # Jika GET, tampilkan form dengan data produk yang sudah ada
    product = products_collection.find_one({"_id": ObjectId(product_id)})
    return render_template('edit_product.html', product=product)


if __name__ == '__main__':
    app.run(debug=True)
