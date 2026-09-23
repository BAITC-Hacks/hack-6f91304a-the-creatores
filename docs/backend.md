# ЗакупAI: сервер участника №3

Реализованы FastAPI, SQLite, загрузка нескольких XLSX, адаптер расчётов,
агент OpenAI Responses API, экспорт по конкретному расчёту и автоматические тесты.
`frontend/` и `backend/calculations/` отсутствовали в исходном репозитории и не изменялись.
Сервер не раздаёт frontend: запускайте его отдельным локальным сервером.

## Запуск в Windows PowerShell / VS Code

Откройте терминал в корне **hack-6f91304a-the-creatores**. Требуется Python 3.12+.
Если `python` открывает Microsoft Store, установите Python с python.org и перезапустите терминал.
Выполняйте команды по очереди:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
Copy-Item .env.example .env
code .env
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Активация venv не обязательна, поэтому менять ExecutionPolicy не требуется.
Если `.env` уже существует, сохраните его и отредактируйте без копирования поверх.
В этой рабочей копии `.venv` уже подготовлен; его и `.tools` не нужно коммитить.

Откройте http://127.0.0.1:8000/docs — интерактивная документация всех операций.
Проверка сервера: http://127.0.0.1:8000/api/health.

Для демонстрации **явно** задайте в `.env`:

```dotenv
DEMO_MODE=true
```

Демопровайдер проверяет, что файлы действительно XLSX, но НЕ читает бизнес-данные
из них. Он использует два синтетических товара и постоянный синтетический спрос
для проверки интеграции. Это отмечено в API, чате, предупреждениях и Excel.
Демо не моделирует сезонность, рост по истории, потерянный спрос или разовые продажи.

По умолчанию `DEMO_MODE=false`: без модуля участника №2 сервер запускается,
health показывает `calculations.available=false`, загрузка корректного файла возвращает
`503 calculation_unavailable`. Скрытой подмены на демо нет.

Для ИИ добавьте **на сервере** в `.env`:

```dotenv
OPENAI_API_KEY=ваш_ключ
OPENAI_MODEL=модель_из_вашего_аккаунта
```

Модель должна поддерживать Responses API и function calling. Если ключ или модель
не заданы, чат возвращает `ai_available=false` с явным сообщением. Загрузка,
расчёт и экспорт от ключа не зависят. Health проверяет наличие конфигурации,
а не доступ к модели: `configured_not_checked` не означает успешный API-вызов.

## Конфигурация и границы MVP

Все настройки описаны в `.env.example` и `backend/config.py`:

| Настройка | По умолчанию |
| --- | --- |
| `CALCULATION_MODULE` | `backend.calculations.provider` |
| `DATA_DIR` | `.data` относительно рабочего каталога |
| `CORS_ORIGINS` | JSON-массив localhost и 127.0.0.1:5500 |
| `MAX_UPLOAD_FILES` | 8 файлов на загрузку |
| `MAX_FILE_BYTES` | 10 MiB на файл |
| `MAX_REQUEST_BYTES` | 80 MiB на multipart-запрос, включая служебные поля |
| `MAX_UNCOMPRESSED_BYTES` | 50 MiB распакованного XLSX на файл |
| `MAX_WORKBOOK_CELLS` | 500000 фактически прочитанных ячеек на файл |
| `OPENAI_TIMEOUT_SECONDS` | 30 секунд на API-вызов, без автоматических повторов |
| `CHAT_TIMEOUT_SECONDS` | 120 секунд на агентный цикл |
| `MAX_TOOL_CALLS` | 8 вызовов инструментов на сообщение |

JSON-запросы ограничены 64 KiB (или меньшим `MAX_REQUEST_BYTES`). XLSX проверяется
как ZIP/OOXML, проверяются CRC, XML и число ячеек. Макросы отклоняются.
Имена пользователей не используются как пути: файлы сохраняются под UUID.
При ошибке загрузки частичные файлы удаляются. Ошибки бизнес-данных сохраняются
в отчёте набора, и такой набор нельзя рассчитать.

SQLite хранит неизменяемые наборы/расчёты и беседы отдельно по UUID. Сохраняются
параметры, источники (имя, SHA-256, размер, листы), период и предупреждения.
Повторная отправка calculate создаёт новый ID; автоматической идемпотентности нет.
Беседа привязана к одному dataset; параллельное сообщение в неё получает 409.
После перезапуска данные сохраняются. При смене провайдера/деморежима старые
расчёты доступны для чтения/экспорта, но набор нужно загрузить заново для пересчёта.

Это **локальная демонстрация без авторизации**, запускаемая на `127.0.0.1`.
UUID и CORS не заменяют авторизацию. Для публикации нужны учётные записи,
проверка владельцев объектов, HTTPS, квоты/очистка хранения и ограничение частоты запросов.
Загруженные данные и беседы остаются на диске без автоматического удаления/шифрования.
Провайдер участника №2 — доверенный серверный Python-код; его собственные долгие
операции должны иметь тайм-ауты. Тайм-аут чата не умеет принудительно останавливать
уже выполняющийся Python-код провайдера. Для больших расчётов нужна очередь задач.

## Участнику №1: HTTP API

База: `http://127.0.0.1:8000`. Точные схемы: `/openapi.json`, `/docs`,
файл `contracts/openapi.json`. Полный пример результата:
`contracts/recommendation.example.json` (синтетические данные, ID — примеры).

| Метод и URL | Запрос | Ответ |
| --- | --- | --- |
| `GET /api/health` | Без тела | 200, состояние конфигурации |
| `POST /api/upload` | Multipart, повторяющееся поле `files` | 201, `UploadResponse` |
| `POST /api/calculate` | JSON `dataset_id`, `parameters` | 201, `Calculation` |
| `GET /api/recommendations` | `calculation_id`, optional `supplier`, `urgency`, `offset`, `limit` | 200, страница рекомендаций |
| `POST /api/chat` | JSON с ID и `message` | 200, `ChatResponse` |
| `GET /api/export` | `calculation_id` | 200, бинарный XLSX |

### Загрузка через FormData

```javascript
const API = "http://127.0.0.1:8000";
async function readJSON(response) {
  const body = await response.json();
  if (!response.ok) throw new Error(body.error?.message ?? "Ошибка сервера");
  return body;
}
const form = new FormData();
for (const file of fileInput.files) form.append("files", file);
const dataset = await readJSON(await fetch(`${API}/api/upload`, {
  method: "POST", body: form
})); // Content-Type для FormData выставляет браузер
// Сохранить dataset.dataset_id; показать validation.errors/warnings и demo.
```

Пример `UploadResponse` (сокращённое содержимое массивов):

```json
{
  "dataset_id": "11111111-1111-4111-8111-111111111111",
  "created_at": "2026-09-23T00:00:00Z",
  "demo": true,
  "sources": [{
    "file_id": "33333333-3333-4333-8333-333333333333",
    "filename": "sales.xlsx", "size_bytes": 5000,
    "sha256": "хеш фактически загруженных байтов", "sheets": ["Sheet"]
  }],
  "validation": {
    "valid": true, "business_validation": "not_performed",
    "errors": [], "warnings": ["ДЕМО: содержимое Excel не участвует в расчёте"],
    "summary": {"uploaded_files": 1, "synthetic_products": 2}
  }
}
```

### Расчёт

```json
{
  "dataset_id": "11111111-1111-4111-8111-111111111111",
  "parameters": {
    "calculation_date": "2026-09-23",
    "supplier": "ИЭК",
    "lead_time_days": 7,
    "review_period_days": 14,
    "safety_stock_days": 10,
    "demand_growth_adjustment": null
  }
}
```

Дата и три периода обязательны. Дни — целые JSON-числа: lead/safety 0..3650,
review 1..3650. Строки `"20"` и bool вместо чисел не принимаются.
`supplier=null` (или отсутствие поля) = все поставщики. Имена сравниваются точно.
`demand_growth_adjustment` = относительная поправка: `0.2` означает +20%,
`-0.1` означает −10%, диапазон −1..5; `null` = ручная поправка не задана.
Она передаётся провайдеру без замены неизвестного на ноль.

Ответ содержит `calculation_id`, `dataset_id`, `created_at`, `demo`, `provider`,
`parameters`, `sources`, `forecast_start`, `forecast_end`, `warnings`, `recommendations`.
Сохраните новый calculation_id. Выводите именно возвращённые параметры.

```javascript
const calculation = await readJSON(await fetch(`${API}/api/calculate`, {
  method: "POST", headers: {"Content-Type": "application/json"},
  body: JSON.stringify({dataset_id: dataset.dataset_id, parameters})
}));
const query = new URLSearchParams({
  calculation_id: calculation.calculation_id, urgency: "high", limit: "100"
});
const page = await readJSON(await fetch(`${API}/api/recommendations?${query}`));
downloadLink.href = `${API}/api/export?${new URLSearchParams({
  calculation_id: calculation.calculation_id
})}`;
```

Рекомендации возвращают `calculation_id`, `dataset_id`, `demo`, `parameters`,
`forecast_start`, `forecast_end`, `warnings`, `recommendations`, `total`, `offset`, `limit`.
`total` — число после фильтров до пагинации. `limit` 1..500, по умолчанию 100.
`urgency`: `high`, `medium`, `low`, `none`, `unknown`.
Не складывайте количества разных единиц измерения. `null` показывайте как «неизвестно».
Всегда сохраняйте SKU строкой, иначе потеряются ведущие нули.

### Чат

```json
{
  "dataset_id": "11111111-1111-4111-8111-111111111111",
  "calculation_id": "22222222-2222-4222-8222-222222222222",
  "conversation_id": null,
  "message": "Поставь страховой запас 20 дней и пересчитай"
}
```

`calculation_id` и `conversation_id` можно не передавать. Без conversation_id
создаётся новая беседа. В следующих сообщениях передавайте возвращённый conversation_id.
Если calculation_id опущен, используется текущий расчёт **этой беседы**, а не глобальный.
Переданный calculation_id переключает её контекст. Нельзя смешивать dataset_id разных бесед.

```json
{
  "conversation_id": "44444444-4444-4444-8444-444444444444",
  "dataset_id": "11111111-1111-4111-8111-111111111111",
  "calculation_id": "22222222-2222-4222-8222-222222222222",
  "ai_available": false,
  "demo": true,
  "message": "ДЕМО: синтетические данные. ИИ не подключён...",
  "applied_parameters": {
    "calculation_date": "2026-09-23", "supplier": "ИЭК",
    "lead_time_days": 7, "review_period_days": 14,
    "safety_stock_days": 10, "demand_growth_adjustment": null
  },
  "export_url": "/api/export?calculation_id=22222222-2222-4222-8222-222222222222",
  "evidence": []
}
```

Если расчёта нет, calculation_id/applied_parameters/export_url равны null.
При работающем ИИ evidence содержит `{tool, result}` для каждого вызова;
это фактические результаты сервера. После пересчёта обновите ID таблицы и ссылки
из ответа. Относительный export_url нужно соединять с базовым URL API.
Для текстов товаров/ИИ используйте `textContent`, не вставляйте их как HTML.

### Ошибки

```json
{
  "error": {
    "code": "validation_error",
    "message": "Проверьте поля запроса.",
    "details": [{"field": "body.parameters.lead_time_days", "message": "Input should be greater than or equal to 0"}]
  }
}
```

| HTTP | Причина / коды |
| --- | --- |
| 400 | Некорректный multipart или превышено число multipart-полей/файлов (`http_error`) |
| 404 | `not_found`, неизвестный ID |
| 409 | `dataset_mismatch`, `provider_changed`, `conversation_busy` |
| 413 | `request_too_large`, `file_too_large`, `workbook_too_large` |
| 422 | `validation_error`, `invalid_file`, `file_count`, `invalid_form`, `dataset_invalid`, `tool_limit` |
| 502 | `provider_error`, `ai_api_error`, `ai_incomplete`, `ai_empty_response` |
| 503 | `calculation_unavailable` |
| 504 | `ai_timeout` |

В ошибке чата details содержит conversation_id и последний calculation_id,
если успел выполниться пересчёт. Получите его рекомендации/экспорт; не повторяйте
пересчёт автоматически, поскольку он создаёт новый результат.

## Участнику №2: расчётный провайдер

Ожидаемый модуль: `backend/calculations/provider.py` (или задайте `CALCULATION_MODULE`).
Это предлагаемый контракт, так как существующего интерфейса ещё не было.
Файл в зоне участника №2 здесь не создавался. Достаточно экспортировать две обычные
синхронные функции; они вызываются вне основного event loop:

```python
from pathlib import Path
from backend.models import (
    CalculationParameters, PreparedDataset, ProviderResult, Source,
)

def prepare_dataset(files: list[Path], sources: list[Source]) -> PreparedDataset:
    # Чтение, нормализация, бизнес-валидация всех загруженных файлов.
    # Вернуть report и JSON-совместимый payload; можно вернуть dict той же формы.
    ...

def calculate(payload: dict, parameters: CalculationParameters) -> ProviderResult:
    # Ваш прогноз: сезонность, устойчивый рост, потерянный спрос, исключение выбросов.
    # Вернуть рекомендации, forecast_start/end, warnings; можно вернуть dict.
    ...
```

`files` — проверенные абсолютные пути, `sources` идут в том же порядке; имена файлов
пользователя берите из sources. Нормализованные данные или ссылки на подготовленные
артефакты складывайте в JSON-совместимый payload. Не возвращайте DataFrame, bytes,
NaN/Infinity, произвольные классы. Payload сохраняется только на сервере.
Файлы остаются в `.data/uploads/<dataset_id>/` после успешного приёма.

`report`:

```json
{
  "valid": false,
  "business_validation": "failed",
  "errors": ["sales.xlsx: отсутствует колонка sku"],
  "warnings": [],
  "summary": {"products": 0}
}
```

При успехе `valid=true`, `business_validation=passed`, `errors=[]`.
`not_performed` разрешён только демонстрационному провайдеру.
Не включайте секреты и целые строки таблиц в ошибки/предупреждения: их видит клиент,
а ограниченную часть может получить модель. Для ожидаемой ошибки можно поднять
`backend.errors.AppError(status, code, message, details)`. Прочие исключения скрыты за 502.

`ProviderResult`:

```json
{
  "forecast_start": "2026-09-23",
  "forecast_end": "2026-10-14",
  "warnings": [],
  "recommendations": [{
    "sku": "000123", "name": "Пример формы строки", "supplier": "ИЭК",
    "unit": "шт", "stock": null, "incoming_in_period": null,
    "forecast_demand": null, "safety_stock": null,
    "moq": null, "order_multiple": null, "recommended_qty": null,
    "urgency": "unknown",
    "reason": "Недостаточно данных для рекомендации", "warnings": ["Нет остатков"]
  }]
}
```

Согласованный период: `[calculation_date, calculation_date + lead_time_days + review_period_days)`.
Конец исключён; страховой запас отдельный и не прибавляет дни к forecast_demand.
incoming_in_period — поставки в этом же периоде, а не весь товар в пути.
Все количества строки — в её `unit`. MOQ и order_multiple различны;
order_multiple > 0 или null, количества >= 0 или null. Неизвестное не заменять нулём.
SKU, поставщик и название — строки; пара `(supplier, sku)` уникальна в результате.
Если supplier задан, провайдер возвращает только его. Сервер проверяет период,
типы, диапазоны, дубликаты и соблюдение фильтра, но не дублирует прогнозирование.
Рекомендация должна содержать фактическое объяснение и предупреждения о пробелах.

При смене формата payload используйте совместимую версию либо новое имя модуля
и повторную загрузку. ID, хранение, экспорт и чат обеспечивает участник №3.

## Агент и достоверность

Реальный серверный вызов реализован через `AsyncOpenAI.responses.create`.
Формат проверен по [официальной документации OpenAI — Function calling](https://developers.openai.com/api/docs/guides/function-calling).
Используются strict JSON schemas, серверная Pydantic-валидация, возврат
function_call_output по call_id и перенос reasoning items между шагами.
`store=false`; это не утверждение об отсутствии всех сроков хранения у провайдера API.

Разрешены только get_data_quality, run_calculation, get_recommendations, explain_sku,
get_export_link. Dataset/calculation привязывает сервер; модель не может выбрать
чужой dataset через аргументы функции. Файлы/полный payload не отправляются модели:
только качество данных, параметры и запрошенные результаты (до 50 позиций или один SKU).
Хранятся последние 20 сообщений беседы; не передавайте в чат секреты.

Числа рекомендаций и applied_parameters берутся из серверных функций. Инструкции
запрещают модели вычислять количества. Дополнительная консервативная проверка
отсекает текст с цифровыми значениями, которых нет в текущих фактах; она может
отклонить форматирование чисел или нумерованный список. Это не полная семантическая
проверка русского текста: совпадение числа само по себе не доказывает правильность
его привязки к товару. Для решений используйте evidence, таблицу и Excel.
В тестах API модели заменён mock; платный реальный вызов не выполнялся.

## Проверки и обновление контрактов

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check backend contracts tests
.\.venv\Scripts\python.exe -m ruff format --check backend contracts tests
.\.venv\Scripts\python.exe -m contracts.generate
```

requirements*.txt задают совместимые диапазоны; requirements*.lock фиксируют
проверенный набор зависимостей. Тесты создают XLSX в памяти и временное хранилище,
ключ не требуется. Проверяются реальные API/SQLite/openpyxl и mock-цикл ИИ,
изолированные ID, внешняя точка подключения расчётов, валидация и ошибки,
пересчёт, ограничения загрузки, защита формул и ведущих нулей в Excel.

Что передать команде: участнику №1 — раздел HTTP API и contracts/openapi.json;
участнику №2 — раздел провайдера и backend/models.py. Математика прогнозирования
и frontend ожидают их реализации. Отправки заказов поставщикам здесь нет.
