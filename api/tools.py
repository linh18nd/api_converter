import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
from PyPDF2 import PdfFileWriter
from PIL import Image
import pytesseract
from PyPDF2 import PdfFileWriter, PdfFileReader, PdfFileMerger
from pdf2image import convert_from_path
import img2pdf

DEFAULT_JPEG_QUALITY = 85
DEFAULT_PNG_QUALITY = 6
DEFAULT_EXECUTOR = ThreadPoolExecutor()


def save_upload_file(upload_file, destination):
    try:
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    finally:
        upload_file.file.close()


def ocr_pdf(input_pdf, output_pdf, lang='eng'):
    pdf_document = PdfFileReader(input_pdf)
    pdf_output = PdfFileWriter()

    for page_number in range(pdf_document.getNumPages()):
        page = pdf_document.getPage(page_number)
        text = ocr_page(page, lang)
        pdf_page = pdf_output.addPage(page)
        pdf_page.mergePage(page)
        pdf_page.addText(10, 10, text)

    with open(output_pdf, 'wb') as output_file:
        pdf_output.write(output_file)


def ocr_page(page, lang='eng'):
    image = page.extractText()
    temp_image = NamedTemporaryFile(delete=False, suffix='.png')

    image.save(temp_image.name, format="PNG")

    text = pytesseract.image_to_string(Image.open(temp_image.name), lang=lang)
    os.remove(temp_image.name)

    return text


def convert_image_pdf(input_image, output_pdf):
    # Convert image to PDF
    img_list = convert_from_path(input_image, single_file=True)
    img_pdf = img2pdf.convert(img_list)

    # Save the PDF
    with open(output_pdf, 'wb') as pdf_file:
        pdf_file.write(img_pdf)


def create_overlay(input_pdf, overlay_text, overlay_image, output_pdf):
    pdf_document = PdfFileReader(input_pdf)
    pdf_output = PdfFileWriter()

    for page_number in range(pdf_document.getNumPages()):
        page = pdf_document.getPage(page_number)

        pdf_page = pdf_output.addPage(page)
        pdf_page.mergePage(page)

        # Add text overlay
        pdf_page.addText(100, 100, overlay_text)
        bounding_boxes = pytesseract.image_to_boxes(Image.frombytes(
            "RGB", (image.width, image.height), image.samples))

        # Tạo trang mới với kích thước tương đương
        pdf_page = pdf_output.new_page(
            width=page.rect.width, height=page.rect.height)
        pdf_page.show_pdf_page(
            rect=pdf_page.rect, src_doc=pdf_document, page_number=page_number)

        # Add image overlay
        pdf_page.addImage(overlay_image, 200, 200, width=100, height=100)

    with open(output_pdf, 'wb') as output_file:
        pdf_output.write(output_file)


def optimize(input_file, output_file):
    # Your existing optimize function
    pass


def main(infile, outfile, level, jobs=1, lang='eng'):
    infile = Path(infile)
    outfile = Path(outfile)

    with DEFAULT_EXECUTOR as executor:
        if infile.suffix.lower() in ['.jpg', '.jpeg', '.png']:
            # Convert image to PDF
            convert_image_pdf(infile, outfile)
        else:
            # OCR and create PDF/A
            with tempfile.TemporaryDirectory() as tempdir:
                temp_pdf = Path(tempdir) / 'temp.pdf'
                ocr_pdf(infile, temp_pdf, lang)
                optimize(temp_pdf, outfile, level, jobs)


def _find_deflatable_jpeg(
    *, pdf: Pdf, root: Path, image: Stream, xref: Xref, options
) -> XrefExt | None:
    result = extract_image_filter(image, xref)
    if result is None:
        return None
    _pim, filtdp = result

    if filtdp[0] == Name.DCTDecode and not filtdp[1] and options.optimize >= 1:
        return XrefExt(xref, '.memory')

    return None


def _deflate_jpeg(
    pdf: Pdf, lock: threading.Lock, xref: Xref, complevel: int
) -> tuple[Xref, bytes]:
    with lock:
        xobj = pdf.get_object(xref, 0)
        try:
            data = xobj.read_raw_bytes()
        except PdfError:
            return xref, b''
    compdata = compress(data, complevel)
    if len(compdata) >= len(data):
        return xref, b''
    return xref, compdata


def deflate_jpegs(pdf: Pdf, root: Path, options, executor: Executor) -> None:
    """Apply FlateDecode to JPEGs.

    This is a lossless compression method that is supported by all PDF viewers,
    and generally results in a smaller file size compared to straight DCTDecode
    images.
    """
    jpegs = []
    for _pageno, xref_ext in extract_images(pdf, root, options, _find_deflatable_jpeg):
        xref = xref_ext.xref
        log.debug(f'xref {xref}: marking this JPEG as deflatable')
        jpegs.append(xref)

    complevel = 9 if options.optimize == 3 else 6

    # Our calls to xobj.write() in finish() need coordination
    lock = threading.Lock()

    def deflate_args() -> Iterator:
        for xref in jpegs:
            yield pdf, lock, xref, complevel

    def finish(result: tuple[Xref, bytes], pbar: ProgressBar):
        xref, compdata = result
        if len(compdata) > 0:
            with lock:
                xobj = pdf.get_object(xref, 0)
                xobj.write(compdata, filter=[Name.FlateDecode, Name.DCTDecode])
        pbar.update()

    executor(
        use_threads=True,  # We're sharing the pdf directly, must use threads
        max_workers=options.jobs,
        progress_kwargs=dict(
            desc="Deflating JPEGs",
            total=len(jpegs),
            unit='image',
            disable=not options.progress_bar,
        ),
        task=_deflate_jpeg,
        task_arguments=deflate_args(),
        task_finished=finish,
    )


def _transcode_png(pdf: Pdf, filename: Path, xref: Xref) -> bool:
    output = filename.with_suffix('.png.pdf')
    with output.open('wb') as f:
        img2pdf.convert(fspath(filename), outputstream=f, **IMG2PDF_KWARGS)

    with Pdf.open(output) as pdf_image:
        foreign_image = next(iter(pdf_image.pages[0].images.values()))
        local_image = pdf.copy_foreign(foreign_image)

        im_obj = pdf.get_object(xref, 0)
        im_obj.write(
            local_image.read_raw_bytes(),
            filter=local_image.Filter,
            decode_parms=local_image.DecodeParms,
        )

        # Don't copy keys from the new image...
        del_keys = set(im_obj.keys()) - set(local_image.keys())
        # ...except for the keep_fields, which are essential to displaying
        # the image correctly and preserving its metadata. (/Decode arrays
        # and /SMaskInData are implicitly discarded prior to this point.)
        keep_fields = {
            '/ID',
            '/Intent',
            '/Interpolate',
            '/Mask',
            '/Metadata',
            '/OC',
            '/OPI',
            '/SMask',
            '/StructParent',
        }
        del_keys -= keep_fields
        for key in local_image.keys():
            if key != Name.Length and str(key) not in keep_fields:
                im_obj[key] = local_image[key]
        for key in del_keys:
            del im_obj[key]
    return True


def transcode_pngs(
    pdf: Pdf,
    images: Sequence[Xref],
    image_name_fn: Callable[[Path, Xref], Path],
    root: Path,
    options,
    executor: Executor,
) -> None:
    """Apply lossy transcoding to PNGs."""
    modified: MutableSet[Xref] = set()
    if options.optimize >= 2:
        png_quality = (
            max(10, options.png_quality - 10),
            min(100, options.png_quality + 10),
        )

        def pngquant_args():
            for xref in images:
                log.debug(image_name_fn(root, xref))
                yield (
                    image_name_fn(root, xref),
                    png_name(root, xref),
                    png_quality[0],
                    png_quality[1],
                )
                modified.add(xref)

        executor(
            use_threads=True,
            max_workers=options.jobs,
            progress_kwargs=dict(
                desc="PNGs",
                total=len(images),
                unit='image',
                disable=not options.progress_bar,
            ),
            task=pngquant.quantize,
            task_arguments=pngquant_args(),
        )

    for xref in modified:
        filename = png_name(root, xref)
        _transcode_png(pdf, filename, xref)


DEFAULT_EXECUTOR = SerialExecutor()


def optimize(
    input_file: Path,
    output_file: Path,
    context: PdfContext,
    save_settings: dict[str, Any],
    executor: Executor = DEFAULT_EXECUTOR,
) -> Path:
    """Optimize images in a PDF file."""
    options = context.options
    if options.optimize == 0:
        safe_symlink(input_file, output_file)
        return output_file

    if options.jpeg_quality == 0:
        options.jpeg_quality = DEFAULT_JPEG_QUALITY if options.optimize < 3 else 40
    if options.png_quality == 0:
        options.png_quality = DEFAULT_PNG_QUALITY if options.optimize < 3 else 30
    if options.jbig2_page_group_size == 0:
        options.jbig2_page_group_size = 10 if options.jbig2_lossy else 1

    with Pdf.open(input_file) as pdf:
        root = output_file.parent / 'images'
        root.mkdir(exist_ok=True)

        jpegs, pngs = extract_images_generic(pdf, root, options)
        transcode_jpegs(pdf, jpegs, root, options, executor)
        deflate_jpegs(pdf, root, options, executor)
        # if options.optimize >= 2:
        # Try pngifying the jpegs
        #    transcode_pngs(pdf, jpegs, jpg_name, root, options)
        transcode_pngs(pdf, pngs, png_name, root, options, executor)

        jbig2_groups = extract_images_jbig2(pdf, root, options)
        convert_to_jbig2(pdf, jbig2_groups, root, options, executor)

        target_file = output_file.with_suffix('.opt.pdf')
        pdf.remove_unreferenced_resources()
        pdf.save(target_file, **save_settings)

    input_size = input_file.stat().st_size
    output_size = target_file.stat().st_size
    if output_size == 0:
        raise OutputFileAccessError(
            f"Output file not created after optimizing. We probably ran "
            f"out of disk space in the temporary folder: {tempfile.gettempdir()}."
        )
    savings = 1 - output_size / input_size

    if savings < 0:
        log.info(
            "Image optimization did not improve the file - "
            "optimizations will not be used"
        )
        # We still need to save the file
        with Pdf.open(input_file) as pdf:
            pdf.remove_unreferenced_resources()
            pdf.save(output_file, **save_settings)
    else:
        safe_symlink(target_file, output_file)

    return output_file


def main(infile, outfile, level, jobs=1):
    """Entry point for direct optimization of a file."""
    from shutil import copy  # pylint: disable=import-outside-toplevel
    from tempfile import TemporaryDirectory  # pylint: disable=import-outside-toplevel

    class OptimizeOptions:
        """Emulate ocrtopdf's options."""

        def __init__(
            self, input_file, jobs, optimize_, jpeg_quality, png_quality, jb2lossy
        ):
            self.input_file = input_file
            self.jobs = jobs
            self.optimize = optimize_
            self.jpeg_quality = jpeg_quality
            self.png_quality = png_quality
            self.jbig2_page_group_size = 0
            self.jbig2_lossy = jb2lossy
            self.jbig2_threshold = 0.85
            self.quiet = True
            self.progress_bar = False

    infile = Path(infile)
    options = OptimizeOptions(
        input_file=infile,
        jobs=jobs,
        optimize_=int(level),
        jpeg_quality=0,  # Use default
        png_quality=0,
        jb2lossy=False,
    )

    with TemporaryDirectory() as tmpdir:
        context = PdfContext(options, tmpdir, infile, None, None)
        tmpout = Path(tmpdir) / 'out.pdf'
        optimize(
            infile,
            tmpout,
            context,
            dict(
                compress_streams=True,
                preserve_pdfa=True,
                object_stream_mode=ObjectStreamMode.generate,
            ),
        )
        copy(fspath(tmpout), fspath(outfile))


def export_ocr_text(input_pdf, output_txt, lang='eng'):
    ocr_text = ocr_pdf(input_pdf, lang)

    with open(output_txt, 'w', encoding='utf-8') as text_file:
        text_file.write(ocr_text)


def ocr_and_overlay(input_pdf, output_pdf):
    # Đọc PDF đầu vào
    pdf_document = fitz.open(input_pdf)

    pdf_output = fitz.open()

    for page_number in range(pdf_document.page_count):

        page = pdf_document[page_number]

        image = page.get_pixmap()

        bounding_boxes = pytesseract.image_to_boxes(Image.frombytes(
            "RGB", (image.width, image.height), image.samples))

        pdf_page = pdf_output.new_page(
            width=page.rect.width, height=page.rect.height)
        pdf_page.show_pdf_page(
            rect=pdf_page.rect, src_doc=pdf_document, page_number=page_number)

        for box in bounding_boxes.splitlines():
            data = box.split()
            x, y, x1, y1 = int(data[1]), int(
                data[2]), int(data[3]), int(data[4])
            text = " ".join(data[0])
            pdf_page.insert_text((x, y), text, fontsize=12, color=(1, 0, 0))

    pdf_output.save(output_pdf)

    pdf_document.close()
    pdf_output.close()
