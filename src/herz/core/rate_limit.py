import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

# 曲の取り込みは試聴のダウンロードと解析で1回数秒かかるので、ほかの検索より厳しくする
HEAVY_PATHS = ("/library/tracks",)
LIMITED_PATHS = ("/search", "/catalog/search", "/taste", *HEAVY_PATHS)
WINDOW_SECONDS = 60.0
MAX_TRACKED = 10_000


class RateLimiter:
    """同じ人（IPアドレス）からの検索を、直近1分間の回数で制限する。

    サーバー1台・プロセス1つで動かす前提で、回数はメモリに持つ（再起動で消える）。
    """

    def __init__(self, per_minute: int, heavy_per_minute: int, trust_proxy_headers: bool = False) -> None:
        self.per_minute = per_minute
        self.heavy_per_minute = heavy_per_minute
        self.trust_proxy_headers = trust_proxy_headers
        self._hits: defaultdict[tuple[str, bool], deque[float]] = defaultdict(deque)

    def client_ip(self, request: Request) -> str:
        # Cloudflare を通すと、本当の相手のIPアドレスはこのヘッダーにしか入らない。
        # 直接つながるサーバーでは誰でも書き換えられるので、Cloudflare の後ろにあるときだけ信じる
        if self.trust_proxy_headers and (forwarded := request.headers.get("cf-connecting-ip")):
            return forwarded
        return request.client.host if request.client else "unknown"

    def allow(self, ip: str, heavy: bool, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if len(self._hits) > MAX_TRACKED:
            # 1分以上来ていない人の記録を捨て、メモリが増え続けないようにする
            for key in [
                key for key, hits in self._hits.items() if not hits or now - hits[-1] >= WINDOW_SECONDS
            ]:
                del self._hits[key]
        limit = self.heavy_per_minute if heavy else self.per_minute
        hits = self._hits[(ip, heavy)]
        while hits and now - hits[0] >= WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True

    async def __call__(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        # 画面やファイルの読み込みは数えず、検索の API だけを数える
        limited = path.startswith(LIMITED_PATHS) and (request.method == "POST" or path == "/catalog/search")
        if not limited:
            return await call_next(request)
        if not self.allow(self.client_ip(request), heavy=path.startswith(HEAVY_PATHS)):
            return JSONResponse(
                {"detail": "続けて検索されたので、少し待ってからもう一度お試しください。"},
                status_code=429,
                headers={"retry-after": str(int(WINDOW_SECONDS))},
            )
        return await call_next(request)
