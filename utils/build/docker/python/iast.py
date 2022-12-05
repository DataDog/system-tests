import hashlib


def weak_hash():
    m = hashlib.md5()
    m.update(b"Nobody inspects")
    m.update(b" the spammish repetition")
    return m.digest()


def secure_algorithm():
    m = hashlib.sha256()
    m.update(b"Nobody inspects")
    m.update(b" the spammish repetition")
    return m.digest()
