from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import sqlite3
import os
import requests
import base64 

# Configuration - Add your API keys here
GROQ_KEY = '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'  # Get from https://console.groq.com/keys
HF_TOKEN = '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'   # Get from https://huggingface.co/settings/tokens

app = Flask(__name__)
CORS(app)  # Allow frontend to connect
app.config['UPLOAD_FOLDER'] = 'uploads'

# Database connection
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

# Initialize database
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
    print("✅ Database initialized!")

# Initialize DB on startup
init_db()

# ========== ROUTES ==========

# Get all products
@app.route('/products', methods=['GET'])
def get_products():
    conn = get_db()
    cursor = conn.execute('SELECT * FROM products')
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(products)

# Get single product by ID
@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    conn = get_db()
    cursor = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    conn.close()
    
    if product:
        return jsonify(dict(product))
    return jsonify({'error': 'Product not found'}), 404

# Add new product
@app.route('/add-product', methods=['POST'])
def add_product():
    try:
        # Get image file
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Save image
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Get form data
        data = request.form
        
        # Insert into database
        conn = get_db()
        cursor = conn.execute('''
            INSERT INTO products (name, cat, tag, price, badge, image, description, features)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('name'),
            data.get('cat'),
            data.get('tag'),
            int(data.get('price')),
            data.get('badge', ''),
            filename,
            data.get('description', ''),
            data.get('features', '')
        ))
        conn.commit()
        product_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'message': 'Product added successfully!',
            'id': product_id
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Update product
@app.route('/update-product/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    try:
        data = request.form
        conn = get_db()
        
        # Check if new image uploaded
        if 'image' in request.files and request.files['image'].filename != '':
            file = request.files['image']
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            conn.execute('''
                UPDATE products 
                SET name=?, cat=?, tag=?, price=?, badge=?, image=?, description=?, features=?
                WHERE id=?
            ''', (
                data.get('name'),
                data.get('cat'),
                data.get('tag'),
                int(data.get('price')),
                data.get('badge', ''),
                filename,
                data.get('description', ''),
                data.get('features', ''),
                product_id
            ))
        else:
            # Update without changing image
            conn.execute('''
                UPDATE products 
                SET name=?, cat=?, tag=?, price=?, badge=?, description=?, features=?
                WHERE id=?
            ''', (
                data.get('name'),
                data.get('cat'),
                data.get('tag'),
                int(data.get('price')),
                data.get('badge', ''),
                data.get('description', ''),
                data.get('features', ''),
                product_id
            ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Product updated successfully!'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Delete product
@app.route('/delete-product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        conn = get_db()
        conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Product deleted successfully!'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Serve uploaded images
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Serve frontend images (for demo/fallback)
@app.route('/images/<filename>')
def frontend_images(filename):
    # Images are in backend/images folder (same level as app.py)
    images_path = os.path.join(os.path.dirname(__file__), 'images')
    print(f"🖼️  Looking for image: {filename}")
    print(f"📁 Images path: {images_path}")
    print(f"✅ File exists: {os.path.exists(os.path.join(images_path, filename))}")
    return send_from_directory(images_path, filename)

# Filter products by category
@app.route('/products/category/<cat>', methods=['GET'])
def get_by_category(cat):
    conn = get_db()
    cursor = conn.execute('SELECT * FROM products WHERE cat = ?', (cat,))
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(products)

# Filter products by tag
@app.route('/products/tag/<tag>', methods=['GET'])
def get_by_tag(tag):
    conn = get_db()
    cursor = conn.execute('SELECT * FROM products WHERE tag = ?', (tag,))
    products = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(products)

# Health check & Serve Frontend
@app.route('/')
def home():
    return send_file('../Frontend/art_by_krm_full_app.html')

# AI Chat Proxy (to avoid CORS) - Using Groq API
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        print("Data received:", data)  # 👈 Debug log
        
        # Get system prompt from frontend (includes product context)
        system_prompt = data.get('system', '''You are the AI fashion designer for ART by KRM, a premium handmade Pakistani cultural fashion store. You specialize in Pakistani embroidery styles, mirror work, gota work, cultural patterns, and fashion advice combining traditional Pakistani style with modern aesthetics. Respond warmly in English/Urdu mix. Keep responses under 150 words. Use bullet points. Start with a warm affirmative.

IMPORTANT: If user message contains words like "generate", "show", "create", "make", "visualize", "design", "draw" — you MUST end your response with EXACTLY this on a new line:
[GENERATE_IMAGE: flat lay only, no humans, no models, no mannequin, only fabric/clothing on white background, detailed english prompt]

Rules for image prompt:
- ALWAYS include: "NO PEOPLE, NO MODELS, NO MANNEQUIN"
- Focus on fabric laid flat on white background
- Emphasize embroidery and texture details

Example: "create white embroidered shirt" →
[GENERATE_IMAGE: white Pakistani kameez flat lay on white background, floral embroidery, NO PEOPLE, NO MODELS, NO MANNEQUIN, fabric detail close up, professional product photography]''')
        
        # Add product context instructions if present
        enhanced_prompt = f'''{system_prompt}

IMPORTANT: If user asks to generate/create/show image:
- Use the EXACT same style and type as the current product (if viewing one)
- Only change what user specifically requests (color, embroidery etc)
- Keep everything else same as original product

End with: [GENERATE_IMAGE: exact same garment type as original, only requested changes, Pakistani fashion, flat lay, white background, NO PEOPLE]'''
        
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {GROQ_KEY}'  # Using config variable
            },
            json={
                'model': 'llama-3.3-70b-versatile',
                'messages': [
                    {'role': 'system', 'content': enhanced_prompt}, 
                    {'role': 'user', 'content': data['messages'][0]['content']}
                ],
                'max_tokens': 1000
            }
        )
        
        print("Groq response:", response.status_code, response.text)  # 👈 Debug log
        
        result = response.json()
        # Anthropic format mein convert karo
        return jsonify({
            'content': [{'text': result['choices'][0]['message']['content']}]
        })
    except Exception as e:
        print("ERROR:", str(e))  # 👈 Debug log
        return jsonify({'error': str(e)}), 500

# AI Image Generation (secure - keys hidden in backend)
@app.route('/api/generate-image', methods=['POST'])
def generate_image():
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        print(f"🎨 Generating image for prompt: {prompt}")
        
        # SDXL prompt - better for fashion products
        full_prompt = f'fashion product photography, {prompt}, Pakistani embroidery, clothing only, flat lay, white background, no people, no mannequin, professional catalog, highly detailed'
        
        print(f"📸 SDXL prompt: {full_prompt}")
        
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
        
        print(f"HF Response status: {response.status_code}")
        
        if response.ok:
            import base64
            img_base64 = base64.b64encode(response.content).decode('utf-8')
            print("✅ HuggingFace image generated successfully")
            return jsonify({'image': img_base64})
        
        print(f"❌ HF failed: {response.text}")
        return jsonify({'error': 'HF failed'}), 500
        
    except Exception as e:
        print(f"❌ Image generation ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
