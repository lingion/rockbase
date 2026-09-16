"""本机模拟 SMTP 对端（"外部世界"）：仅用于本机彩排与测试，🚫生产。

实现最小 SMTP 会话（EHLO/AUTH LOGIN/DATA/QUIT），收下的原始信件交给
on_message 回调；宿主可借它模拟 KOL 自动回信等剧本。
"""
from __future__ import annotations

import socket
import socketserver


def start_fake_smtp(on_message, host: str = "127.0.0.1", port: int = 0):
    """起一个假 SMTP 服务，返回 server（.server_address 取实际端口，.shutdown() 停）。"""

    class Handler(socketserver.StreamRequestHandler):
        def _auth(self, line: bytes) -> None:
            # AUTH LOGIN <b64user>（一行式）→ 下一行是密码；裸 AUTH LOGIN（两步式）→ 先要用户名
            if len(line.split()) >= 3:
                self.wfile.write(b"334 UGFzc3dvcmQ6\r\n")
                self.rfile.readline()
            else:
                self.wfile.write(b"334 VXNlcm5hbWU6\r\n")
                self.rfile.readline()
                self.wfile.write(b"334 UGFzc3dvcmQ6\r\n")
                self.rfile.readline()
            self.wfile.write(b"235 ok\r\n")

        def handle(self) -> None:
            self.request.settimeout(15)  # 防对端半开会挂死线程（test-reliability 教训）
            try:
                self._session()
            except (socket.timeout, TimeoutError, ConnectionResetError,
                    BrokenPipeError):
                pass

        def _session(self) -> None:
            self.wfile.write(b"220 fake-world ready\r\n")
            while True:
                line = self.rfile.readline()
                if not line:
                    break
                cmd = line.strip().upper()
                if cmd.startswith((b"EHLO", b"HELO")):
                    self.wfile.write(b"250-fake-world\r\n250-AUTH LOGIN PLAIN\r\n"
                                     b"250 8BITMIME\r\n")
                elif cmd == b"DATA":
                    self.wfile.write(b"354 end with <CRLF>.<CRLF>\r\n")
                    raw = b""
                    while True:
                        d = self.rfile.readline()
                        if not d or d.strip() == b".":
                            break
                        if d.startswith(b".."):
                            d = d[1:]  # SMTP 点填充还原
                        raw += d
                    try:
                        on_message(raw)
                    except Exception as e:  # noqa: BLE001
                        print(f"  [fake-smtp] on_message 异常: {e}", flush=True)
                    self.wfile.write(b"250 accepted\r\n")
                elif line[:4].upper() == b"AUTH":
                    self._auth(line)
                elif cmd == b"QUIT":
                    self.wfile.write(b"221 bye\r\n")
                    break
                else:  # MAIL FROM / RCPT TO / NOOP / RSET
                    self.wfile.write(b"250 ok\r\n")

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    srv = Server((host, port), Handler)
    return srv
