"""TR3 LAN リーダ／ライタ制御 GUI サンプル."""

from __future__ import annotations

import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import List, Optional

import tr3_lan_protocol as proto
from tr3_lan_client import Reply, Tr3LanClient, timestamp


# =============================================
# データクラス（表示用）
# =============================================
@dataclass
class RomInfo:
    major: int = 0
    minor: int = 0
    patch: int = 0
    series: str = ""
    code: str = ""

    def to_text(self) -> str:
        return f"{self.major}.{self.minor:02d}.{self.patch} {self.series}{self.code}"


@dataclass
class InventoryTag:
    dsfid: int
    uid: List[int]

    def uid_text(self) -> str:
        # UID は表示用に MSB→LSB へ並べ替える
        ordered = list(reversed(self.uid))
        return " ".join(f"{b:02X}" for b in ordered)


# =============================================
# GUI 本体
# =============================================
class Tr3LanApp:
    """Tkinter を用いた簡易 GUI."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("TR3 LAN Python Sample")

        self.client = Tr3LanClient()
        self.worker: Optional[threading.Thread] = None
        self.worker_lock = threading.Lock()

        self.ip_var = tk.StringVar(value="192.168.0.2")
        self.port_var = tk.StringVar(value="9004")
        self.reads_var = tk.StringVar(value="1")
        self.ant_var = tk.StringVar(value="1")

        self._build_layout()
        self._set_connected(False)

    # -----------------------------------------
    # レイアウト構築
    # -----------------------------------------
    def _build_layout(self) -> None:
        frame_conn = ttk.LabelFrame(self.root, text="接続設定")
        frame_conn.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        ttk.Label(frame_conn, text="IPアドレス").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_conn, textvariable=self.ip_var, width=18).grid(
            row=0, column=1, padx=4, pady=2
        )

        ttk.Label(frame_conn, text="ポート").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_conn, textvariable=self.port_var, width=8).grid(
            row=1, column=1, padx=4, pady=2, sticky="w"
        )

        btn_conn = ttk.Button(frame_conn, text="接続", command=self._on_connect)
        btn_conn.grid(row=2, column=0, pady=4, sticky="ew")
        self.btn_conn = btn_conn

        btn_disc = ttk.Button(frame_conn, text="切断", command=self._on_disconnect)
        btn_disc.grid(row=2, column=1, pady=4, sticky="ew")
        self.btn_disc = btn_disc

        frame_param = ttk.LabelFrame(self.root, text="読取設定")
        frame_param.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)

        ttk.Label(frame_param, text="読取回数").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_param, textvariable=self.reads_var, width=6).grid(
            row=0, column=1, padx=4, pady=2, sticky="w"
        )

        ttk.Label(frame_param, text="アンテナ数 (1-3)").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_param, textvariable=self.ant_var, width=6).grid(
            row=1, column=1, padx=4, pady=2, sticky="w"
        )

        btn_inventory = ttk.Button(
            frame_param, text="Inventory 実行", command=self._on_inventory
        )
        btn_inventory.grid(row=2, column=0, columnspan=2, pady=6, sticky="ew")
        self.btn_inventory = btn_inventory

        btn_buzzer = ttk.Button(frame_param, text="ブザー", command=self._on_buzzer)
        btn_buzzer.grid(row=3, column=0, columnspan=2, pady=2, sticky="ew")
        self.btn_buzzer = btn_buzzer

        frame_log = ttk.LabelFrame(self.root, text="ログ")
        frame_log.grid(row=2, column=0, sticky="nsew", padx=8, pady=8)
        frame_log.rowconfigure(0, weight=1)
        frame_log.columnconfigure(0, weight=1)

        text = tk.Text(frame_log, width=80, height=20, state=tk.DISABLED)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(frame_log, orient=tk.VERTICAL, command=text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)
        self.log_text = text

    # -----------------------------------------
    # 状態更新
    # -----------------------------------------
    def _set_connected(self, connected: bool) -> None:
        self.btn_conn.configure(state=tk.DISABLED if connected else tk.NORMAL)
        self.btn_disc.configure(state=tk.NORMAL if connected else tk.DISABLED)
        self.btn_inventory.configure(state=tk.NORMAL if connected else tk.DISABLED)
        self.btn_buzzer.configure(state=tk.NORMAL if connected else tk.DISABLED)

    def _set_connected_async(self, connected: bool) -> None:
        self.root.after(0, lambda: self._set_connected(connected))

    # -----------------------------------------
    # ボタンハンドラ
    # -----------------------------------------
    def _on_connect(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo("実行中", "別の処理が完了するまでお待ちください")
            return

        host = self.ip_var.get().strip() or "192.168.0.2"
        try:
            port = int(self.port_var.get())
        except ValueError:
            messagebox.showerror("入力エラー", "ポート番号が正しくありません")
            return

        def task() -> None:
            try:
                self._log("info", f"[接続試行] {host}:{port}")
                self.client.connect(host, port)
                self._log("info", "接続に成功しました")
                self._set_connected_async(True)
                self._after_rom_sequence()
            except Exception as exc:  # デモのため簡易に例外処理
                self.client.close()
                self._set_connected_async(False)
                self._log("error", f"接続に失敗しました: {exc}")
                self._message_async("error", "接続エラー", str(exc))
            finally:
                with self.worker_lock:
                    self.worker = None

        t = threading.Thread(target=task, daemon=True)
        with self.worker_lock:
            self.worker = t
        t.start()

    def _after_rom_sequence(self) -> None:
        """接続直後に ROM 取得とコマンドモード設定を実施."""

        try:
            rom_reply = self._execute(proto.build_check_rom(), "ROMバージョン読取")
            info = self._parse_rom(rom_reply.data)
            if info:
                self._log("cmt", f"ROMバージョン: {info.to_text()}")
            else:
                self._log("warn", "ROM応答の形式が予想外です")

            self._execute(proto.build_set_command_mode(), "コマンドモード設定")
        except Exception as exc:
            self._log("error", f"初期コマンド実行でエラー: {exc}")
            self._message_async("error", "初期化エラー", str(exc))

    def _on_disconnect(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo("実行中", "処理完了後に切断してください")
            return
        self.client.close()
        self._set_connected(False)
        self._log("info", "切断しました")

    def _on_inventory(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo("実行中", "処理が完了するまでお待ちください")
            return

        try:
            reads = max(1, int(self.reads_var.get()))
        except ValueError:
            messagebox.showerror("入力エラー", "読取回数は整数で入力してください")
            return
        try:
            ants = max(1, min(3, int(self.ant_var.get())))
        except ValueError:
            messagebox.showerror("入力エラー", "アンテナ数は整数で入力してください")
            return

        def task() -> None:
            try:
                for i in range(reads):
                    self._log("cmt", f"-- 読取 {i + 1}/{reads} --")
                    for ant in range(ants):
                        self._inventory_once(ant)
            except Exception as exc:
                self._log("error", f"Inventory でエラー: {exc}")
                self._message_async("error", "Inventory エラー", str(exc))
            finally:
                with self.worker_lock:
                    self.worker = None

        t = threading.Thread(target=task, daemon=True)
        with self.worker_lock:
            self.worker = t
        t.start()

    def _inventory_once(self, antenna: int) -> None:
        self._log("info", f"[アンテナ切替] ANT#{antenna}")
        self._execute(proto.build_switch_antenna(antenna), "アンテナ切替")

        reply = self._execute(proto.build_inventory2(), "Inventory2")
        count = self._parse_inventory_ack(reply.data)
        if count is None:
            self._log("warn", "タグ件数応答を解釈できません")
            return

        self._log("cmt", f"UID数: {count}")
        tags: List[InventoryTag] = []
        for _ in range(count):
            tag_reply = self._receive_only()
            tag = self._parse_tag(tag_reply)
            if tag:
                tags.append(tag)
                self._log("cmt", f"DSFID: {tag.dsfid:02X}")
                self._log("cmt", f"UID  : {tag.uid_text()}")
        # 読み取りごとにブザーを鳴らす
        self._execute(proto.build_buzzer(0x01), "ブザー")

    def _on_buzzer(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            messagebox.showinfo("実行中", "処理中は操作できません")
            return

        def task() -> None:
            try:
                self._execute(proto.build_buzzer(0x01), "ブザー")
            except Exception as exc:
                self._log("error", f"ブザー制御に失敗: {exc}")
                self._message_async("error", "ブザーエラー", str(exc))
            finally:
                with self.worker_lock:
                    self.worker = None

        t = threading.Thread(target=task, daemon=True)
        with self.worker_lock:
            self.worker = t
        t.start()

    # -----------------------------------------
    # コマンド送受信ラッパー
    # -----------------------------------------
    def _execute(self, frame: List[int], title: str) -> Reply:
        self._log("send", f"{title}: {self._to_hex(frame)}")
        reply = self.client.transact(frame)
        self._log("recv", self._to_hex(reply.raw))
        return reply

    def _receive_only(self) -> Reply:
        reply = self.client.receive_only()
        self._log("recv", self._to_hex(reply.raw))
        return reply

    # -----------------------------------------
    # 応答パース
    # -----------------------------------------
    def _parse_rom(self, data: List[int]) -> Optional[RomInfo]:
        if len(data) >= 10 and data[0] == 0x90:
            def digit(c: int) -> int:
                return c - 0x30 if 0x30 <= c <= 0x39 else 0

            info = RomInfo()
            info.major = digit(data[1])
            info.minor = digit(data[2]) * 10 + digit(data[3])
            info.patch = digit(data[4])
            info.series = "".join(chr(b) for b in data[5:8])
            info.code = "".join(chr(b) for b in data[8:10])
            return info
        return None

    def _parse_inventory_ack(self, data: List[int]) -> Optional[int]:
        if len(data) == 2 and data[0] == 0xF0:
            return data[1]
        return None

    def _parse_tag(self, reply: Reply) -> Optional[InventoryTag]:
        if reply.cmd == 0x49 and len(reply.data) == 9:
            dsfid = reply.data[0]
            uid = reply.data[1:]
            return InventoryTag(dsfid=dsfid, uid=uid)
        return None

    # -----------------------------------------
    # ログ出力
    # -----------------------------------------
    def _log(self, tag: str, message: str) -> None:
        line = f"{timestamp()}  [{tag}]  {message}"
        self.root.after(0, self._append_log, line)

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _message_async(self, kind: str, title: str, message: str) -> None:
        def show() -> None:
            if kind == "error":
                messagebox.showerror(title, message)
            elif kind == "info":
                messagebox.showinfo(title, message)
            else:
                messagebox.showwarning(title, message)

        self.root.after(0, show)

    @staticmethod
    def _to_hex(data: List[int]) -> str:
        return " ".join(f"{b:02X}" for b in data)

    # -----------------------------------------
    # 実行
    # -----------------------------------------
    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    app = Tr3LanApp()
    app.run()