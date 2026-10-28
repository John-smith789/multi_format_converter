"""A practical multi-format conversion engine.

Optional backends are imported only when needed:
  Images: Pillow
  Audio/video: ffmpeg (or imageio-ffmpeg)
  PDF rasterization: pdf2image + Poppler
  Tables: pandas + format-specific Excel engines
  Documents/presentations: LibreOffice (soffice) and/or Pandoc
  Archives: Python standard library for ZIP/TAR; py7zr/rarfile for 7z/RAR

This is a conversion engine, not a promise that every pair of formats is
semantically convertible. Each backend reports unsupported pairs/errors rather
than claiming success without producing an output.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
import tarfile
from pathlib import Path
from typing import Callable, Optional, Any

ProgressCallback = Optional[Callable[[float, str], None]]
CompletionCallback = Optional[Callable[[bool], None]]

AUDIO = {"mp3", "wav", "aac", "flac", "ogg", "m4a", "opus", "wma", "aiff", "ac3"}
VIDEO = {"mp4", "mkv", "avi", "mov", "webm", "wmv", "flv", "mpeg", "mpg", "3gp", "gif", "m4v", "ts"}
IMAGE = {"jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff", "ico", "avif", "gif"}
TABLE = {"csv", "tsv", "xlsx", "xls", "ods", "json"}
STRUCTURED = {"json", "xml", "yaml", "yml"}
ARCHIVE = {"zip", "tar", "tgz", "gz", "tar.gz", "7z", "rar"}
DOCUMENT = {"pdf", "doc", "docx", "odt", "rtf", "txt", "md", "html", "htm", "epub", "ppt", "pptx", "odp"}


class ConversionError(RuntimeError):
    """Raised when a conversion cannot be completed."""


class FullConverterEngine:
    def __init__(self, ffmpeg_bin: Optional[str] = None, timeout: Optional[int] = None):
        self.ffmpeg_bin = ffmpeg_bin or self._locate_ffmpeg()
        self.timeout = timeout

    @staticmethod
    def _locate_ffmpeg() -> str:
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            return shutil.which("ffmpeg") or "ffmpeg"

    @staticmethod
    def _get_ext(filepath: str) -> str:
        name = Path(filepath).name.lower()
        if name.endswith(".tar.gz"):
            return "tar.gz"
        return Path(name).suffix.lstrip(".")

    @staticmethod
    def _notify(callback: ProgressCallback, amount: float, message: str) -> None:
        if callback:
            try:
                callback(max(0.0, min(1.0, float(amount))), message)
            except Exception:
                pass  # UI callback errors must not corrupt an otherwise valid conversion.

    def convert(self, input_path: str, output_path: str, progress_callback: ProgressCallback = None) -> bool:
        """Convert one file synchronously. Returns True only if output exists and is non-empty."""
        source, destination = Path(input_path), Path(output_path)
        if not source.is_file():
            raise ConversionError(f"Input file does not exist: {source}")
        if source.resolve() == destination.resolve():
            raise ConversionError("Input and output paths must be different.")
        if not destination.suffix:
            raise ConversionError("Output path must include a file extension.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            destination.unlink()

        ext_in, ext_out = self._get_ext(str(source)), self._get_ext(str(destination))
        self._notify(progress_callback, 0.05, "Inspecting formats...")
        try:
            # Route specialized pairs first, before general image/document families.
            if ext_in in STRUCTURED and ext_out in (STRUCTURED | {"txt"}):
                self._convert_data_struct(str(source), str(destination), ext_in, ext_out, progress_callback)
            elif ext_in in TABLE and ext_out in (TABLE | {"html", "pdf"}):
                self._convert_tabular(str(source), str(destination), ext_in, ext_out, progress_callback)
            elif ext_in in ARCHIVE or ext_out in ARCHIVE:
                self._convert_archive(str(source), str(destination), ext_in, ext_out, progress_callback)
            elif ext_in == "pdf" and ext_out in IMAGE:
                self._convert_pdf_to_image(str(source), str(destination), progress_callback)
            elif ext_out in AUDIO:
                self._convert_audio(str(source), str(destination), ext_out, progress_callback)
            elif ext_out in VIDEO:
                self._convert_video(str(source), str(destination), ext_out, progress_callback)
            elif ext_in in IMAGE and ext_out in IMAGE:
                self._convert_image(str(source), str(destination), progress_callback)
            elif ext_in in {"ppt", "pptx", "odp"} or ext_out in {"ppt", "pptx", "odp"}:
                self._convert_presentation(str(source), str(destination), progress_callback)
            elif ext_in in DOCUMENT or ext_out in DOCUMENT:
                self._convert_document(str(source), str(destination), ext_in, ext_out, progress_callback)
            else:
                raise ConversionError(f"Unsupported conversion: .{ext_in} to .{ext_out}")

            if not destination.is_file() or destination.stat().st_size == 0:
                raise ConversionError("The conversion backend did not create a non-empty output file.")
            self._notify(progress_callback, 1.0, "Conversion complete")
            return True
        except Exception:
            try:
                if destination.exists():
                    destination.unlink()
            except OSError:
                pass
            raise

    def convert_async(self, input_path: str, output_path: str, progress_callback: ProgressCallback = None,
                      completion_callback: CompletionCallback = None) -> threading.Thread:
        """Run conversion on a daemon thread. Completion callback receives (success: bool)."""
        def worker() -> None:
            success = False
            try:
                success = self.convert(input_path, output_path, progress_callback)
            except Exception as exc:
                self._notify(progress_callback, 0.0, f"Failed: {exc}")
            finally:
                if completion_callback:
                    try:
                        completion_callback(success)
                    except Exception:
                        pass
        thread = threading.Thread(target=worker, name="file-converter", daemon=True)
        thread.start()
        return thread

    def _run_subprocess(self, cmd: list[str], timeout: Optional[int] = None) -> None:
        startupinfo = None
        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  startupinfo=startupinfo, creationflags=creationflags,
                                  timeout=self.timeout if timeout is None else timeout, check=False)
        except FileNotFoundError as exc:
            raise ConversionError(f"Required program not found: {cmd[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise ConversionError(f"Conversion timed out after {exc.timeout} seconds.") from exc
        if proc.returncode:
            detail = (proc.stderr or proc.stdout or "No diagnostic output").strip()
            raise ConversionError(f"Command failed ({proc.returncode}): {detail[-2500:]}")

    def _convert_audio(self, src: str, dst: str, ext: str, cb: ProgressCallback) -> None:
        self._notify(cb, .2, f"Encoding audio as {ext.upper()}...")
        codecs = {"mp3": ["-c:a", "libmp3lame", "-q:a", "2"], "wav": ["-c:a", "pcm_s16le"],
                  "aac": ["-c:a", "aac"], "m4a": ["-c:a", "aac"], "flac": ["-c:a", "flac"],
                  "ogg": ["-c:a", "libvorbis"], "opus": ["-c:a", "libopus"],
                  "wma": ["-c:a", "wmav2"], "aiff": ["-c:a", "pcm_s16be"], "ac3": ["-c:a", "ac3"]}
        self._run_subprocess([self.ffmpeg_bin, "-nostdin", "-y", "-i", src, "-vn", *codecs[ext], dst])

    def _convert_video(self, src: str, dst: str, ext: str, cb: ProgressCallback) -> None:
        self._notify(cb, .2, f"Encoding media as {ext.upper()}...")
        if ext == "gif":
            args = ["-vf", "fps=12,scale=640:-1:flags=lanczos"]
        elif ext == "webm":
            args = ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-c:a", "libopus"]
        else:
            args = ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-movflags", "+faststart"]
        self._run_subprocess([self.ffmpeg_bin, "-nostdin", "-y", "-i", src, *args, dst])

    def _convert_image(self, src: str, dst: str, cb: ProgressCallback) -> None:
        self._notify(cb, .3, "Converting image...")
        try:
            from PIL import Image, ImageOps
        except ImportError as exc:
            raise ConversionError("Image conversion requires Pillow (pip install Pillow).") from exc
        with Image.open(src) as original:
            image = ImageOps.exif_transpose(original)
            ext = self._get_ext(dst)
            if ext in {"jpg", "jpeg"}:
                if image.mode in ("RGBA", "LA", "P"):
                    rgba = image.convert("RGBA")
                    background = Image.new("RGB", rgba.size, "white")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    image = background
                else:
                    image = image.convert("RGB")
                image.save(dst, format="JPEG", quality=92, optimize=True)
            elif ext == "ico":
                image.save(dst, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            else:
                image.save(dst, format={"jpg": "JPEG", "tif": "TIFF"}.get(ext, ext.upper()))

    def _convert_pdf_to_image(self, src: str, dst: str, cb: ProgressCallback) -> None:
        self._notify(cb, .3, "Rendering first PDF page...")
        try:
            from pdf2image import convert_from_path
        except ImportError as exc:
            raise ConversionError("PDF-to-image requires pdf2image and Poppler.") from exc
        pages = convert_from_path(src, first_page=1, last_page=1)
        if not pages:
            raise ConversionError("PDF contains no renderable pages.")
        pages[0].save(dst)

    def _convert_tabular(self, src: str, dst: str, ext_in: str, ext_out: str, cb: ProgressCallback) -> None:
        self._notify(cb, .25, "Reading tabular data...")
        try:
            import pandas as pd
        except ImportError as exc:
            raise ConversionError("Spreadsheet conversion requires pandas.") from exc
        if ext_in in {"csv", "tsv"}:
            df = pd.read_csv(src, sep="\t" if ext_in == "tsv" else ",")
        elif ext_in in {"xlsx", "xls", "ods"}:
            df = pd.read_excel(src)
        elif ext_in == "json":
            df = pd.read_json(src)
        else:
            raise ConversionError(f"Unsupported input table format: {ext_in}")
        self._notify(cb, .7, f"Writing {ext_out.upper()}...")
        if ext_out == "csv": df.to_csv(dst, index=False)
        elif ext_out == "tsv": df.to_csv(dst, sep="\t", index=False)
        elif ext_out in {"xlsx", "xls", "ods"}: df.to_excel(dst, index=False)
        elif ext_out == "json": df.to_json(dst, orient="records", indent=2, force_ascii=False)
        elif ext_out == "html": df.to_html(dst, index=False)
        elif ext_out == "pdf": self._soffice_convert(src, dst)
        else: raise ConversionError(f"Unsupported table output format: {ext_out}")

    def _convert_data_struct(self, src: str, dst: str, ext_in: str, ext_out: str, cb: ProgressCallback) -> None:
        self._notify(cb, .25, "Parsing structured data...")
        try:
            import yaml
        except ImportError:
            yaml = None
        try:
            import xmltodict
        except ImportError:
            xmltodict = None
        text = Path(src).read_text(encoding="utf-8-sig")
        if ext_in == "json": data = json.loads(text)
        elif ext_in in {"yaml", "yml"}:
            if yaml is None: raise ConversionError("YAML conversion requires PyYAML.")
            data = yaml.safe_load(text)
        elif ext_in == "xml":
            if xmltodict is None: raise ConversionError("XML conversion requires xmltodict.")
            data = xmltodict.parse(text)
        else: raise ConversionError(f"Unsupported structured input: {ext_in}")
        self._notify(cb, .7, f"Writing {ext_out.upper()}...")
        if ext_out == "json": output = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        elif ext_out in {"yaml", "yml"}:
            if yaml is None: raise ConversionError("YAML conversion requires PyYAML.")
            output = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        elif ext_out == "xml":
            if xmltodict is None: raise ConversionError("XML conversion requires xmltodict.")
            if not isinstance(data, dict) or len(data) != 1:
                raise ConversionError("XML output requires a single named root element.")
            output = xmltodict.unparse(data, pretty=True) + "\n"
        elif ext_out == "txt": output = str(data) + "\n"
        else: raise ConversionError(f"Unsupported structured output: {ext_out}")
        Path(dst).write_text(output, encoding="utf-8")

    @staticmethod
    def _safe_extract_zip(path: str, dest: str) -> None:
        root = Path(dest).resolve()
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                target = (root / member.filename).resolve()
                if target != root and root not in target.parents:
                    raise ConversionError("Unsafe path detected in ZIP archive.")
            archive.extractall(root)

    @staticmethod
    def _safe_extract_tar(path: str, dest: str) -> None:
        root = Path(dest).resolve()
        with tarfile.open(path, "r:*") as archive:
            for member in archive.getmembers():
                target = (root / member.name).resolve()
                if target != root and root not in target.parents:
                    raise ConversionError("Unsafe path detected in TAR archive.")
                if member.issym() or member.islnk():
                    raise ConversionError("Links are not allowed in converted archives.")
            archive.extractall(root, filter="data")

    def _convert_archive(self, src: str, dst: str, ext_in: str, ext_out: str, cb: ProgressCallback) -> None:
        if ext_in not in ARCHIVE or ext_out not in ARCHIVE:
            raise ConversionError("Archive conversion requires both input and output to be supported archive formats.")
        self._notify(cb, .2, "Extracting archive contents safely...")
        with tempfile.TemporaryDirectory(prefix="converter-") as work:
            contents = Path(work) / "contents"
            contents.mkdir()
            if ext_in == "zip": self._safe_extract_zip(src, str(contents))
            elif ext_in in {"tar", "tar.gz", "tgz", "gz"}: self._safe_extract_tar(src, str(contents))
            elif ext_in == "7z":
                try: import py7zr
                except ImportError as exc: raise ConversionError("7z requires py7zr (pip install py7zr).") from exc
                with py7zr.SevenZipFile(src, mode="r") as archive: archive.extractall(path=contents)
            elif ext_in == "rar":
                try: import rarfile
                except ImportError as exc: raise ConversionError("RAR requires rarfile and an installed RAR backend.") from exc
                with rarfile.RarFile(src) as archive: archive.extractall(path=contents)
            else: raise ConversionError(f"Unsupported archive input: {ext_in}")
            self._notify(cb, .7, f"Creating {ext_out.upper()} archive...")
            if ext_out == "zip":
                with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for item in contents.rglob("*"):
                        if item.is_file(): archive.write(item, item.relative_to(contents))
            elif ext_out in {"tar", "tar.gz", "tgz", "gz"}:
                mode = "w:gz" if ext_out in {"tar.gz", "tgz", "gz"} else "w"
                with tarfile.open(dst, mode) as archive:
                    for item in contents.iterdir(): archive.add(item, arcname=item.name)
            elif ext_out == "7z":
                try: import py7zr
                except ImportError as exc: raise ConversionError("7z output requires py7zr (pip install py7zr).") from exc
                with py7zr.SevenZipFile(dst, mode="w") as archive: archive.writeall(contents, arcname="")
            else: raise ConversionError("Creating RAR archives is not supported.")

    def _convert_presentation(self, src: str, dst: str, cb: ProgressCallback) -> None:
        self._notify(cb, .3, "Converting presentation with LibreOffice...")
        self._soffice_convert(src, dst)

    def _convert_document(self, src: str, dst: str, ext_in: str, ext_out: str, cb: ProgressCallback) -> None:
        self._notify(cb, .3, "Converting document...")
        pandoc_input = {"md", "txt", "html", "htm", "epub"}
        if ext_in in pandoc_input or ext_out in {"md", "epub"}:
            pandoc = shutil.which("pandoc")
            if pandoc:
                try:
                    self._run_subprocess([pandoc, src, "-o", dst])
                    return
                except ConversionError:
                    if ext_in in {"md", "txt", "html", "htm", "epub"} and ext_out in {"md", "epub"}:
                        raise
        self._soffice_convert(src, dst)

    def _soffice_convert(self, src: str, dst: str) -> None:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if os.name == "nt" and not soffice:
            candidate = r"C:\Program Files\LibreOffice\program\soffice.exe"
            if os.path.isfile(candidate): soffice = candidate
        if not soffice:
            raise ConversionError("LibreOffice is required for this document conversion (install soffice).")
        ext = self._get_ext(dst)
        out_dir = str(Path(dst).resolve().parent)
        with tempfile.TemporaryDirectory(prefix="lo-profile-") as profile:
            cmd = [soffice, "-env:UserInstallation=" + Path(profile).as_uri(), "--headless", "--convert-to", ext,
                   "--outdir", out_dir, str(Path(src).resolve())]
            self._run_subprocess(cmd, timeout=self.timeout or 300)
        produced = Path(out_dir) / (Path(src).stem + "." + ext)
        target = Path(dst)
        if produced.resolve() != target.resolve() and produced.exists():
            if target.exists(): target.unlink()
            produced.replace(target)
        if not target.exists():
            raise ConversionError(f"LibreOffice did not produce the expected output: {target}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert between supported media, document, data, table, and archive formats.")
    parser.add_argument("input", help="Input file")
    parser.add_argument("output", help="Output file (extension selects output format)")
    parser.add_argument("--timeout", type=int, default=None, help="Subprocess timeout in seconds")
    args = parser.parse_args()
    engine = FullConverterEngine(timeout=args.timeout)
    try:
        engine.convert(args.input, args.output, lambda p, msg: print(f"{p:5.0%} {msg}"))
        print(f"Saved: {args.output}")
    except Exception as error:
        parser.exit(1, f"Conversion failed: {error}\n")
