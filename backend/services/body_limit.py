from tempfile import SpooledTemporaryFile

from starlette.responses import JSONResponse

from backend.errors import AppError


class BodyLimitMiddleware:
    """Bound even chunked bodies before multipart parsing can spool unbounded files."""

    def __init__(self, app, max_bytes):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        limit = self.max_bytes if scope["path"] == "/api/upload" else min(self.max_bytes, 64 * 1024)

        async def reject():
            response = JSONResponse(
                AppError(413, "request_too_large", "Размер запроса превышает лимит.").body(), 413
            )
            await response(scope, receive, send)

        headers = dict(scope["headers"])
        try:
            if int(headers.get(b"content-length", b"0")) > limit:
                return await reject()
        except ValueError:
            return await reject()
        with SpooledTemporaryFile(max_size=1024 * 1024) as buffer:
            size = 0
            while True:
                event = await receive()
                if event["type"] == "http.disconnect":
                    return
                chunk = event.get("body", b"")
                size += len(chunk)
                if size > limit:
                    return await reject()
                buffer.write(chunk)
                if not event.get("more_body", False):
                    break
            buffer.seek(0)
            consumed = False

            async def replay():
                nonlocal consumed
                if consumed:
                    return await receive()
                chunk = buffer.read(64 * 1024)
                more = buffer.tell() < size
                consumed = not more
                return {"type": "http.request", "body": chunk, "more_body": more}

            await self.app(scope, replay, send)
