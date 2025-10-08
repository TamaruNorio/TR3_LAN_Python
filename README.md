## TAKAYA RFID リーダライタ サンプルプログラム ドキュメント

> **ドキュメントの全体像や他のサンプルプログラムについては、[こちらのランディングページ](https://tamarunorio.github.io/TAKAYA-RFID-Sample-Code/)をご覧ください。**

# TR3_LAN_Python — TR3XMシリーズ LAN制御サンプル

タカヤ製 **TR3XM（HF帯）リーダライタ** を **有線LAN (TCP/IP)** で制御するための **Pythonサンプルプログラム** です。  
ROMバージョン確認、コマンドモード切替、アンチコリジョン確認/設定、アンテナ切替、Inventory2（タグ読取）といった一連の処理を、指定回数分自動実行します。  
通信ログは `rfid_reader.log` に出力されます。

---

## 概要

このサンプルプログラムは、最小構成で TR3XM を LAN 経由で制御し、安定した受信解析と典型的な RFID 読み取りフローを学習することを目的としています。  
Python およびネットワーク通信の初学者から中級者（現場検証／デモ／PoC用途）を想定しています。

---

## 動作環境

| 項目 | 内容 |
|:------|:------|
| OS | Windows 10 以降（他OSでも Python が動作し TCP 接続できれば可） |
| Python | 3.9 以上（標準ライブラリのみ使用） |
| デバイス | TR3XM シリーズ（LAN インターフェース搭載モデル） |

> **注意:** 本サンプルは **無保証** です。実運用には、製品の基礎知識およびプロトコル仕様の理解が必要です。  
> RWManager を併用して機器設定・通信ログの確認を行ってください。

---

## セットアップと実行方法

1. **リポジトリのクローン**
   ```bash
   git clone https://github.com/TamaruNorio/TR3_LAN_Python.git
   cd TR3_LAN_Python
   ```

2. **接続先設定**  
   `src/TR3XM_LAN_sample_0.1.0.py` 冒頭の `RW_IP` と `PORT` を実機に合わせて変更します。

3. **実行**
   ```bash
   python src/TR3XM_LAN_sample_0.1.0.py
   ```
   読取回数を入力すると、その回数分アンテナ切替 → Inventory2 → UID検出時ブザーが実行されます。  
   ログは `rfid_reader.log` に追記されます。

---

## プロジェクト構成

```
TR3_LAN_Python/
├─ src/
│  └─ TR3XM_LAN_sample_0.1.0.py   # 本サンプル（LAN版）
├─ .gitignore
└─ README.md                      # このファイル
```

---

## 主な関数

- `send_command(sock, hex_str)`：HEX文字列を送信し、応答を取得。  
- `receive_full_response(sock)`：LAN受信をフレーム単位で復元。  
- `parse_response(frame)`：受信データを構造化。  
- `check_rom_version` / `set_command_mode` / `switch_antenna` / `send_inventory`：各操作を関数化。

---

## 通信仕様

### 📦 パケット構造（受信フォーマット）

全ての通信は次の **基本フォーマット** に従います：  

`STX | アドレス | コマンド | データ長 | データ部 | ETX | SUM | CR`  
（各1バイト／データ部のみ可変長）

**検証ポイント**
- `CR` / `ETX` の位置確認  
- `データ長` と実データ長の一致確認  
- `SUM`（チェックサム）整合性の確認

---

## 実装済みコマンド一覧

| 機能 | コマンド名 |
|:------|:------------|
| ROMバージョン取得 | `CHECK_ROM_VERSION` |
| コマンドモード設定 | `SET_COMMAND_MODE` |
| アンテナ切替 | `SWITCH_ANTENNA_0..2` |
| タグ読取（Inventory2） | `INVENTORY_2` |
| アンチコリジョン確認／設定 | `CHECK_ANTI_COLLISION_MODE`, `SET_ANTI_COLLISION_MODE_HIGH_SPEED_3` |
| ブザー制御 | `BUZZER_PI` |

---

## 読み取りフロー

1. ROMバージョン確認  
2. コマンドモードへ移行  
3. アンチコリジョンモード確認 → 必要に応じて「高速モード3」へ設定  
4. アンテナ切替 → Inventory2 実行 → UID検出でブザー動作  
5. 受信パース（複数レスポンスから UID 抽出）

---

## 関連ドキュメント

- [TAKAYA RFID Sample Code メインページ](https://tamarunorio.github.io/TAKAYA-RFID-Sample-Code/)
- [TR3XMシリーズ リーダライタ通信仕様書（TDR-MNL-PRCX-110）](https://github.com/TamaruNorio/TR3_LAN_Python/blob/main/docs/TDR-MNL-PRCX-110.pdf)
- [タカヤ株式会社 RFID製品サイト](https://www.product.takaya.co.jp/rfid/)

---

## ライセンス

[MIT License](./LICENSE)  
© 2025 Takaya Corporation

---

## 変更履歴

| バージョン | 日付 | 内容 |
|:--|:--|:--|
| 0.1.0 | 2024-06-06 | 初版。LAN受信のフレーム復元とInventory2最小動作を実装。 |
