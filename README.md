# biref (BiRefNet ToonOut serverless)

Сервис фона/маски на базе BiRefNet (ToonOut). Работает в двух режимах:
- HTTP (FastAPI) для локальных проверок здоровья
- Runpod Serverless handler (`rp_handler.py`) для инференса: вход — base64 PNG/JPEG, выход — PNG RGBA или маска

## Интерфейс Runpod

Вызов:
```json
{
  "input": {
    "image": "<base64>",
    "return_mask": false
  }
}
```
Ответ:
- `{ "image": "<base64>" }` — RGBA PNG
- `{ "mask": "<base64>" }` — если `return_mask=true`

## Сборка локально
```bash
cd biref
DOCKER_BUILDKIT=1 docker build -t biref:local .
```

## Запуск локально (HTTP healthcheck)
```bash
docker run --rm -it -p 7865:7865 --gpus all biref:local
# открыть http://localhost:7865/
```

## Тест handler локально
```bash
docker run --rm -it --gpus all biref:local python3 -c "import rp_handler,base64;print(rp_handler.handler({'input':{'image':base64.b64encode(open('sample.png','rb').read()).decode()}}).keys())"
```

## Деплой на Runpod Serverless
Готовим образ и публикуем через GitHub Actions (workflow ниже). Затем в консоли Runpod создать Serverless template, указав образ контейнера и Python entrypoint `rp_handler.py` (переменная окружения `RUNPOD_SERVERLESS=1`).

