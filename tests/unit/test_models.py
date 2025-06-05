from bot.models import encrypt, decrypt
import base64
import os


def test_encrypt_decrypt() -> None:
    key = base64.b64encode(os.urandom(32)).decode()
    text = "hello"
    cipher = encrypt(text, key)
    assert decrypt(cipher, key) == text
