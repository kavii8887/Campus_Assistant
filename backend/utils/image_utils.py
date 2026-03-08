from PIL import Image, ImageEnhance
import io

def preprocess_image(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    if image.width > 2000:
        ratio = 2000 / image.width
        image = image.resize(
            (int(image.width * ratio), int(image.height * ratio))
        )

    image = ImageEnhance.Contrast(image).enhance(1.6)
    image = ImageEnhance.Sharpness(image).enhance(1.8)

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=95)
    return buf.getvalue()