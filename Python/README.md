# TR3 LAN Python Sample

タカヤ製 TR3 シリーズ（LAN 接続モデル）を Python から操作する GUI サンプルです。
C++ 版 [TR3_LAN_CPP](https://github.com/TamaruNorio/TR3_LAN_CPP) の手順をベースに、
Tkinter 製のシンプルな画面（TR3_USB_Python に近い構成）を用意しています。

## 構成

```
python/
├─ tr3_lan_protocol.py   # フレーム生成・パーサ・コマンドビルダー
├─ tr3_lan_client.py     # ソケット通信ラッパー（send/recv とタイムアウト制御）
├─ tr3_lan_gui.py        # Tkinter GUI（接続・Inventory・ブザー制御）
├─ mock_tr3_lan_device.py # モックサーバー（自動テスト／学習用）
├─ run_mock_session.py   # モックを使ったコンソール実行例
└─ README.md             # このファイル
```

- 外部ライブラリに依存せず、標準ライブラリのみで構成しています。
- コメントは C++ 版にならい日本語で丁寧に記述してあります。

## 使い方

1. Windows 上で Python 3.10 以降をインストールします。
2. 本リポジトリを取得し、`python` ディレクトリへ移動します。

   ```bat
   cd python
   python tr3_lan_gui.py
   ```

3. GUI が起動したら以下を入力します。
   - IP アドレス（既定値: `192.168.0.2`）
   - ポート番号（既定値: `9004`）
   - 読取回数／アンテナ数（必要に応じて変更）

4. **接続** ボタンを押すと、ROM バージョン取得 → コマンドモード設定を自動実行します。
5. **Inventory 実行** ボタンで Inventory2 コマンドを指定回数・アンテナ数分だけ実行します。
   - タグ件数（ACK: `F0 NN`）と UID（CMD: `0x49`）をログに表示します。
- 読み取りごとにブザーコマンド (`0x42`) を送信します。
6. **ブザー** ボタンで任意にブザーを鳴らせます。

### モックサーバーでの確認

実機が手元にない場合は、モックサーバーを利用してプロトコルの流れを
コンソール上で確認できます。

```bash
python run_mock_session.py
```

実行するとモックサーバーが自動起動し、ROM 取得 → コマンドモード設定 →
Inventory → ブザー送信までの流れと受信結果がログとして表示されます。

### Windows 向け exe の作成（PyInstaller）

Windows 環境で Python をインストールしていない利用者へ配布したい場合は、
PyInstaller を用いて GUI を単体の exe にまとめられます。

1. コマンドプロンプトで `python` ディレクトリに移動します。
2. 初回は PyInstaller を導入します。

   ```bat
   py -3 -m pip install --upgrade pip pyinstaller
   ```

3. 付属バッチを実行して exe を生成します。

   ```bat
   build_exe.bat
   ```

   `dist\TR3_LAN_GUI\TR3_LAN_GUI.exe` が作成され、`dist` フォルダごとコピー
   すれば他 PC でも起動できます。

4. 生成物を削除したい場合は次を実行します。

   ```bat
   build_exe.bat clean
   ```

   `build/` や `dist/` など PyInstaller の成果物をまとめて削除します。

## 備考

- ソケットの送受信は 1 バイトずつ解析する状態機械で実装しています（C++ 版と同様）。
- 通信エラーやタイムアウトは `RuntimeError` として呼び出し元に伝搬します。
- 教育用サンプルとして、例外処理は簡潔にまとめています。