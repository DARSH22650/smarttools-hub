from flask import Flask, render_template, request, send_file, session, Response
from PIL import Image, UnidentifiedImageError
from pypdf import PdfWriter, PdfReader
from io import BytesIO
import secrets

app = Flask(__name__)

app.secret_key = secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

COMPRESSED_FILES = {}

BASE_URL = "https://smarttools-hub.onrender.com"


# HOME PAGE
@app.route("/")
def home():
    return render_template("index.html")


# SITEMAP
@app.route("/sitemap.xml")
def sitemap():
    pages = [
        "/",
        "/image-to-pdf",
        "/merge-pdf",
        "/split-pdf",
        "/compress-pdf",
        "/compress-image",
        "/jpg-to-png",
    ]

    urls = "".join(
        f"<url><loc>{BASE_URL}{page}</loc></url>"
        for page in pages
    )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}"
        "</urlset>"
    )

    return Response(
        xml,
        status=200,
        content_type="application/xml; charset=utf-8"
    )


# ROBOTS TXT
@app.route("/robots.txt")
def robots():
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        f"Sitemap: {BASE_URL}/sitemap.xml\n"
    )

    response = Response(
        content,
        status=200,
        content_type="text/plain; charset=utf-8"
    )

    response.headers["Cache-Control"] = (
        "no-cache, no-store, must-revalidate"
    )

    return response


# WEBSITE HEALTH CHECK
@app.route("/health")
def health():
    return {
        "status": "ok",
        "website": "SmartTools Hub"
    }, 200


# IMAGE TO PDF
@app.route("/image-to-pdf", methods=["GET", "POST"])
def image_to_pdf():
    if request.method == "POST":
        files = [
            file for file in request.files.getlist("images")
            if file.filename
        ]

        if not files:
            return render_template(
                "image_to_pdf.html",
                error="Please select at least one image."
            )

        if len(files) > 50:
            return render_template(
                "image_to_pdf.html",
                error="Please select no more than 50 images."
            )

        images = []

        try:
            for file in files:
                image = Image.open(file.stream)

                if image.format not in ("JPEG", "PNG"):
                    image.close()
                    raise ValueError(
                        "Please upload only JPG, JPEG, or PNG images."
                    )

                image.load()
                converted_image = image.convert("RGB")
                image.close()
                images.append(converted_image)

            output = BytesIO()

            images[0].save(
                output,
                format="PDF",
                save_all=True,
                append_images=images[1:]
            )

            output.seek(0)

            return send_file(
                output,
                mimetype="application/pdf",
                as_attachment=True,
                download_name="converted_images.pdf"
            )

        except ValueError as error:
            return render_template(
                "image_to_pdf.html",
                error=str(error)
            )

        except (UnidentifiedImageError, OSError):
            return render_template(
                "image_to_pdf.html",
                error="One or more images are invalid or cannot be opened."
            )

        except Exception:
            app.logger.exception("Image to PDF conversion failed")
            return render_template(
                "image_to_pdf.html",
                error="Conversion failed. Please try different images."
            )

        finally:
            for image in images:
                image.close()

    return render_template("image_to_pdf.html")


# MERGE PDF
@app.route("/merge-pdf", methods=["GET", "POST"])
def merge_pdf():
    if request.method == "POST":
        files = [
            file for file in request.files.getlist("pdfs")
            if file.filename
        ]

        if len(files) < 2:
            return render_template(
                "merge_pdf.html",
                error="Please select at least two PDF files."
            )

        if len(files) > 20:
            return render_template(
                "merge_pdf.html",
                error="Please select no more than 20 PDF files."
            )

        writer = PdfWriter()
        output = BytesIO()

        try:
            for file in files:
                if not file.filename.lower().endswith(".pdf"):
                    return render_template(
                        "merge_pdf.html",
                        error="Please select only PDF files."
                    )

                writer.append(file.stream)

            writer.write(output)
            output.seek(0)

            return send_file(
                output,
                mimetype="application/pdf",
                as_attachment=True,
                download_name="merged_document.pdf"
            )

        except Exception:
            app.logger.exception("PDF merging failed")
            return render_template(
                "merge_pdf.html",
                error=(
                    "Unable to merge these PDFs. Check that they are valid "
                    "and not password-protected."
                )
            )

        finally:
            writer.close()

    return render_template("merge_pdf.html")


# SPLIT PDF
@app.route("/split-pdf", methods=["GET", "POST"])
def split_pdf():
    if request.method == "POST":
        pdf_file = request.files.get("pdf")
        start_page = request.form.get("start_page", type=int)
        end_page = request.form.get("end_page", type=int)

        if not pdf_file or not pdf_file.filename:
            return render_template(
                "split.html",
                error="Please select a PDF file."
            )

        if not pdf_file.filename.lower().endswith(".pdf"):
            return render_template(
                "split.html",
                error="Please upload a PDF file."
            )

        if start_page is None or end_page is None:
            return render_template(
                "split.html",
                error="Please enter both page numbers."
            )

        try:
            reader = PdfReader(pdf_file.stream)

            if reader.is_encrypted:
                return render_template(
                    "split.html",
                    error="Password-protected PDFs are not supported."
                )

            total_pages = len(reader.pages)

            if (
                start_page < 1
                or end_page < start_page
                or end_page > total_pages
            ):
                return render_template(
                    "split.html",
                    error=f"Enter page numbers between 1 and {total_pages}."
                )

            writer = PdfWriter()

            for page_number in range(start_page - 1, end_page):
                writer.add_page(reader.pages[page_number])

            output = BytesIO()
            writer.write(output)
            writer.close()
            output.seek(0)

            return send_file(
                output,
                mimetype="application/pdf",
                as_attachment=True,
                download_name="split_document.pdf"
            )

        except Exception:
            app.logger.exception("PDF splitting failed")
            return render_template(
                "split.html",
                error="Unable to split this PDF. Please try another file."
            )

    return render_template("split.html")


# COMPRESS PDF
@app.route("/compress-pdf", methods=["GET", "POST"])
def compress_pdf():
    if request.method == "POST":
        pdf_file = request.files.get("pdf")

        if not pdf_file or not pdf_file.filename:
            return render_template(
                "compress_pdf.html",
                error="Please select a PDF file."
            )

        if not pdf_file.filename.lower().endswith(".pdf"):
            return render_template(
                "compress_pdf.html",
                error="Please upload a PDF file."
            )

        try:
            original_data = pdf_file.read()

            if not original_data:
                return render_template(
                    "compress_pdf.html",
                    error="The selected file is empty."
                )

            reader = PdfReader(BytesIO(original_data))

            if reader.is_encrypted:
                return render_template(
                    "compress_pdf.html",
                    error="Password-protected PDFs are not supported."
                )

            writer = PdfWriter()

            for page in reader.pages:
                writer.add_page(page)

            for page in writer.pages:
                page.compress_content_streams()

            output = BytesIO()
            writer.write(output)
            writer.close()
            output.seek(0)

            return send_file(
                output,
                mimetype="application/pdf",
                as_attachment=True,
                download_name="compressed_document.pdf"
            )

        except Exception:
            app.logger.exception("PDF compression failed")
            return render_template(
                "compress_pdf.html",
                error="Unable to process this PDF. Please try another file."
            )

    return render_template("compress_pdf.html")


# IMAGE COMPRESSOR
@app.route("/compress-image", methods=["GET", "POST"])
def compress_image():
    if request.method == "POST":
        image_file = request.files.get("image")
        quality = request.form.get("quality", default=60, type=int)

        if not image_file or not image_file.filename:
            return render_template(
                "compress.html",
                error="Please select an image."
            )

        if not image_file.filename.lower().endswith(
            (".jpg", ".jpeg", ".png")
        ):
            return render_template(
                "compress.html",
                error="Please upload a JPG, JPEG, or PNG image."
            )

        if not 20 <= quality <= 95:
            quality = 60

        try:
            original_data = image_file.read()
            original_size = len(original_data)

            if original_size == 0:
                return render_template(
                    "compress.html",
                    error="The selected file is empty."
                )

            with Image.open(BytesIO(original_data)) as source_image:
                if source_image.format not in ("JPEG", "PNG"):
                    return render_template(
                        "compress.html",
                        error="Please upload a valid JPG or PNG image."
                    )

                source_image.load()
                image = source_image.convert("RGB")

            output = BytesIO()

            image.save(
                output,
                format="JPEG",
                quality=quality,
                optimize=True
            )

            image.close()

            compressed_data = output.getvalue()
            output.close()

            compressed_size = len(compressed_data)
            token = secrets.token_urlsafe(24)

            COMPRESSED_FILES[token] = compressed_data
            session["compressed_token"] = token

            return render_template(
                "compress.html",
                original_size=f"{original_size / 1024:.2f} KB",
                compressed_size=f"{compressed_size / 1024:.2f} KB",
                savings=round(
                    (1 - compressed_size / original_size) * 100, 2
                )
            )

        except (UnidentifiedImageError, OSError):
            return render_template(
                "compress.html",
                error="Invalid or unsupported image. Please select another image."
            )

        except Exception:
            app.logger.exception("Image compression failed")
            return render_template(
                "compress.html",
                error="Unable to compress this image. Please try again."
            )

    return render_template("compress.html")


# DOWNLOAD COMPRESSED IMAGE
@app.route("/download-compressed")
def download_compressed():
    token = session.get("compressed_token")
    compressed_data = COMPRESSED_FILES.get(token)

    if not compressed_data:
        return (
            "Your compressed image is no longer available. "
            "Please compress it again.",
            404
        )

    return send_file(
        BytesIO(compressed_data),
        mimetype="image/jpeg",
        as_attachment=True,
        download_name="compressed_image.jpg"
    )


# FILE SIZE ERROR
@app.errorhandler(413)
def file_too_large(error):
    return (
        "Your uploaded files exceed the 50 MB limit. "
        "Please select smaller files.",
        413
    )


# JPG TO PNG
@app.route("/jpg-to-png", methods=["GET", "POST"])
def jpg_to_png():
    if request.method == "POST":
        file = request.files.get("image")

        if not file or file.filename == "":
            return render_template(
                "jpg_to_png.html",
                error="Please select an image."
            )

        try:
            with Image.open(file.stream) as image:
                if image.format != "JPEG":
                    return render_template(
                        "jpg_to_png.html",
                        error="Please upload a JPG or JPEG image."
                    )

                output = BytesIO()
                image.convert("RGB").save(output, format="PNG")
                output.seek(0)

            return send_file(
                output,
                as_attachment=True,
                download_name="converted_image.png",
                mimetype="image/png"
            )

        except (UnidentifiedImageError, OSError):
            return render_template(
                "jpg_to_png.html",
                error="Invalid image. Please upload a valid JPG file."
            )

    return render_template("jpg_to_png.html", error=None)


# RUN WEBSITE LOCALLY
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)