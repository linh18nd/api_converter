
### Usage (Docker)
## Build với docker
```shell
docker build -t linh18/api_converter:1.0.5 .
```

## Pull image mới nhất từ dockerHub
```shell
docker pull linh18/api_converter:1.0.5
```
### Triển khai
## Chạy (không cần build), mở docker và chạy lệnh sau:
```shell
docker run -p "8080:8080" linh18/api_converter:1.0.5
```

Sau đó mở browser truy cập http://127.0.0.1:8000/docs hoặc http://0.0.0.0:8000/docs để xem tài liệu API, pass = "123456"


## Developmentdocker images

```shell
pip install -r requirements.txt
pip install -r requirements_dev.txt
uvicorn main:app --reload
```