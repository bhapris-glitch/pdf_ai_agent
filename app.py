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

# Configure OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

def save_uploaded_file(file):
    filename = str(uuid.uuid4()) + "_" + file.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    return filepath

# --- Existing endpoints omitted for brevity ---

# ----------------------------
# New features implementation
# ----------------------------

@app.route('/merge_pdfs', methods=['POST'])
def merge_pdfs():
    files = request.files.getlist('files')
    if len(files) < 2:
        return jsonify({"error": "Upload at least two PDF files to merge."}), 400
    merger = PdfWriter()
    merged_pdf_path = os.path.join(PROCESSED_FOLDER, f'merged_{uuid.uuid4()}.pdf')
    for file in files:
        file_path = save_uploaded_file(file)
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                merger.add_page(page)
    with open(merged_pdf_path, 'wb') as f_out:
        merger.write(f_out)
    return jsonify({"merged_pdf": merged_pdf_path})

@app.route('/split_pdf', methods=['POST'])
def split_pdf():
    data = request.json
    file_path = data.get('file_path')
    start_page = data.get('start_page', 0)
    end_page = data.get('end_page', None)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    reader = PyPDF2.PdfReader(open(file_path, 'rb'))
    total_pages = len(reader.pages)
    start_page = max(0, start_page)
    end_page = min(end_page if end_page is not None else total_pages, total_pages)
    writer = PdfWriter()
    for i in range(start_page, end_page):
        writer.add_page(reader.pages[i])
    split_path = os.path.join(PROCESSED_FOLDER, f'split_{uuid.uuid4()}.pdf')
    with open(split_path, 'wb') as f:
        writer.write(f)
    return jsonify({"split_pdf": split_path})

@app.route('/convert_to_docx', methods=['POST'])
def convert_to_docx():
    data = request.json
    file_path = data.get('file_path')
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    output_path = os.path.join(PROCESSED_FOLDER, f"{uuid.uuid4()}.docx")
    try:
        cv = Converter(file_path)
        cv.convert(output_path, start=0, end=None)
        cv.close()
        return jsonify({"docx": output_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_password', methods=['POST'])
def add_password():
    data = request.json
    file_path = data.get('file_path')
    password = data.get('password')
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    output_path = os.path.join(PROCESSED_FOLDER, f"protected_{uuid.uuid4()}.pdf")
    with open(file_path, 'rb') as f_in:
        reader = PyPDF2.PdfReader(f_in)
        writer = PyPDF2.PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(password)
        with open(output_path, 'wb') as f_out:
            writer.write(f_out)
    return jsonify({"protected_pdf": output_path})

@app.route('/extract_metadata', methods=['POST'])
def extract_metadata():
    data = request.json
    file_path = data.get('file_path')
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        info = reader.metadata
        num_pages = len(reader.pages)
    return jsonify({"metadata": dict(info), "page_count": num_pages})

@app.route('/ocr_pdf', methods=['POST'])
def ocr_pdf():
    data = request.json
    file_path = data.get('file_path')
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    # Convert PDF pages to images
    pages = convert_from_path(file_path)
    full_text = ''
    for page in pages:
        text = pytesseract.image_to_string(page)
        full_text += text
    return jsonify({"ocr_text": full_text})

# ----------------------------
# Run the app
# ----------------------------

if __name__ == '__main__':
    app.run(debug=True, port=5000)
