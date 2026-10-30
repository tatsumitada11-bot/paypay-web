from paypay_web import PayPay, PayPayLoginError


SESSION_FILE = "my_paypay.json"


def main():
    client = PayPay.load(SESSION_FILE)

    if client is None:
        phone = input("電話番号: ").strip()
        password = input("パスワード: ")
        client = PayPay()
        prefix = client.start_login(phone, password)
        if prefix is not None:
            otp = input(f"SMSの {prefix}- のあと（4桁）: ").strip()
            client.verify_otp(otp)
        print("ログインしました")
    else:
        try:
            client.ensure_alive(otp_input=lambda prefix: input(f"SMSの {prefix}- のあと（4桁）: ").strip())
        except PayPayLoginError as e:
            print(f"入り直せませんでした: {e}")
            return

    client.save(SESSION_FILE)

    balance = client.get_balance()
    print(f"残高: {balance.all_balance} 円（マネー {balance.money} / マネーライト {balance.money_light}）")

    url = input("照会したいリンク（空欄で終了）: ").strip()
    if url:
        info = client.link_check(url)
        print(f"送り主: {info.sender_name}")
        print(f"金額:   {info.amount} 円")
        print(f"状態:   {info.status}")
        if info.status == "PENDING":
            if input("受け取りますか？ [y/N]: ").strip().lower() == "y":
                client.link_receive(url, info=info)
                print("受け取りました")


if __name__ == "__main__":
    main()
