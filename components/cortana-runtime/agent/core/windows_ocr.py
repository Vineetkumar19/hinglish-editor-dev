"""Bounded built-in Windows OCR; no cloud upload or shell command from a model."""
import asyncio
import os
import tempfile
from pathlib import Path
from core.config import ROOT_DIR, settings


def recognize(image):
    folder=Path(settings.memory_dir)/'ocr-scratch'
    folder.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(suffix='.png',dir=folder)
    os.close(fd)
    try:
        image.save(name)
        async def read():
            from winrt.windows.storage import StorageFile, FileAccessMode
            from winrt.windows.graphics.imaging import BitmapDecoder
            from winrt.windows.media.ocr import OcrEngine
            source=await StorageFile.get_file_from_path_async(str(Path(name).resolve()))
            stream=await source.open_async(FileAccessMode.READ)
            try:
                decoder=await BitmapDecoder.create_async(stream)
                bitmap=await decoder.get_software_bitmap_async()
                try:
                    engine=OcrEngine.try_create_from_user_profile_languages()
                    if engine is None:
                        raise ValueError('No installed Windows OCR language is available.')
                    result=await engine.recognize_async(bitmap)
                    return '\n'.join(line.text for line in result.lines),None
                finally:
                    bitmap.close()
            finally:
                stream.close()
        async def bounded():
            return await asyncio.wait_for(read(),timeout=35)
        return asyncio.run(bounded())
    finally:
        Path(name).unlink(missing_ok=True)
