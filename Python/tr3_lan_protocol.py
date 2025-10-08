
"""TR3 LAN プロトコル処理（フレーム生成・解析）.

このモジュールはタカヤ製TR3シリーズの通信プロトコルをPythonで扱うための
最小限の機能を提供します。Frame/Parserクラスや代表的なコマンド生成
ヘルパーをC++版（TR3_LAN_CPP）の構造に合わせて実装しています。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List

# =============================================
# 定数（通信プロトコル仕様に準拠）
# =============================================
STX: int = 0x02  # Start of Text: フレーム開始を示すバイト
ETX: int = 0x03  # End of Text: データ部の終了を示すバイト
CR: int = 0x0D   # Carriage Return: フレームの終端を示すバイト
HEADER_LEN: int = 4  # ヘッダー部の長さ (STX, アドレス, コマンド, データ長)
FOOTER_LEN: int = 3  # フッター部の長さ (ETX, SUM, CR)


@dataclass
class Frame:
    """送信用フレームを保持するデータクラス.

    TR3リーダライタへ送信するコマンドフレームの構成要素を定義します。
    """
    addr: int = 0x00  # アドレス (通常は0x00)
    cmd: int = 0x00   # コマンドコード
    data: List[int] | None = None  # データ部（バイト列のリスト）

    def encode(self) -> List[int]:
        """自身のフィールドから [STX..CR] の完全フレームを生成する.

        Returns:
            List[int]: 送信準備ができた完全なフレーム（バイト列のリスト）。
        """
        payload = list(self.data or [])  # データ部が存在しない場合は空リスト
        frame: List[int] = []
        frame.append(STX)  # STX
        frame.append(self.addr & 0xFF)  # アドレス
        frame.append(self.cmd & 0xFF)   # コマンド
        frame.append(len(payload) & 0xFF)  # データ長
        frame.extend(payload)  # データ部
        frame.append(ETX)  # ETX
        frame.append(calc_sum(frame))  # チェックサム (SUM)
        frame.append(CR)  # CR
        return frame


def calc_sum(stx_to_etx: Iterable[int]) -> int:
    """STX〜ETX の総和（下位1バイト）を計算する.

    Args:
        stx_to_etx (Iterable[int]): STXからETXまでのバイト列。

    Returns:
        int: 計算されたチェックサム（下位1バイト）。
    """
    total = 0
    for b in stx_to_etx:
        total = (total + b) & 0xFF  # 256で割った余り（下位1バイト）を保持
    return total


class Parser:
    """受信バイト列を解析して 1 フレームを取り出す状態機械.

    TR3リーダライタからの受信データを1バイトずつ処理し、
    完全なフレームが構築されたかどうかを判定します。
    """

    class _State:
        """パーサーの内部状態を定義する列挙型."""
        SEEK_STX = 0  # STXを探索中
        HEADER = 1    # ヘッダー部を読み込み中
        PAYLOAD = 2   # データ部を読み込み中
        FOOTER = 3    # フッター部を読み込み中

    def __init__(self) -> None:
        """Parserのコンストラクタ.

        パーサーの初期状態とバッファをセットアップします。
        """
        self._state = self._State.SEEK_STX  # 初期状態はSTX探索
        self._buffer: List[int] = []        # 受信バイトを一時的に保持するバッファ
        self._need = 0                      # 次に読み込むべきバイト数

    def reset(self) -> None:
        """内部状態をリセットして STX 探索からやり直す

        エラー発生時や新しいフレームの解析を開始する際に呼び出します。
        """
        self._state = self._State.SEEK_STX
        self._buffer.clear()
        self._need = 0

    def push(self, byte: int) -> bool:
        """1 バイトを投入して、フレーム完成時に True を返す.

        受信したバイトをパーサーに渡し、フレームの構築を進めます。

        Args:
            byte (int): 受信した1バイトのデータ。

        Returns:
            bool: 完全なフレームが構築された場合にTrue、それ以外はFalse。
        """
        b = byte & 0xFF  # バイト値を0-255の範囲に正規化
        self._buffer.append(b)  # バッファにバイトを追加

        if self._state == self._State.SEEK_STX:
            if b == STX:
                # STX を検出したらヘッダ読取状態へ遷移
                self._buffer.clear()  # STXより前のデータは不要なのでクリア
                self._buffer.append(b)  # STXをバッファに追加
                self._state = self._State.HEADER
                self._need = HEADER_LEN - 1  # STXを除いたヘッダーの残りバイト数
            else:
                self._buffer.clear()  # STXが見つからない場合はバッファをクリアして再探索
            return False

        if self._state == self._State.HEADER:
            self._need -= 1
            if self._need == 0:
                # ヘッダーが完全に受信されたか確認
                if len(self._buffer) < HEADER_LEN:
                    self.reset()  # 不正な状態なのでリセット
                    return False
                data_len = self._buffer[3]  # データ長を取得
                self._need = int(data_len) + FOOTER_LEN  # データ部とフッター部の合計バイト数
                self._state = self._State.PAYLOAD  # データ部読取状態へ遷移
            return False

        if self._state == self._State.PAYLOAD:
            self._need -= 1
            if self._need == 0:
                # データ部とフッターが完全に受信されたか確認
                size = len(self._buffer)
                if size < HEADER_LEN + FOOTER_LEN:
                    self.reset()  # 不正な状態なのでリセット
                    return False
                # CRとETXの位置を確認
                if self._buffer[-1] != CR or self._buffer[-3] != ETX:
                    self.reset()  # 不正なフレームなのでリセット
                    return False
                expected_sum = self._buffer[-2]  # 受信したチェックサム
                calc = calc_sum(self._buffer[:-2])  # STXからETXまでのチェックサムを計算
                if expected_sum == calc:
                    self._state = self._State.FOOTER  # フレームが有効なのでフッター状態へ遷移
                    return True  # フレーム完成
                self.reset()  # チェックサム不一致なのでリセット
            return False

        if self._state == self._State.FOOTER:
            # フレームが完成し、take()が呼ばれるのを待つ状態
            # take()が呼ばれたらreset()されるため、ここでは常にFalseを返す
            self.reset() # 既にフレームが完成しているので、次のバイトは新しいフレームの開始とみなす
            return False

        return False # 未定義の状態

    def take(self) -> tuple[int, int, List[int]]:
        """完成済みフレームから (addr, cmd, data) を取り出す.

        フレームが完成している場合にのみ呼び出してください。

        Returns:
            tuple[int, int, List[int]]: アドレス、コマンド、データ部のタプル。

        Raises:
            RuntimeError: フレームが完成していない場合。
        """
        if len(self._buffer) < HEADER_LEN + FOOTER_LEN:
            raise RuntimeError("フレームが完成していません")

        addr = self._buffer[1]  # アドレス
        cmd = self._buffer[2]   # コマンド
        length = self._buffer[3]  # データ長
        data_end = HEADER_LEN + length
        data = list(self._buffer[HEADER_LEN:data_end])  # データ部を抽出
        self.reset()  # フレームを取り出したのでパーサーをリセット
        return addr, cmd, data

    def take_raw(self) -> List[int]:
        """完成済みフレームの生バイト列を返す.

        フレームが完成している場合にのみ呼び出してください。

        Returns:
            List[int]: 受信した生のフレーム（STXからCRまで）。
        """
        raw = list(self._buffer)  # バッファの内容をコピー
        self.reset()  # フレームを取り出したのでパーサーをリセット
        return raw


# =============================================
# コマンド生成ヘルパー
# =============================================

def build_check_rom(addr: int = 0x00) -> List[int]:
    """ROMバージョン確認コマンドフレームを生成する.

    Args:
        addr (int): リーダライタのアドレス。デフォルトは0x00。

    Returns:
        List[int]: ROMバージョン確認コマンドフレーム。
    """
    frame = Frame(addr=addr, cmd=0x4F, data=[0x90])
    return frame.encode()

def build_set_command_mode(addr: int = 0x00) -> List[int]:
    """コマンドモード設定コマンドフレームを生成する.

    Args:
        addr (int): リーダライタのアドレス。デフォルトは0x00。

    Returns:
        List[int]: コマンドモード設定コマンドフレーム。
    """
    frame = Frame(addr=addr, cmd=0x4E, data=[0x00, 0x00, 0x00, 0x1C])
    return frame.encode()

def build_switch_antenna(ant: int, addr: int = 0x00) -> List[int]:
    """アンテナ切替コマンドフレームを生成する.

    Args:
        ant (int): 切り替えるアンテナ番号。0から始まる。
        addr (int): リーダライタのアドレス。デフォルトは0x00。

    Returns:
        List[int]: アンテナ切替コマンドフレーム。
    """
    frame = Frame(addr=addr, cmd=0x4E, data=[0x9C, ant & 0xFF])
    return frame.encode()

def build_inventory2(addr: int = 0x00) -> List[int]:
    """Inventory2（タグ読み取り）コマンドフレームを生成する.

    Args:
        addr (int): リーダライタのアドレス。デフォルトは0x00。

    Returns:
        List[int]: Inventory2コマンドフレーム。
    """
    frame = Frame(addr=addr, cmd=0x78, data=[0xF0, 0x40, 0x01])
    return frame.encode()

def build_buzzer(onoff: int = 0x01, addr: int = 0x00) -> List[int]:
    """ブザー制御コマンドフレームを生成する.

    Args:
        onoff (int): ブザーのON/OFFまたは鳴らし方を示す値。0x00:OFF, 0x01:ON。
        addr (int): リーダライタのアドレス。デフォルトは0x00。

    Returns:
        List[int]: ブザー制御コマンドフレーム。
    """
    frame = Frame(addr=addr, cmd=0x42, data=[onoff & 0xFF, 0x00])
    return frame.encode()

