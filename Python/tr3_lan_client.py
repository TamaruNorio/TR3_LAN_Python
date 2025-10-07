"""TR3 LAN クライアント（ソケット通信ラッパー）."""

from __future__ import annotations

import socket
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import tr3_lan_protocol as proto


@dataclass
class Reply:
    """受信結果（CMD/Data/Raw）の簡易コンテナ."""

    cmd: int
    data: List[int]
    raw: List[int]


class Tr3LanClient:
    """TR3 リーダライタと LAN 経由で通信するシンプルなクライアント."""

    def __init__(self) -> None:
        self._socket: Optional[socket.socket] = None
        self._lock = threading.Lock()  # ソケット操作の排他制御

    # ---------------------------------------------
    # 接続制御
    # ---------------------------------------------
    def connect(self, host: str, port: int, timeout_ms: int = 5000) -> None:
        """指定した IP/ポートへ TCP 接続する."""

        self.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_ms / 1000.0)
        try:
            sock.connect((host, port))
        except Exception:
            sock.close()
            raise
        sock.settimeout(timeout_ms / 1000.0)
        self._socket = sock

    def close(self) -> None:
        """ソケットをクローズする."""

        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    def is_connected(self) -> bool:
        """ソケットが有効かどうかを返す."""

        return self._socket is not None

    # ---------------------------------------------
    # 送受信
    # ---------------------------------------------
    def transact(self, frame: List[int], retries: int = 1) -> Reply:
        """1 コマンド送信→応答フレーム取得を行う."""

        sock = self._require_socket()
        # 送信と受信をまとめてロックし、同時実行を防ぐ
        with self._lock:
            raw = self._send_and_receive(sock, frame, retries)
        parser = proto.Parser()
        for b in raw:
            parser.push(b)
        _, cmd, data = parser.take()
        return Reply(cmd=cmd, data=data, raw=raw)

    def receive_only(self) -> Reply:
        """送信を行わずに次の 1 フレームだけを受信する."""

        sock = self._require_socket()
        with self._lock:
            raw = self._receive_frame(sock)
        parser = proto.Parser()
        for b in raw:
            parser.push(b)
        _, cmd, data = parser.take()
        return Reply(cmd=cmd, data=data, raw=raw)

    # ---------------------------------------------
    # 内部ヘルパー
    # ---------------------------------------------
    def _require_socket(self) -> socket.socket:
        if self._socket is None:
            raise RuntimeError("ソケットが未接続です")
        return self._socket

    def _send_and_receive(
        self, sock: socket.socket, frame: List[int], retries: int
    ) -> List[int]:
        payload = bytes(frame)
        parser = proto.Parser()
        attempt = 0
        last_error: Optional[Exception] = None
        while attempt <= retries:
            try:
                sock.sendall(payload)
                raw = self._receive_frame(sock, parser)
                return raw
            except socket.timeout as exc:
                last_error = exc
                attempt += 1
                if attempt > retries:
                    break
                # タイムアウト時は再送を試みる
                parser.reset()
                continue
        raise RuntimeError(f"受信タイムアウト: {last_error}")

    def _receive_frame(
        self, sock: socket.socket, parser: Optional[proto.Parser] = None
    ) -> List[int]:
        if parser is None:
            parser = proto.Parser()
        while True:
            chunk = sock.recv(1)
            if not chunk:
                raise RuntimeError("切断されました")
            byte = chunk[0]
            if parser.push(byte):
                return parser.take_raw()


# ---------------------------------------------
# ログ用ユーティリティ
# ---------------------------------------------

def timestamp() -> str:
    """現在時刻を mm/dd HH:MM:SS.mmm 形式で返す."""

    now = datetime.now()
    return now.strftime("%m/%d %H:%M:%S.%f")[:-3]