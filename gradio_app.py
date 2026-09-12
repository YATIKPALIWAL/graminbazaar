import gradio as gr
import requests
from supabase import create_client
from PIL import Image, ImageEnhance
import urllib.parse
import numpy as np
from PIL import Image,ImageEnhance,ImageFilter

# ==========================================
# 1. CONFIGURATION
# ==========================================
SUPABASE_URL = "https://rldpbncnvjypdvkowzrp.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_PUBLIC_KEY" # Apni poori anon public key yahan paste karein

# Local n8n Webhook URL
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/voice-product"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def enhance_to_studio_image(input_image):
    if input_image is None:
        return None
    from rembg import remove

    if isinstance(input_image, np.ndarray):
        img = Image.fromarray(input_image)
    elif isinstance(input_image, Image.Image):
        img = input_image
    else:
        img = Image.open(input_image)

    target_dim = 1600
    img.thumbnail((target_dim, target_dim), Image.Resampling.LANCZOS)

    cutout = remove(img)
    alpha_mask = cutout.split()[3]

    backdrop = Image.new("RGBA", cutout.size, (244, 246, 248, 255))

    glow_layer = Image.new("RGBA", cutout.size, (255, 255, 255, 0))
    glow_color = Image.new("RGBA", cutout.size, (255, 255, 255, 140))
    glow_mask = alpha_mask.filter(ImageFilter.GaussianBlur(radius=28))
    glow_layer.paste(glow_color, mask=glow_mask)

    backdrop.alpha_composite(glow_layer)
    backdrop.paste(cutout, mask=alpha_mask)
    final_output = backdrop.convert("RGB")

    contrast_engine = ImageEnhance.Contrast(final_output)
    final_output = contrast_engine.enhance(1.28)

    color_engine = ImageEnhance.Color(final_output)
    final_output = color_engine.enhance(1.18)

    final_output = final_output.filter(ImageFilter.UnsharpMask(radius=2.5, percent=130, threshold=3))
    return final_output
# ==========================================
# 2. BACKEND FUNCTIONS
# ==========================================
def process_product_data(image, audio, raw_cost):
    enhanced_image= enhance_to_studio_image(image)
  

    # 2. Voice Note processing via n8n
    title_text = "Handmade Rural Craft"
    desc_text = "Eco-friendly handmade item by village artisan."
    suggested_price = raw_cost * 2

    if audio is not None:
        try:
            with open(audio, 'rb') as f:
                files = {'data': (audio, f, 'audio/wav')}
                res = requests.post(N8N_WEBHOOK_URL, files=files, timeout=120)
                if res.status_code == 200:
                    data = res.json()
                    title_text = data.get('title_hi') or data.get('title_en') or title_text
                    desc_text = data.get('desc_hi') or data.get('desc_en') or desc_text
                    suggested_price = data.get('suggested_price') or suggested_price
        except Exception as e:
            desc_text = f"{desc_text} (AI connection fallback: {e})"

    return enhanced_image, title_text, desc_text, int(suggested_price)

def publish_to_db(name, phone, category, title, desc, price):
    if not name or not phone:
        return "❌ Kripya apna naam aur WhatsApp number zaroor bharein!"
    try:
        clean_price=float(price) if price else 0.0
    except Exception :
        clean_price=0.0    
    
    payload = {
        "artisan_name": str(name).strip(),
        "artisan_phone": str(phone).strip(),
        "category": str(category) if category else "General",
        "title_hi": str(title) if title else "Bina Naam Ka Saman",
        "desc_hi": str(desc) if desc else "",
        "suggested_price": clean_price,
        "image_url": "https://images.unsplash.com/photo-1578749556568-bc2c40e68b61"
    }
    try:
        res= supabase.table("products").insert(payload).execute()
        return "🎉 Badhai! Aapka samaan bazaar me live ho gaya hai!"
    except Exception as e:
        return f"Error: {e}"

def load_marketplace(category_filter):
    res = supabase.table("products").select("*").order("id", desc=True).execute()
    items = res.data or []

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