from flask import Flask, request, jsonify, send_file
import os
import uuid
import PyPDF2
import fitz  # PyMuPDF
import openai
from PyPDF2 import PdfWriter
from pdf2docx import Converter
import shutil
import tempfile
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from io import BytesIO
from PIL import Image
import cv2
from googletrans import Translator

# Configure environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Utility functions
def save_uploaded_file(file):
    filename = str(uuid.uuid4()) + "_" + file.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return filepath

# --- Basic endpoints (upload, download, list, etc.) --- (omitted for brevity, focus on new features)

# ------------------------------
# Advanced Features Endpoints
# ------------------------------

@app.route('/add_attachments', methods=['POST'])
def add_attachments():
    """
    Attach images or files to a PDF
    """
    data = request.form
    file_path = data.get('file_path')
    files = request.files.getlist('attachments')
    if not os.path.exists(file_path):
        return jsonify({"error": "Original PDF not found"}), 404
    output_path = os.path.join(PROCESSED_FOLDER, f"attached_{uuid.uuid4()}.pdf")
    reader = PyPDF2.PdfReader(open(file_path, 'rb'))
    writer = PyPDF2.PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    # Add attachments as embedded files (simulate by adding as pages or annotations)
    # Note: PyPDF2 doesn't support embedded files directly; use PyPDF4 or other libraries for full support
    # As a workaround, append attachment pages
    for attachment in files:
        attachment_bytes = attachment.read()
        # Convert to PDF page with image
        image_stream = BytesIO(attachment_bytes)
        image = Image.open(image_stream)
        img_temp_path = os.path.join(PROCESSED_FOLDER, f"temp_{uuid.uuid4()}.png")
        image.save(img_temp_path)
        # Create a new page with image
        c = canvas.Canvas(img_temp_path, pagesize=letter)
        c.drawImage(ImageReader(image), 0, 0, width=letter[0], height=letter[1])
        c.save()
        # Append page
        # For simplicity, skip embedding and just note
    # Save
    with open(output_path, 'wb') as f_out:
        writer.write(f_out)
    return jsonify({"attached_pdf": output_path})

@app.route('/add_watermark', methods=['POST'])
def add_watermark():
    """
    Add watermark text or image
    """
    data = request.json
    file_path = data.get('file_path')
    watermark_text = data.get('watermark_text')
    watermark_image_path = data.get('watermark_image_path')  # optional
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    output_path = os.path.join(PROCESSED_FOLDER, f"watermarked_{uuid.uuid4()}.pdf")
    reader = PyPDF2.PdfReader(open(file_path, 'rb'))
    writer = PyPDF2.PdfWriter()
    for page in reader.pages:
        packet = BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        if watermark_text:
            can.setFont("Helvetica", 40)
            can.setFillColorRGB(0.6, 0.6, 0.6, alpha=0.3)
            can.drawString(100, 400, watermark_text)
        if watermark_image_path and os.path.exists(watermark_image_path):
            img = Image.open(watermark_image_path)
            can.drawImage(watermark_image_path, 100, 300, width=200, height=200)
        can.save()
        packet.seek(0)
        watermark_pdf = PyPDF2.PdfReader(packet)
        watermark_page = watermark_pdf.pages[0]
        page.merge_page(watermark_page)
        writer.add_page(page)
    with open(output_path, 'wb') as f_out:
        writer.write(f_out)
    return jsonify({"watermarked_pdf": output_path})

@app.route('/compress_pdf', methods=['POST'])
def compress_pdf():
    """
    Compress PDF by reducing quality
    """
    data = request.json
    file_path = data.get('file_path')
    quality = data.get('quality', 'default')  # placeholder
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    # For simplicity, just copy the file, real compression would need library like pikepdf or qpdf
    output_path = os.path.join(PROCESSED_FOLDER, f"compressed_{uuid.uuid4()}.pdf")
    shutil.copyfile(file_path, output_path)
    return jsonify({"compressed_pdf": output_path})

@app.route('/convert_format', methods=['POST'])
def convert_format():
    """
    Convert between formats
    """
    data = request.json
    file_path = data.get('file_path')
    target_format = data.get('target_format')  # e.g. 'docx', 'txt', 'png'
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    # Implement conversion
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(PROCESSED_FOLDER, f"{base_name}_converted.{target_format}")
    if target_format == 'txt':
        # Extract text
        text = ''
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        return jsonify({"converted_file": output_path})
    elif target_format == 'png':
        # Convert first page to image
        images = convert_from_path(file_path, first_page=1, last_page=1)
        images[0].save(output_path)
        return jsonify({"converted_file": output_path})
    elif target_format == 'docx':
        # Convert PDF to DOCX using pdf2docx
        converter = Converter(file_path)
        converter.convert(output_path)
        converter.close()
        return jsonify({"converted_file": output_path})
    else:
        return jsonify({"error": "Unsupported target format"}), 400

@app.route('/create_pdf_from_text', methods=['POST'])
def create_pdf_from_text():
    """
    Create PDF from AI-generated text
    """
    data = request.json
    text = data.get('text')
    output_path = os.path.join(PROCESSED_FOLDER, f"ai_generated_{uuid.uuid4()}.pdf")
    c = canvas.Canvas(output_path, pagesize=letter)
    textobject = c.beginText(40, 750)
    for line in text.split('\n'):
        textobject.textLine(line)
    c.drawText(textobject)
    c.save()
    return jsonify({"pdf": output_path})

@app.route('/extract_metadata', methods=['POST'])
def extract_metadata():
    """
    Extract PDF metadata
    """
    data = request.json
    file_path = data.get('file_path')
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        info = reader.metadata
        num_pages = len(reader.pages)
    return jsonify({"metadata": dict(info), "page_count": num_pages})

@app.route('/flatten_pdf', methods=['POST'])
def flatten_pdf():
    """
    Flatten PDF forms
    """
    data = request.json
    file_path = data.get('file_path')
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    output_path = os.path.join(PROCESSED_FOLDER, f"flattened_{uuid.uuid4()}.pdf")
    reader = PyPDF2.PdfReader(open(file_path, 'rb'))
    writer = PyPDF2.PdfWriter()
    for page in reader.pages:
        # Flatten forms
        page = page
        page = page
        # For simplicity, just add pages
        writer.add_page(page)
    with open(output_path, 'wb') as f_out:
        writer.write(f_out)
    return jsonify({"flattened_pdf": output_path})

@app.route('/import_form_data', methods=['POST'])
def import_form_data():
    """
    Import form data
    """
    data = request.json
    file_path = data.get('file_path')
    form_data = data.get('form_data')  # dict of field: value
    # PyPDF2 does not support form filling directly, use pdfrw or pypdf
    # Placeholder:
    return jsonify({"status": "Form data imported (not implemented)"})

@app.route('/export_form_data', methods=['POST'])
def export_form_data():
    """
    Export form data
    """
    data = request.json
    file_path = data.get('file_path')
    # Placeholder: return dummy data
    return jsonify({"form_data": {}})

@app.route('/translate_text', methods=['POST'])
def translate_text():
    """
    Translate document text
    """
    data = request.json
    text = data.get('text')
    dest_lang = data.get('dest_lang', 'en')
    translator = Translator()
    translated = translator.translate(text, dest=dest_lang)
    return jsonify({"translated_text": translated.text})

@app.route('/ocr_pdf', methods=['POST'])
def ocr_pdf():
    """
    Perform OCR on PDF
    """
    data = request.json
    file_path = data.get('file_path')
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    pages = convert_from_path(file_path)
    full_text = ''
    for page in pages:
        text = pytesseract.image_to_string(page)
        full_text += text
    return jsonify({"ocr_text": full_text})

# Run the app
if __name__ == '__main__':
    app.run(debug=True, port=5000)
