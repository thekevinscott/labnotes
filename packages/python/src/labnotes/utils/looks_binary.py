import codecs


def looks_binary(head: bytes) -> bool:
    if b"\0" in head:
        return True
    try:
        codecs.getincrementaldecoder("utf-8")().decode(head)
    except UnicodeDecodeError:
        return True
    return False
