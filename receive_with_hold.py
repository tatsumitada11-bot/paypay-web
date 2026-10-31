"""保留対処つきの受け取りフロー。自販機・代行Botなど、通信エラーで
「受け取れたのかどうか分からない」状態を正しく処理するためのお手本。

このフローが解く問題：
- link_receive の応答がタイムアウトすると、お金を受け取れたか失敗したか分からない
- そのまま「失敗」にすると、本当は受け取っていたお金を無かったことにしてしまう
- そのまま「成功」にすると、受け取れていないのに商品を渡してしまう
- → 保留にして、あとから確実に判定する

判定の順番（速くて確実な順）：
1. link_check の isReceiver を見る（1回の通信で済む。2026-10から入った新しい項目）
2. 取引履歴から orderId + 金額 で探す（確実だが遅い）
3. リンクが CANCELED / EXPIRED になっていたら、諦めて「失敗」
"""

import time

from paypay_web import (
    PayPay,
    PayPayAcceptError,
    PayPayAcceptUnknownError,
    PayPayError,
    PayPayLinkGoneError,
    PayPayLoginError,
    find_receive_in_history,
    is_link_dead,
    is_link_received_by_me,
)


HOLD_RETRY_SECONDS = 15

HOLD_MAX_RETRIES = 160


def receive_with_hold(client: PayPay, url: str, passcode: str | None = None) -> str:
    """送金リンクを受け取る。応答が怪しいときは保留にして、確実な判定が出るまで繰り返す。

    戻り値：
      "RECEIVED"  成功（受け取り確認済み）
      "GONE"      リンクが別のアカウントに受け取られた・期限切れ・キャンセル
      "FAILED"    保留のまま最大回数に達した（人が確認）
      "LOGIN"     ログインが切れている（呼び出し側で入り直してからもう一度）
    """
    info = client.link_check(url)
    if is_link_received_by_me(info.raw):
        return "RECEIVED"
    if is_link_dead(info.raw):
        return "GONE"

    order_id = info.order_id
    amount = info.amount

    try:
        client.link_receive(url, passcode=passcode, info=info)
        return "RECEIVED"
    except PayPayLinkGoneError:
        return "GONE"
    except PayPayLoginError:
        return "LOGIN"
    except PayPayAcceptError:
        return "FAILED"
    except PayPayAcceptUnknownError:
        pass

    for i in range(HOLD_MAX_RETRIES):
        time.sleep(HOLD_RETRY_SECONDS)

        try:
            info = client.link_check(url)
        except PayPayLoginError:
            return "LOGIN"
        except PayPayError:
            continue

        if is_link_received_by_me(info.raw):
            return "RECEIVED"

        try:
            history = client.get_history(size=20)
        except PayPayLoginError:
            return "LOGIN"
        except PayPayError:
            history = {}
        if order_id and amount and find_receive_in_history(history, order_id, amount):
            return "RECEIVED"

        if is_link_dead(info.raw):
            return "GONE"

    return "FAILED"


if __name__ == "__main__":
    client = PayPay.load("session.json")
    if client is None:
        raise SystemExit("先に example.py でログインしてセッションを作ってください")
    client.ensure_alive(otp_input=input)

    url = input("受け取るリンク: ").strip()
    result = receive_with_hold(client, url)
    print({"RECEIVED": "受け取り成功", "GONE": "リンクが既に処理済み", "FAILED": "確認できず（要人力）", "LOGIN": "ログイン切れ"}[result])

    client.save("session.json")
