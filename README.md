# paypay-web

Web版PayPay（`www.paypay.ne.jp/app`）を Python から叩くための1ファイルのクライアント。

- SMS認証でログイン → 2回目からは同じ `client_uuid` でSMSを省ける
- ログインの状態（クッキー・uuid・パスワード）はJSONに保存できる
- 期限が切れたら、保存したパスワードで自動で入り直せる（SMSが要るときは `otp_input` を呼ぶ）

## 入れ方

```
pip install curl_cffi
```

`paypay_web.py` を手元のプロジェクトに置くか、このリポジトリをcloneして使う。

## 使い方

`example.py` 参照。短く言うと：

```python
from paypay_web import PayPay

# 最初（SMSが届く）
client = PayPay()
prefix = client.start_login("09012345678", "password")
if prefix is not None:
    client.verify_otp(input(f"SMSの {prefix}- のあと: "))
client.save("session.json")

# 2回目以降（SMSなし。期限が切れたらここで自動で入り直す）
client = PayPay.load("session.json")
client.ensure_alive(otp_input=input)
balance = client.get_balance()

# 送金リンク
info = client.link_check("https://pay.paypay.ne.jp/XXXX")
if info.status == "PENDING":
    client.link_receive("https://pay.paypay.ne.jp/XXXX", info=info)
```

## できること

| 機能 | メソッド |
|---|---|
| SMSログイン | `start_login(phone, password)` → `verify_otp(code)` |
| 同じuuidで入り直し | `relogin(password=None)` |
| SMSの再送 | `resend_otp()` |
| 期限チェック＋自動入り直し | `ensure_alive(password=None, otp_input=None)` |
| 残高 | `get_balance()` |
| 取引履歴 | `get_history(size)` |
| プロフィール | `get_profile()` |
| 送金リンクの照会 | `link_check(url_or_code)` |
| 送金リンクの受け取り | `link_receive(url_or_code, passcode=None, info=None)` |
| 自分が受け取ったか | `paypay_web.is_link_received_by_me(info.raw)` |

## 分かっていること

- アクセストークンは発行時刻にかかわらず、だいたい毎日決まった時刻に切れる（1アカウント・1uuidごと）。`expires_in` で何秒持つかは PayPay が答える
- Web版からの「送金リンクの作成」は PayPay 側で断られる（`P2P_LINK_WEB_SENDER`）
- Web版はログインしないと `getP2PLinkInfo` も使えない（アプリ版は未ログインでも照会できた）
- 送信元IPが PayPay のブロック対象（データセンターなど）だと `IP_BLACKLIST`（`01101007`）で全部弾かれる
- Web画面の JS で見える版は `5.72.0`（2026-10-30 時点）。Webには版チェックは無く、クライアントは版を名乗らない

## できないこと（Web版の制限）

- 送金リンクの作成（`P2P_LINK_WEB_SENDER`）
- 相手を指定した直接送金（通信先がWeb側にない）
- リフレッシュトークン（Web版は発行しない）

## 気をつけること

- PayPay は非公式なアクセスを認めていません。これを使う責任はご自身にあります
- 保存したJSONには電話番号・パスワード・クッキーがそのまま入ります。他人に渡さないでください
- SMSログインを3回失敗するとアカウントが一時ロックされます
- セッションを作りすぎたり、同じアカウントで短時間に何度も入り直すと、PayPayに警戒されます

## 使ったもの

[curl_cffi](https://github.com/lexiforest/curl_cffi) 。ブラウザのふりをしたHTTPクライアント。
