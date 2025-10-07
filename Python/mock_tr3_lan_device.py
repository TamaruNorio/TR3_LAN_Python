"""TR3 LAN リーダライタの簡易モックサーバー."""

from __future__ import annotations

import socket
import threading
from typing import Iterable, List, Sequence

import tr3_lan_protocol as proto


class MockTr3LanDevice:
    """プロトコルレベルでの動作確認用に応答を模擬するサーバー."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9100) -> None:
        # 接続待ち受け用のソケット情報を保持
        self.host = host
        self.port = port
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._server: socket.socket | None = None
        # デモ用に返すタグリスト（dsfid + UID8 バイト）
        self.tags: List[List[int]] = [
            [0x00, 0xE0, 0x04, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC],
            [0x01, 0xE0, 0x04, 0x98, 0x76, 0x54, 0x32, 0x10, 0xFF],
        ]

    # ---------------------------------------------
    # サーバー制御
    # ---------------------------------------------
    def start(self) -> None:
        """バックグラウンドスレッドでサーバーを起動する."""

        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._ready.clear()
        thread = threading.Thread(target=self._serve, daemon=True)
        self._thread = thread
        thread.start()
        # バインド完了を待機してから戻る
        self._ready.wait(timeout=2.0)

    def stop(self) -> None:
        """サーバーを停止してスレッドを破棄する."""

        self._stop_event.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
            finally:
                self._server = None
        # 自分自身に接続して accept を解除
        try:
            with socket.create_connection((self.host, self.port), timeout=0.2):
                pass
        except OSError:
            pass
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    # ---------------------------------------------
    # 内部実装
    # ---------------------------------------------
    def _serve(self) -> None:
        """ソケット待受とコマンド応答を順次処理する."""

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((self.host, self.port))
                server.listen(1)
                server.settimeout(0.2)
                self._server = server
                self._ready.set()

                while not self._stop_event.is_set():
                    try:
                        conn, _ = server.accept()
                    except socket.timeout:
                        continue
                    with conn:
                        conn.settimeout(0.5)
                        self._handle_client(conn)
        finally:
            self._ready.set()

    def _handle_client(self, conn: socket.socket) -> None:
        """クライアント1接続ごとにコマンドを読み取って応答する."""

        parser = proto.Parser()
        while not self._stop_event.is_set():
            try:
                chunk = conn.recv(1)
            except socket.timeout:
                continue
            if not chunk:
                break
            byte = chunk[0]
            if parser.push(byte):
                addr, cmd, data = parser.take()
                replies = self._build_replies(addr, cmd, data)
                for reply in replies:
                    conn.sendall(bytes(reply))

    def _build_replies(
        self, addr: int, cmd: int, data: Sequence[int]
    ) -> List[List[int]]:
        """受信コマンドに対する応答フレーム列を生成する."""

        if cmd == 0x4F and list(data) == [0x90]:
            rom = [0x90]
            rom.extend(ord(c) for c in "1052TR3A1")
            return [self._encode(addr, cmd, rom)]
        if cmd == 0x4E:
            return [self._encode(addr, cmd, [0x00])]
        if cmd == 0x78:
            count = len(self.tags)
            replies = [self._encode(addr, cmd, [0xF0, count & 0xFF])]
            for tag in self.tags:
                replies.append(self._encode(addr, 0x49, tag))
            return replies
        if cmd == 0x42:
            return [self._encode(addr, cmd, [0x00])]
        # 想定外コマンドは汎用的に NAK 相当を返す
        return [self._encode(addr, cmd, [0xFF])]

    @staticmethod
    def _encode(addr: int, cmd: int, data: Iterable[int]) -> List[int]:
        """Frame クラスを用いて送信フレームを作成する."""

        frame = proto.Frame(addr=addr, cmd=cmd, data=list(data))
        return frame.encode()