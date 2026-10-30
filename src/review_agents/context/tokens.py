"""Token estimates for sizing context; never used for billing."""


def estimate_tokens(text: str) -> int:
    # About four characters per token for ASCII; CJK and other wide characters are
    # roughly one token each. Models differ, so callers leave headroom.
    ascii_chars = sum(1 for char in text if ord(char) < 128)
    return (ascii_chars + 3) // 4 + (len(text) - ascii_chars)
