
## Usage (Docker)

```shell
docker build -t linh18/api_converter:1.0.4 .
```

```shell
docker run -p "80:80" linh18/api_converter:1.0.4
```

then open your browser to http://127.0.0.1:8000/docs or http://0.0.0.0:8000/docs

## Settings

There are some settings which can be configured via environment variable. The list is available in `settings.py`. Simply
apply upper case to the name of the setting.

## Developmentdocker images

```shell
pip install -r requirements.txt
pip install -r requirements_dev.txt
uvicorn main:app --reload
```