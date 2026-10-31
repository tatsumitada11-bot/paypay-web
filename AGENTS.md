# AI向け：Botへの組み込み手順

このファイルは、別のAI（Claude Code、ChatGPTなど）に向けた手順書です。
ユーザーから「このGitHubを使って、BotにPayPay受け取りを足して」と頼まれたら、以下の順でやってください。

## 1. 先にユーザーに聞くこと（1回だけ）

- Botは Discord bot（discord.py）か、それ以外か？ → discord.py なら `receive_with_hold_async.py` を使う。それ以外なら同期版の `receive_with_hold.py`
- 既に PayPay 関連のコード（ログイン・リンク受け取り）があるか？ → あれば置き換え、無ければ新規追加
- 受け取り結果（成功・失敗・保留切れ）をユーザーにどう知らせているか？（DM・チャンネル投稿・Webhookなど）

これ以上は聞かずに、既存コードを読んで判断してください。

## 2. ファイルの置き方

Botのフォルダ直下に、以下の2ファイルをそのままコピー：

- `paypay_web.py` ← クライアント本体。中は触らない
- `receive_with_hold.py` または `receive_with_hold_async.py` ← 受け取りの型。中は触らない

依存は `curl_cffi` のみ。`requirements.txt` に `curl_cffi>=0.16` を足す。

## 3. ログイン画面を作る

Botのユーザー向けコマンド（例：`/paypay` スラッシュコマンド）に、以下の2段階ログインを実装：

1. **1段階目**：ユーザーが電話番号＋パスワードを入れる → `PayPay().start_login(phone, password)` を呼ぶ
   - 戻り値 `None` → すでに通った。`client.save("paypay.json")`
   - 戻り値 文字列（SMS接頭辞） → ユーザーに「SMSの `○○-` のあとの4桁を入れて」と出す
2. **2段階目**：ユーザーが4桁を入れる → `client.verify_otp(code)` を呼ぶ → `client.save("paypay.json")`

重要：**`client.client_uuid` を2回目のログイン以降も使い回す**こと。`PayPay()` を毎回新しく作ると、PayPay側が「新しい端末」と見なしてSMSを毎回求めてくる。保存ファイルから `PayPay.load()` で復元すれば自動的に維持される。

## 4. 受け取り処理を差し替える

既存の受け取り処理（例：`async def receive_paypay_link(url): ...`）があれば、中身を以下のように差し替え：

```python
from paypay_web import PayPay
from receive_with_hold_async import receive_with_hold

async def receive_paypay_link(url: str, passcode: str | None = None) -> str:
    client = PayPay.load("paypay.json")
    if client is None:
        return "LOGIN"
    await asyncio.to_thread(client.ensure_alive)  # 期限が切れていたら自動で入り直し
    client.save("paypay.json")
    result = await receive_with_hold(client, url, passcode=passcode)
    client.save("paypay.json")  # クッキーが更新されたかもしれない
    return result  # "RECEIVED" / "GONE" / "FAILED" / "LOGIN"
```

既存のコードが同期なら `receive_with_hold.py` の方を使う。

## 5. 返り値ごとの処理

Botの既存の仕組みに合わせて、以下のように振り分け：

- `"RECEIVED"` → 商品を渡す・ポイント加算など、本来の処理を実行
- `"GONE"` → 「このリンクは既に受け取り済み・期限切れ・辞退済みです」とユーザーに案内。商品は渡さない
- `"FAILED"` → 「確認できませんでした。管理者が確認します」とユーザーに案内。管理者にも通知する
- `"LOGIN"` → オーナーに「PayPayのログインが切れました」とDMする。ユーザーには「一時的に受け取れません」と案内

既存に類似の分岐があればそれに合わせる。無ければ新規追加。

## 6. 保存ファイルの扱い

`paypay.json` には電話番号・パスワード・ログインクッキーが入る。以下を守る：

- `.gitignore` に `paypay.json` を追加
- Dockerなどで動かす場合、ボリュームマウントして揮発させない
- Botと同じフォルダに置く（絶対パスで指定でもOK）

## 7. やらないこと

- `paypay_web.py` と `receive_with_hold*.py` の中身は変更しない。アップデートが来たときに差し替えやすくするため
- `create_link`（送金リンク作成）を期待する実装はしない。PayPayのWeb版では塞がれている
- 送金処理（相手を指定して送る）も実装しない。同じく塞がれている
- 受け取り処理をリトライループで囲まない。`receive_with_hold` が内部でリトライするので二重になる

## 8. 動作確認

ユーザー本人に以下をやってもらう（AI側では実行しない）：

1. 別のアカウントから1円の送金リンクを作る
2. そのリンクをBotに渡す
3. ログに「`RECEIVED`」が出て、Bot上の処理が走ることを確認
4. もう一度同じリンクを渡して、`GONE` になることを確認

## 補足：なぜ保留対処が必要か

`link_receive` の応答がネットワーク都合で消えると、「受け取れた」のか「失敗した」のか分かりません。
- 失敗扱いにすると、本当は受け取ったお金を無かったことにしてしまう
- 成功扱いにすると、受け取っていないのに商品を渡してしまう

`receive_with_hold` は、この「分からない」状態を保留にして、2つの手段で判定します：
1. `link_check` の応答に含まれる `receiver.isReceiver` ← 2026-10から入った新項目。1回の通信で判定
2. 取引履歴から `orderId` と金額で照合 ← 遅いが確実
