import random

def generate_mac():
    values = [
        random.randint(0, 255)
        for _ in range(6)
    ]

    values[0] = 0x02

    return ":".join(
        f"{value:02x}"
        for value in values
    )