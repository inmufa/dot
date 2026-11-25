"""Local sites with login forms for the vault tests."""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from dot_browser.vault.totp import totp_code

USER, PASSWORD, TOTP = "alice@example.com", "s3cret-pass-1", "JBSWY3DPEHPK3PXP"
COOKIE = "sid=session-token-abcdef123456"

USER_FIELD = '<input name="email" type="email" aria-label="Email">'
PASS_FIELD = '<input name="password" type="password" aria-label="Password">'


def page(body: str, title: str = "Login") -> str:
    return f"<!doctype html><title>{title}</title><body>{body}</body>"


def form(action: str, inner: str, extra: str = "") -> str:
    return (
        f'<form method="post" action="{action}">{inner}{extra}'
        '<button type="submit">Go</button></form>'
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_a: object) -> None:
        return

    def _send(self, body: str, status: int = 200, **h: str) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        for k, v in h.items():
            self.send_header(k.replace("_", "-"), v)
        self.end_headers()
        self.wfile.write(data)

    def _form(self) -> dict[str, str]:
        n = int(self.headers.get("Content-Length", 0))
        raw = parse_qs(self.rfile.read(n).decode())
        return {k: v[0] for k, v in raw.items()}

    def _home(self) -> None:
        ok = COOKIE in self.headers.get("Cookie", "")
        self._send(
            page("Welcome alice" if ok else "Anonymous", "Home" if ok else "Anon")
        )

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        host = self.headers["Host"]
        pages = {
            "/login1": form("/do1", USER_FIELD + PASS_FIELD),
            "/login2": form("/step2", USER_FIELD),
            "/login-totp": form("/do-totp", USER_FIELD + PASS_FIELD),
            "/hidden": form(
                "/do1",
                '<input type="password" name="password" style="display:none">',
            ),
            "/offaction": form(
                f"http://localhost:{host.split(':')[1]}/do1", USER_FIELD + PASS_FIELD
            ),
            "/captcha": '<div class="g-recaptcha"></div>'
            + form("/do1", USER_FIELD + PASS_FIELD),
            "/framed": "<iframe srcdoc='<input type=\"password\">'></iframe>",
            "/plain": page("nothing to see"),
        }
        if path == "/home":
            self._home()
        elif path in pages:
            self._send(page(pages[path]))
        else:
            self._send("nope", 404)

    def _ok(self) -> None:
        self._send(
            "", 302, Location="/home", Set_Cookie=f"{COOKIE}; Path=/; Max-Age=86400"
        )

    def do_POST(self) -> None:
        f, path = self._form(), self.path
        good = f.get("password") == PASSWORD and f.get("email") == USER
        if path == "/step2":
            hidden = f'<input type="hidden" name="email" value="{f.get("email", "")}">'
            self._send(page(form("/do2", PASS_FIELD, hidden)))
        elif path in ("/do1", "/do2") and good:
            self._ok()
        elif path == "/do-totp" and good:
            code = '<input name="code" autocomplete="one-time-code" maxlength="6">'
            self._send(page(form("/do-otp", code)))
        elif path == "/do-otp" and self._otp_ok(f.get("code", "")):
            self._ok()
        else:
            err = '<p class="error">Invalid email or password</p>'
            self._send(page(err + form("/do1", USER_FIELD + PASS_FIELD)))

    @staticmethod
    def _otp_ok(code: str) -> bool:
        now = time.time()
        return code in {totp_code(TOTP, now + d) for d in (-30, 0, 30)}


def start() -> tuple[ThreadingHTTPServer, str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"
