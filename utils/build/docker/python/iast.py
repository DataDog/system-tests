import hashlib


def weak_hash():
    m = hashlib.md5()
    m.update(b"Nobody inspects")
    m.update(b" the spammish repetition")
    return m.digest()


def weak_hash_multiple():
    m = hashlib.md5()
    m.update(b"Nobody inspects")
    m.update(b" the spammish repetition")
    m.digest()

    m = hashlib.sha1()
    m.update(b"Nobody inspects")
    m.update(b" the spammish repetition")
    m.digest()
    return "OK"


def weak_hash_duplicates():
    for i in range(10):
        m = hashlib.md5()
        m.update(b"Nobody inspects")
        m.update(b" the spammish repetition")
        m.digest()

    return "OK"


def weak_hash_secure_algorithm():
    m = hashlib.sha256()
    m.update(b"Nobody inspects")
    m.update(b" the spammish repetition")
    return m.digest()


def weak_cipher():
    from Crypto.Cipher import ARC4

    password = b"12345678"
    data = b"abcdefgh"
    crypt_obj = ARC4.new(password)
    return crypt_obj.encrypt(data)


def weak_cipher_secure_algorithm():
    from Crypto.Cipher import AES

    key = b"Sixteen byte key"
    data = b"abcdefgh"
    crypt_obj = AES.new(key, AES.MODE_EAX)
    return crypt_obj.encrypt(data)
