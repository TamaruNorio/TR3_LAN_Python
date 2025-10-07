"""TR3 LAN プロトコル処理（フレーム生成・解析）.

このモジュールは TR3 シリーズの通信プロトコルを Python で扱うための
最小限の機能を提供します。Frame/Parser クラスや代表的なコマンド生成
ヘルパーを C++ 版（TR3_LAN_CPP）の構造に合わせて実装しています。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

# =============================================
# 定数（通信プロトコル仕様に準拠）
# =============================================
STX: int = 0x02
ETX: int = 0x03
CR: int = 0x0D

HEADER_LEN: int = 4
FOOTER_LEN: int = 3


@dataclass
class Frame:
    """送信用フレームを保持するデータクラス."""

    addr: int = 0x00
    cmd: int = 0x00
    data: List[int] | None = None

    def encode(self) -> List[int]:
        """自身のフィールドから [STX..CR] の完全フレームを生成する."""

        payload = list(self.data or [])
        frame: List[int] = []
        frame.append(STX)
        frame.append(self.addr & 0xFF)
        frame.append(self.cmd & 0xFF)
        frame.append(len(payload) & 0xFF)
        frame.extend(payload)
        frame.append(ETX)
        frame.append(calc_sum(frame))
        frame.append(CR)
        return frame


def calc_sum(stx_to_etx: Iterable[int]) -> int:
    """STX〜ETX の総和（下位1バイト）を計算する."""

    total = 0
    for b in stx_to_etx:
        total = (total + b) & 0xFF
    return total


class Parser:
    """受信バイト列を解析して 1 フレームを取り出す状態機械."""

    class _State:
        SEEK_STX = 0
        HEADER = 1
        PAYLOAD = 2
        FOOTER = 3

    def __init__(self) -> None:
        self._state = self._State.SEEK_STX
        self._buffer: List[int] = []
        self._need = 0

    def reset(self) -> None:
        """内部状態をリセットして STX 探索からやり直す."""

        self._state = self._State.SEEK_STX
        self._buffer.clear()
        self._need = 0

    def push(self, byte: int) -> bool:
        """1 バイトを投入して、フレーム完成時に True を返す."""

        b = byte & 0xFF
        self._buffer.append(b)

        if self._state == self._State.SEEK_STX:
            if b == STX:
                # STX を検出したらヘッダ読取状態へ遷移
                self._buffer.clear()
                self._buffer.append(b)
                self._state = self._State.HEADER
                self._need = HEADER_LEN - 1
            else:
                self._buffer.clear()
            return False

        if self._state == self._State.HEADER:
            self._need -= 1
            if self._need == 0:
                if len(self._buffer) < HEADER_LEN:
                    self.reset()
                    return False
                data_len = self._buffer[3]
                self._need = int(data_len) + FOOTER_LEN
                self._state = self._State.PAYLOAD
            return False

        if self._state == self._State.PAYLOAD:
            self._need -= 1
            if self._need == 0:
                size = len(self._buffer)
                if size < HEADER_LEN + FOOTER_LEN:
                    self.reset()
                    return False
                if self._buffer[-1] != CR or self._buffer[-3] != ETX:
                    self.reset()
                    return False
                expected_sum = self._buffer[-2]
                calc = calc_sum(self._buffer[:-2])
                if expected_sum == calc:
                    self._state = self._State.FOOTER
                    return True
                self.reset()
            return False

        if self._state == self._State.FOOTER:
            self.reset()
            return False

        return False

    def take(self) -> tuple[int, int, List[int]]:
        """完成済みフレームから (addr, cmd, data) を取り出す."""

        if len(self._buffer) < HEADER_LEN + FOOTER_LEN:
            raise RuntimeError("フレームが完成していません")
        addr = self._buffer[1]
        cmd = self._buffer[2]
        length = self._buffer[3]
        data_end = HEADER_LEN + length
        data = list(self._buffer[HEADER_LEN:data_end])
        self.reset()
        return addr, cmd, data

    def take_raw(self) -> List[int]:
        """完成済みフレームの生バイト列を返す."""

        raw = list(self._buffer)
        self.reset()
        return raw


# =============================================
# コマンド生成ヘルパー
# =============================================

def build_check_rom(addr: int = 0x00) -> List[int]:
    frame = Frame(addr=addr, cmd=0x4F, data=[0x90])
    return frame.encode()


def build_set_command_mode(addr: int = 0x00) -> List[int]:
    frame = Frame(addr=addr, cmd=0x4E, data=[0x00, 0x00, 0x00, 0x1C])
    return frame.encode()


def build_switch_antenna(ant: int, addr: int = 0x00) -> List[int]:
    frame = Frame(addr=addr, cmd=0x4E, data=[0x9C, ant & 0xFF])
    return frame.encode()


def build_inventory2(addr: int = 0x00) -> List[int]:
    frame = Frame(addr=addr, cmd=0x78, data=[0xF0, 0x40, 0x01])
    return frame.encode()


def build_buzzer(onoff: int = 0x01, addr: int = 0x00) -> List[int]:
    frame = Frame(addr=addr, cmd=0x42, data=[onoff & 0xFF, 0x00])
    return frame.encode()
