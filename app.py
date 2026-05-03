from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import sqlite3
import os
import requests
import base64

# Configuration
GROQ_KEY = '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'
HF_TOKEN = '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'

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cat TEXT NOT NULL,
            tag TEXT NOT NULL,
            price INTEGER NOT NULL,
            badge TEXT,
            image TEXT NOT NULL,
            description TEXT,
            features TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    return jsonify({'status': 'ART by KRM API Running!', 'version': '1.0'})

@app.route('/products', methods=['GET'])
def get_products():
    conn = get_db()
    cursor = conn.execute('SELECT * FROM products')
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(products)

@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    conn = get_db()
    cursor = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    conn.close()
    if product:
        return jsonify(dict(product))
    return jsonify({'error': 'Product not found'}), 404

@app.route('/add-product', methods=['POST'])
def add_product():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        data = request.form
        conn = get_db()
        cursor = conn.execute('''
            INSERT INTO products (name, cat, tag, price, badge, image, description, features)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('name'), data.get('cat'), data.get('tag'),
            int(data.get('price')), data.get('badge', ''), filename,
            data.get('description', ''), data.get('features', '')
        ))
        conn.commit()
        product_id = cursor.lastrowid
        conn.close()
        return jsonify({'message': 'Product added!', 'id': product_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete-product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        conn = get_db()
        conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Product deleted!'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/images/<filename>')
def frontend_images(filename):
    images_path = os.path.join(os.path.dirname(__file__), 'images')
    return send_from_directory(images_path, filename)

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        system_prompt = data.get('system', 'You are an AI fashion designer for ART by KRM, a Pakistani handmade fashion store. Respond warmly in English/Urdu mix. Keep responses under 150 words.')
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {GROQ_KEY}'
            },
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': data['messages'][0]['content']}
                ],
                'max_tokens': 1000
            }
        )
        result = response.json()
        return jsonify({
            'content': [{'text': result['choices'][0]['message']['content']}]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-image', methods=['POST'])
def generate_image():
    try:
        data = request.json
        prompt = data.get('prompt', '')
        full_prompt = f'fashion product photography, {prompt}, Pakistani embroidery, flat lay, white background, no people, professional catalog'
        response = requests.post(
            'https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell',
            headers={
                'Authorization': f'Bearer {HF_TOKEN}',
                'Content-Type': 'application/json',
                'x-wait-for-model': 'true'
            },
            json={'inputs': full_prompt},
            timeout=60
        )
        if response.ok:
            img_base64 = base64.b64encode(response.content).decode('utf-8')
            return jsonify({'image': img_base64})
        return jsonify({'error': 'Image generation failed'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Railway uses $PORT automatically with gunicorn
# No need to specify port here