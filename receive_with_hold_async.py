"""保留対処つきの受け取りフロー（非同期版）。discord.py など asyncio ベースのBot向け。

同期版 receive_with_hold.py と中身は同じ。sleep と、PayPay への通信を asyncio.to_thread で
別スレッドに逃がしているだけ。Botのイベントループを止めない。
"""

import asyncio

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


async def receive_with_hold(client: PayPay, url: str, passcode: str | None = None) -> str:
    """送金リンクを非同期で受け取る。応答が怪しいときは保留にして、確実な判定が出るまで繰り返す。

    戻り値：
      "RECEIVED"  成功（受け取り確認済み）
      "GONE"      リンクが別のアカウントに受け取られた・期限切れ・キャンセル
      "FAILED"    保留のまま最大回数に達した（人が確認）
      "LOGIN"     ログインが切れている（呼び出し側で入り直してからもう一度）
    """
    try:
        info = await asyncio.to_thread(client.link_check, url)
    except PayPayLoginError:
        return "LOGIN"
    except PayPayError:
        return "FAILED"

    if is_link_received_by_me(info.raw):
        return "RECEIVED"
    if is_link_dead(info.raw):
        return "GONE"

    order_id = info.order_id
    amount = info.amount

    try:
        await asyncio.to_thread(client.link_receive, url, passcode, info)
        return "RECEIVED"
    except PayPayLinkGoneError:
        return "GONE"
    except PayPayLoginError:
        return "LOGIN"
    except PayPayAcceptError:
        return "FAILED"
    except PayPayAcceptUnknownError:
        pass

    for _ in range(HOLD_MAX_RETRIES):
        await asyncio.sleep(HOLD_RETRY_SECONDS)

        try:
            info = await asyncio.to_thread(client.link_check, url)
        except PayPayLoginError:
            return "LOGIN"
        except PayPayError:
            continue

        if is_link_received_by_me(info.raw):
            return "RECEIVED"

        try:
            history = await asyncio.to_thread(client.get_history, 20)
        except PayPayLoginError:
            return "LOGIN"
        except PayPayError:
            history = {}
        if order_id and amount and find_receive_in_history(history, order_id, amount):
            return "RECEIVED"

        if is_link_dead(info.raw):
            return "GONE"

    return "FAILED"
