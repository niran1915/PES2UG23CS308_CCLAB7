import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from minio import Minio
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Ensure DB directory exists
BASE_DIR = os.getcwd()
DB_DIR = os.path.join(BASE_DIR, "my_block_data")
os.makedirs(DB_DIR, exist_ok=True)

# Database path
if os.path.exists("/mnt/block_volume"):
    BLOCK_STORAGE_PATH = "/mnt/block_volume/ecommerce.db"
else:
    BLOCK_STORAGE_PATH = os.path.join(DB_DIR, "ecommerce.db")

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{BLOCK_STORAGE_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# MinIO client
minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.getenv("MINIO_ROOT_USER", "admin_user"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD", "admin_password"),
    secure=False
)

# Upload folder
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database Model
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_name = db.Column(db.String(120))


@app.route('/')
def home():
    return "E-commerce Lab is Running! Send a POST request to /product to add data."


@app.route('/product', methods=['POST'])
def add_product():
    try:
        name = request.form.get('name')
        price = request.form.get('price')
        image = request.files.get('image')
        # 1. Define your metadata dictionary
        # Values must be strings
        file_metadata = {
        "x-amz-meta-product-name": str(name),
        "x-amz-meta-product-price": str(price)
}

        # Validate inputs
        if not name or not price:
            return jsonify({"error": "Name and price are required"}), 400

        if not image:
            return jsonify({"error": "No image uploaded"}), 400

        # Convert price
        price = float(price)

        # Secure filename
        filename = secure_filename(image.filename)

        # Save locally
        temp_path = os.path.join(UPLOAD_FOLDER, filename)
        image.save(temp_path)

        # MinIO bucket (MUST be lowercase)
        bucket = "pes2ug23cs308"

        # Create bucket if not exists
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)

        # Upload to MinIO
        minio_client.fput_object( bucket, image.filename, temp_path, metadata=file_metadata)

        # Save to DB
        new_product = Product(
            name=name,
            price=price,
            image_name=filename
        )

        db.session.add(new_product)
        db.session.commit()

        return jsonify({
            "status": "success",
            "msg": "Structured data in Block, Image in Object"
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

    finally:
        # Cleanup temp file
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    print("Starting Flask app on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
