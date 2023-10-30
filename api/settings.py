import os
from pathlib import Path

from pydantic import BaseSettings


class Settings(BaseSettings):
    basedir: Path = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
    workdir: Path = "/Users/linhth1/Documents/python/api_converter/workdir"
    base_command_ocr: str = "/usr/local/bin/ocrmypdf"
    api_key_secret: str = "123456"
    base_command_option: str = "--output-type pdf --fast-web-view 0 --optimize 0"
    max_ocr_process: int = 15
    document_expire_hour: int = 1
    enable_wsl_compat: bool = False


config = Settings()