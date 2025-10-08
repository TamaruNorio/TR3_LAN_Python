
"""TR3 LAN クライアント（ソケット通信ラッパー）.

このモジュールは、タカヤ製TR3リーダライタとLAN経由で通信するための
基本的なTCPクライアント機能を提供します。
"""

from __future__ import annotations

import socket
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import tr3_lan_protocol as proto  # TR3プロトコル解析モジュールをインポート


@dataclass
class Reply:
    """受信結果（CMD/Data/Raw）の簡易コンテナ.

    TR3リーダライタからの応答フレームを解析した結果を保持します。
    - cmd: コマンドコード (int)
    - data: データ部 (List[int])
    - raw: 生の受信フレーム (List[int])
    """

    cmd: int
    data: List[int]
    raw: List[int]


class Tr3LanClient:
    """TR3 リーダライタと LAN 経由で通信するシンプルなクライアント.

    TCPソケットの接続管理、コマンドの送受信、応答フレームの解析を行います。
    """

    def __init__(self) -> None:
        """Tr3LanClientのコンストラクタ.

        ソケット接続の状態と、スレッドセーフな操作のためのロックを初期化します。
        """
        self._socket: Optional[socket.socket] = None  # 現在のソケット接続
        self._lock = threading.Lock()  # ソケット操作の排他制御

    # ---------------------------------------------
    # 接続制御
    # ---------------------------------------------
    def connect(self, host: str, port: int, timeout_ms: int = 5000) -> None:
        """指定した IP/ポートへ TCP 接続する.

        既存の接続があればクローズし、新しいTCP接続を確立します。

        Args:
            host (str): 接続先IPアドレスまたはホスト名。
            port (int): 接続先ポート番号。
            timeout_ms (int): ソケット操作のタイムアウト時間（ミリ秒）。デフォルトは5000ms。

        Raises:
            Exception: 接続に失敗した場合。
        """
        self.close()  # 既存の接続をクローズ
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP/IPソケットを作成
        sock.settimeout(timeout_ms / 1000.0)  # タイムアウトを設定 (秒単位)
        try:
            sock.connect((host, port))  # 指定されたホストとポートに接続
        except Exception:
            sock.close()  # 接続失敗時はソケットをクローズ
            raise  # 例外を再発生
        sock.settimeout(timeout_ms / 1000.0)  # 接続後のソケットにもタイムアウトを設定
        self._socket = sock  # 確立したソケットを保持

    def close(self) -> None:
        """ソケットをクローズする.

        現在開いているソケット接続を安全に閉じます。
        """
        if self._socket is not None:
            try:
                self._socket.close()  # ソケットをクローズ
            finally:
                self._socket = None  # ソケット参照をクリア

    def is_connected(self) -> bool:
        """ソケットが有効かどうかを返す.

        Returns:
            bool: ソケットが接続されていればTrue、そうでなければFalse。
        ""
        return self._socket is not None

    # ---------------------------------------------
    # 送受信
    # ---------------------------------------------
    def transact(self, frame: List[int], retries: int = 1) -> Reply:
        """1 コマンド送信→応答フレーム取得を行う.

        指定されたフレームを送信し、それに対する応答フレームを受信して解析します。
        ソケット操作はスレッドセーフに行われます。

        Args:
            frame (List[int]): 送信するコマンドフレーム（バイト列のリスト）。
            retries (int): タイムアウト時の再試行回数。デフォルトは1回。

        Returns:
            Reply: 受信した応答フレームの解析結果。

        Raises:
            RuntimeError: ソケットが未接続の場合、または受信タイムアウトが発生した場合。
        """
        sock = self._require_socket()  # 接続済みソケットを取得
        # 送信と受信をまとめてロックし、同時実行を防ぐ
        with self._lock:
            raw = self._send_and_receive(sock, frame, retries)  # フレームを送信し、応答を受信
        parser = proto.Parser()  # プロトコルパーサーを初期化
        for b in raw:
            parser.push(b)  # 受信した生データをパーサーに投入
        _, cmd, data = parser.take()  # 解析結果（アドレス、コマンド、データ）を取得
        return Reply(cmd=cmd, data=data, raw=raw)  # Replyオブジェクトとして返す

    def receive_only(self) -> Reply:
        """送信を行わずに次の 1 フレームだけを受信する.

        すでにデータが送信されているが、その応答を再度受信したい場合などに使用します。
        ソケット操作はスレッドセーフに行われます。

        Returns:
            Reply: 受信した応答フレームの解析結果。

        Raises:
            RuntimeError: ソケットが未接続の場合、または受信タイムアウトが発生した場合。
        """
        sock = self._require_socket()  # 接続済みソケットを取得
        with self._lock:
            raw = self._receive_frame(sock)  # フレームを受信
        parser = proto.Parser()  # プロトコルパーサーを初期化
        for b in raw:
            parser.push(b)  # 受信した生データをパーサーに投入
        _, cmd, data = parser.take()  # 解析結果（アドレス、コマンド、データ）を取得
        return Reply(cmd=cmd, data=data, raw=raw)  # Replyオブジェクトとして返す

    # ---------------------------------------------
    # 内部ヘルパー
    # ---------------------------------------------
    def _require_socket(self) -> socket.socket:
        """ソケット接続が確立されていることを確認し、ソケットオブジェクトを返す.

        Returns:
            socket.socket: 接続済みのソケットオブジェクト。

        Raises:
            RuntimeError: ソケットが未接続の場合。
        """
        if self._socket is None:
            raise RuntimeError("ソケットが未接続です")
        return self._socket

    def _send_and_receive(
        self, sock: socket.socket, frame: List[int], retries: int
    ) -> List[int]:
        """指定されたフレームを送信し、応答フレームを受信する.

        タイムアウトが発生した場合、指定された回数だけ再試行します。

        Args:
            sock (socket.socket): 使用するソケットオブジェクト。
            frame (List[int]): 送信するコマンドフレーム。
            retries (int): タイムアウト時の再試行回数。

        Returns:
            List[int]: 受信した生の応答フレーム。

        Raises:
            RuntimeError: 受信タイムアウトが指定された再試行回数を超えて発生した場合。
        """
        payload = bytes(frame)  # フレームをバイト列に変換
        parser = proto.Parser()  # プロトコルパーサーを初期化
        attempt = 0  # 現在の試行回数
        last_error: Optional[Exception] = None  # 最後に発生したエラー
        while attempt <= retries:
            try:
                sock.sendall(payload)  # 全てのペイロードを送信
                raw = self._receive_frame(sock, parser)  # 応答フレームを受信
                return raw  # 成功したら生データを返す
            except socket.timeout as exc:
                last_error = exc  # タイムアウトエラーを記録
                attempt += 1  # 試行回数をインクリメント
                if attempt > retries:
                    break  # 再試行回数を超えたらループを抜ける
                # タイムアウト時は再送を試みる前にパーサーをリセット
                parser.reset()
                continue  # 次の試行へ
        raise RuntimeError(f"受信タイムアウト: {last_error}")  # 再試行後も失敗したらエラーを発生

    def _receive_frame(
        self, sock: socket.socket, parser: Optional[proto.Parser] = None
    ) -> List[int]:
        """ソケットから1バイトずつ読み込み、完全なフレームを受信する.

        プロトコルパーサーを使用して、STXからCRまでの完全なフレームを構築します。

        Args:
            sock (socket.socket): 使用するソケットオブジェクト。
            parser (Optional[proto.Parser]): 既存のプロトコルパーサー。指定がなければ新規作成。

        Returns:
            List[int]: 受信した生の応答フレーム。

        Raises:
            RuntimeError: ソケットが切断された場合。
        """
        if parser is None:
            parser = proto.Parser()  # パーサーが指定されていなければ新規作成
        while True:
            chunk = sock.recv(1)  # 1バイト受信
            if not chunk:
                raise RuntimeError("切断されました")  # 接続が切断された場合
            byte = chunk[0]  # 受信したバイト
            if parser.push(byte):  # バイトをパーサーに投入し、完全なフレームが構築されたか確認
                return parser.take_raw()  # 完全なフレームが構築されたら生データを返す


# ---------------------------------------------
# ログ用ユーティリティ
# ---------------------------------------------

def timestamp() -> str:
    """現在時刻を mm/dd HH:MM:SS.mmm 形式で返す.

    Returns:
        str: フォーマットされた現在時刻文字列。
    """

    now = datetime.now()
    return now.strftime("%m/%d %H:%M:%S.%f")[:-3]  # ミリ秒まで含む形式でフォーマット

