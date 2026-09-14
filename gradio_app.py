import gradio as gr
import requests
from supabase import create_client
import urllib.parse
import numpy as np
from PIL import Image, ImageEnhance,ImageFilter,ImageDraw
# ==========================================
# 1. CONFIGURATION
# ==========================================
SUPABASE_URL = "https://rldpnbcnvjypdvkuwzrp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJsZHBuYmNudmp5cGR2a3V3enJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkxMTgzNzUsImV4cCI6MjEwNDY5NDM3NX0._s0qUZ8ImcNGUFCQpskDes83uFADNONdPyV3cDsnqgA" # Apni poori anon public key yahan paste karein

# Local n8n Webhook URL
N8N_WEBHOOK_URL = "https://puma-faster-collapse.ngrok-free.dev/webhook/voice-product"

def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def enhance_to_studio_image(input_image):
    if input_image is None:
        return None

    try:
        if isinstance(input_image, np.ndarray):
            img = Image.fromarray(input_image)
        elif isinstance(input_image, Image.Image):
            img = input_image
        else:
            img = Image.open(input_image)

        img = img.convert("RGB")
        img.thumbnail((700, 700), Image.Resampling.LANCZOS)
        w, h = img.size

        # 1. Amazon Clarity & Texture Boost
        img = ImageEnhance.Sharpness(img).enhance(1.4)
        img = ImageEnhance.Contrast(img).enhance(1.18)
        img = ImageEnhance.Color(img).enhance(1.22)

        # 2. Amazon Studio White Backdrop (Clean Light Base)
        canvas = Image.new("RGB", (800, 800), (252, 252, 253))
        offset_x = (800 - w) // 2
        offset_y = (800 - h) // 2

        # 3. Soft Drop Shadow under product
        shadow_mask = Image.new("L", (800, 800), 0)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(shadow_mask)
        draw.ellipse([offset_x + 20, offset_y + h - 15, offset_x + w - 20, offset_y + h + 25], fill=80)
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius=14))

        shadow_layer = Image.new("RGB", (800, 800), (220, 222, 225))
        canvas = Image.composite(shadow_layer, canvas, shadow_mask)

        # 4. Paste Centered Product
        canvas.paste(img, (offset_x, offset_y))
        return canvas
    except Exception as e:
        print(f"Image Enhance Error: {e}")
        return input_image
# ==========================================
# 2. BACKEND FUNCTIONS
# ==========================================
def process_product_data(image, audio, raw_cost):
    enhanced_image= enhance_to_studio_image(image)
  

    # 2. Voice Note processing via n8n
    title_text = "Handmade Rural Craft"
    desc_text = "Eco-friendly handmade item by village artisan."
    suggested_price =int(raw_cost) * 2 if (raw_cost and str(raw_cost).strip()!="") else 150

    if audio is not None:
        try:
            import os
            file_name = os.path.basename(audio) if isinstance(audio, str) else "audio.wav"
            with open(audio, 'rb') as f:
                files = {'data': (file_name, f, 'audio/wav')}
                res = requests.post(N8N_WEBHOOK_URL, files=files, timeout=20)
                if res.status_code == 200:
                    data = res.json()
                    title_text = data.get('title_hi') or data.get('title') or data.get('title_en') or title_text
                    desc_text = data.get('desc_hi') or data.get('description') or data.get('desc_en') or desc_text
                    suggested_price = data.get('suggested_price') or data.get('price') or suggested_price
        except Exception as e:
            desc_text = f"{desc_text} (AI connection fallback: {e})"

    return enhanced_image, title_text, desc_text, int(suggested_price)

def publish_to_db(name, phone, category, title, desc, price):
    if not name or not phone:
        return "❌ Kripya apna naam aur WhatsApp number zaroor bharein!"
    try:
        clean_price = float(price) if price else 0.0
    except Exception:
        clean_price = 0.0    
    
    payload = {
        "artisan_name": str(name).strip(),
        "artisan_phone": str(phone).strip(),
        "category": str(category) if category else "General",
        "title_hi": str(title) if title else "Bina Naam Ka Saman",
        "desc_hi": str(desc) if desc else "",
        "suggested_price": clean_price,
        "image_url": "https://images.unsplash.com/photo-1578749556568-bc2c40e68b61"
    }

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    url = f"{SUPABASE_URL}/rest/v1/products"
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code in [200, 201]:
            return "🎉 Badhai! Aapka samaan bazaar me live ho gaya hai!"
        else:
            return f"Database Error ({r.status_code}): {r.text}"
    except Exception as e:
        return f"Publish Error: {e}"
def load_marketplace(category_filter):
    try:
        client = get_supabase()
        res=client.table("products").select("*").order("id",desc=True).execute()
        items = res.data or []
    except Exception:
        items=[]    

    html_cards = "<div style='display: flex; flex-wrap: wrap; gap: 16px; justify-content: center;'>"
    for item in items:
        cat = item.get('category', 'General')
        if category_filter != "All" and cat != category_filter:
            continue

        title = item.get('title_hi', 'Product')
        desc = item.get('desc_hi', '')
        price = item.get('suggested_price', '0')
        phone = item.get('artisan_phone', '')
        seller = item.get('artisan_name', 'Artisan')
        img = item.get('image_url', 'https://via.placeholder.com/250')

        wa_msg = urllib.parse.quote(f"Namaste {seller}, mujhe aapka '{title}' kharidna hai.")
        wa_link = f"https://wa.me/91{phone}?text={wa_msg}"

        card = f"""
        <div style='border: 1px solid #ddd; border-radius: 10px; padding: 12px; width: 280px; box-shadow: 2px 2px 8px rgba(0,0,0,0.1); background-color: white;'>
            <img src='{img}' style='width: 100%; height: 180px; object-fit: cover; border-radius: 8px;' />
            <h3 style='margin: 8px 0 4px 0; color: #111;'>{title}</h3>
            <p style='font-size: 12px; color: #666; margin: 0;'>By: {seller} | <b>{cat}</b></p>
            <p style='font-size: 13px; color: #444; margin: 8px 0;'>{desc}</p>
            <h4 style='color: #2e7d32; margin: 6px 0;'>₹{price}</h4>
            <div style='margin-top: 10px; display: flex; gap: 8px;'>
                <a href='tel:{phone}' style='text-decoration: none; padding: 6px 12px; background-color: #2196F3; color: white; border-radius: 6px; font-size: 13px;'>📞 Call</a>
                <a href='{wa_link}' target='_blank' style='text-decoration: none; padding: 6px 12px; background-color: #25D366; color: white; border-radius: 6px; font-size: 13px;'>💬 WhatsApp</a>
            </div>
        </div>
        """
        html_cards += card

    html_cards += "</div>"
    return html_cards

# ==========================================
# 3. UI LAYOUT
# ==========================================
with gr.Blocks(title="GraminBazaar") as demo:
    gr.Markdown("# 🌾 GraminBazaar (Micro-Business Direct Linkage)")

    with gr.Tabs():
        # --- TAB 1: SELLER PANEL ---
        with gr.TabItem("👨‍🌾 Seller Panel"):
            gr.Markdown("### Upload Samaan Details via Camera & Voice")
            with gr.Row():
                with gr.Column():
                    seller_name = gr.Textbox(label="Aapka Naam", value="Ramesh Kumar")
                    seller_phone = gr.Textbox(label="WhatsApp Mobile Number", value="9876543210")
                    category = gr.Dropdown(
                        label="Product Category",
                        choices=["Clay Pottery & Crafts", "Handicrafts & Home Decor", "Textiles & Weaving", "Homemade Organic Food", "Other"],
                        value="Clay Pottery & Crafts"
                    )
                    raw_cost = gr.Number(label="Kacchi Samagri ki Laagat (₹)", value=100)
                
                with gr.Column():
                    cam_input = gr.Image(label="Product Photo (Camera/Upload)", sources=["webcam", "upload"], type="numpy")
                    mic_input = gr.Audio(label="Voice Description (Mic/Upload)", sources=["microphone", "upload"], type="filepath")

            gen_btn = gr.Button("✨ Generate AI Catalog & Fair Price", variant="primary")

            with gr.Row():
                enhanced_out = gr.Image(label="Auto-Enhanced Photo")
                with gr.Column():
                    title_out = gr.Textbox(label="Product Title")
                    desc_out = gr.Textbox(label="Product Description", lines=3)
                    price_out = gr.Number(label="Suggested Fair Price (₹)")

            publish_btn = gr.Button("🚀 Publish to Marketplace", variant="stop")
            publish_status = gr.Textbox(label="Status", interactive=False)

            gen_btn.click(
                fn=process_product_data,
                inputs=[cam_input, mic_input, raw_cost],
                outputs=[enhanced_out, title_out, desc_out, price_out]
            )

            publish_btn.click(
                fn=publish_to_db,
                inputs=[seller_name, seller_phone, category, title_out, desc_out, price_out],
                outputs=[publish_status]
            )

        # --- TAB 2: BUYER MARKETPLACE ---
        with gr.TabItem("🛒 Buyer Marketplace"):
            with gr.Row():
                cat_filter = gr.Dropdown(
                    label="Filter Category",
                    choices=["All", "Clay Pottery & Crafts", "Handicrafts & Home Decor", "Textiles & Weaving", "Homemade Organic Food", "Other"],
                    value="All"
                )
                refresh_btn = gr.Button("🔄 Refresh Samaan List")

            market_display = gr.HTML()

            demo.load(fn=load_marketplace, inputs=[cat_filter], outputs=[market_display])
            refresh_btn.click(fn=load_marketplace, inputs=[cat_filter], outputs=[market_display])
            cat_filter.change(fn=load_marketplace, inputs=[cat_filter], outputs=[market_display])

import os

# ==========================================
# 4. LAUNCH (Cloud & Local compatible)
# ==========================================
port = int(os.environ.get("PORT", 7860))
demo.launch(server_name="0.0.0.0", server_port=port)