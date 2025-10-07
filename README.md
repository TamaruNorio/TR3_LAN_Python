# TR3_LAN_Python — TR3XMシリーズ LAN制御サンプル

タカヤ製 **TR3XM（HF帯）リーダライタ**を **有線LAN (TCP/IP)** で制御するための **Pythonサンプル**です。  
ROMバージョン確認 → コマンドモード切替 → アンチコリジョン確認/設定 → アンテナ切替 → Inventory2（タグ読取）という一連の流れを、読み取り回数を指定して実行します。ログはファイルへ出力します。

---

## 目的と想定読者

- **目的**：最小構成で TR3XM を LAN 経由制御し、**安定した受信パース**と**典型フロー**を学ぶこと。  
- **想定読者**：Python/ネットワーク初学者〜中級者（現場検証／デモ／PoC）。

---

## 動作確認環境

- OS: Windows 10 以降（他OSでも Python が動作し TCP 接続できれば概ね可）
- Python: 3.9+（標準ライブラリのみ使用）
- デバイス: TR3XMシリーズ（LANインターフェース）

> 注意：本サンプルは**無保証**です。実運用には製品の基礎知識・プロトコル仕様の理解が必要です（RWManager で機器設定・通信ログ確認を併用）。

---

## 仕組みの概要

### パケット構造（受信フォーマット）

すべての通信は次の**基本フォーマット**に従います：

`STX | アドレス | コマンド | データ長 | データ部 | ETX | SUM | CR`（各1バイト/データ部のみ可変）  

**検証の要点**
- `CR`/`ETX` の位置確認、`データ長` と実長一致、`SUM`（チェックサム）一致の確認を行います。

### 実装済みの主なコマンド

- **ROMバージョン読み取り**: `CHECK_ROM_VERSION`  
- **コマンドモード設定**: `SET_COMMAND_MODE`  
- **アンテナ切替**: `SWITCH_ANTENNA_0..2`  
- **Inventory2（UID取得）**: `INVENTORY_2`  
- **アンチコリジョン確認/設定**: `CHECK_ANTI_COLLISION_MODE`, `SET_ANTI_COLLISION_MODE_HIGH_SPEED_3`  
- **ブザー**: `BUZZER_PI`  

### 読み取りフロー

1. **ROMバージョン確認**
2. **コマンドモードへ移行**
3. **アンチコリジョンモード確認** → 必要に応じて **高速モード3** に設定
4. **アンテナ切替 → Inventory2実行 → UID検出でブザー**
5. **受信パース**（複数レスポンスからUID抽出）

---

## セットアップ

```bash
git clone https://github.com/TamaruNorio/TR3_LAN_Python.git
cd TR3_LAN_Python
```

Python 実行環境は標準ライブラリのみ使用。追加インストール不要。

**接続先設定**：`TR3XM_LAN_sample_0.1.0.py` 冒頭で `RW_IP` と `PORT` を実機に合わせて変更。

---

## 実行方法

```bash
python TR3XM_LAN_sample_0.1.0.py
```

読取回数を入力 → その回数だけ  
アンテナ切替 → Inventory2 → UID検出時ブザー。  
ログは `rfid_reader.log` に追記出力されます。

---

## 主な関数

- `send_command(sock, hex_str)`：HEX文字列を送信し、応答を取得。
- `receive_full_response(sock)`：LAN受信をフレーム単位で復元。
- `parse_response(frame)`：受信データを構造化。
- `check_rom_version` / `set_command_mode` / `switch_antenna` / `send_inventory`：各操作を関数化。

---

## トラブルシューティング

- IP/ポートが正しいか（RWManagerで確認）
- アンテナ数が実機と一致しているか
- 受信途切れ時はSTX/ETX/SUM検証を確認
- UIDが出ない場合はタグ距離とアンテナ配置を確認

---

## 参考資料

- TR3/UTR/LTRシリーズ 制御用ソフト開発方法（Ver.1.03）  
- 通信インターフェース仕様書（TDR-OTH-PROGRAMMING-103.pdf）

---

## ライセンス

MIT License（予定）

---

## 変更履歴

- 0.1.0 (2024-06-06): 初版。LAN受信のフレーム復元とInventory2最小動作を実装。
