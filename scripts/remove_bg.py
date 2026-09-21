from PIL import Image
import os

img_path = r"C:\Users\Hadi Mughny\Downloads\SweetDessertWeb\static\Logo baru.jpeg"
out_path = r"C:\Users\Hadi Mughny\Downloads\SweetDessertWeb\static\logo_transparent.png"

if not os.path.exists(img_path):
    print("Image not found")
else:
    img = Image.open(img_path).convert("RGBA")
    width, height = img.size
    pixels = img.load()

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            
            # Since the background is black, we check how dark the pixel is
            brightness = max(r, g, b)
            if brightness < 20:
                pixels[x, y] = (0, 0, 0, 0)
            elif brightness < 80:
                alpha = int((brightness - 20) / 60.0 * 255)
                # To prevent it from looking dark, we can boost the RGB slightly
                # But let's just adjust the alpha
                pixels[x, y] = (r, g, b, alpha)

    img.save(out_path)
    print("Success")
