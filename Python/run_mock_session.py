"""TR3 LAN Python サンプルをモックサーバーで実行するデモスクリプト."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, List

import tr3_lan_protocol as proto
from mock_tr3_lan_device import MockTr3LanDevice
from tr3_lan_client import Tr3LanClient


@contextmanager
def start_mock_device() -> Iterator[MockTr3LanDevice]:
    """モックサーバーを起動し、利用後に必ず停止させるコンテキスト."""

    device = MockTr3LanDevice()
    device.start()
    try:
        yield device
    finally:
        device.stop()


def parse_rom_text(data: List[int]) -> str:
    """ROM 応答データを読みやすい文字列へ変換する."""

    if len(data) < 10 or data[0] != 0x90:
        return "unknown"
    major = chr(data[1])
    minor = chr(data[2]) + chr(data[3])
    patch = chr(data[4])
    series = "".join(chr(b) for b in data[5:8])
    code = "".join(chr(b) for b in data[8:10])
    return f"{major}.{minor}.{patch} {series}{code}"


def format_uid(data: List[int]) -> str:
    """UID を MSB→LSB に並べ替えて 16 進文字列に整形する."""

    uid = list(reversed(data))
    return " ".join(f"{b:02X}" for b in uid)


def main() -> None:
    """モックサーバーと通信してプロトコルの流れを確認する."""

    with start_mock_device():
        client = Tr3LanClient()
        try:
            client.connect("127.0.0.1", 9100)
            print("[info] 接続に成功しました")

            rom = client.transact(proto.build_check_rom())
            print("[recv] ROM応答:", parse_rom_text(rom.data))

            client.transact(proto.build_set_command_mode())
            print("[info] コマンドモード設定完了")

            client.transact(proto.build_switch_antenna(0))
            print("[info] ANT#0 へ切替")

            ack = client.transact(proto.build_inventory2())
            count = ack.data[1] if len(ack.data) >= 2 else 0
            print(f"[info] Inventory 件数: {count}")

            for index in range(count):
                tag = client.receive_only()
                if len(tag.data) == 9:
                    dsfid = tag.data[0]
                    uid = tag.data[1:]
                    print(f"[tag] {index + 1}: DSFID={dsfid:02X} UID={format_uid(uid)}")
                else:
                    print(f"[warn] 予期しない応答: CMD={tag.cmd:02X} DATA={tag.data}")

            client.transact(proto.build_buzzer(0x01))
            print("[info] ブザーコマンド送信")
        finally:
            client.close()
            print("[info] 切断しました")


if __name__ == "__main__":
    main()