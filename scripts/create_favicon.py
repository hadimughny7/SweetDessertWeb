from PIL import Image

def create_favicon(input_path, output_path):
    # Buka gambar
    img = Image.open(input_path).convert("RGBA")
    
    # Ambil bounding box dari area yang tidak transparan
    bbox = img.getbbox()
    if bbox:
        img_cropped = img.crop(bbox)
        
        # Buat background kotak transparan
        max_size = max(img_cropped.size)
        square_img = Image.new("RGBA", (max_size, max_size), (0, 0, 0, 0))
        
        # Tempelkan gambar yang dicrop ke tengah
        offset = ((max_size - img_cropped.size[0]) // 2, (max_size - img_cropped.size[1]) // 2)
        square_img.paste(img_cropped, offset)
        
        # Resize jadi ukuran wajar untuk favicon (misal 256x256)
        square_img = square_img.resize((256, 256), Image.Resampling.LANCZOS)
        square_img.save(output_path, "PNG")
        print(f"Favicon saved to {output_path}")
    else:
        print("Image is entirely transparent.")

if __name__ == "__main__":
    create_favicon("static/images/logo_transparent.png", "static/images/favicon.png")
