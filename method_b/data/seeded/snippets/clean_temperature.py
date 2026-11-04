from dataclasses import dataclass


@dataclass(frozen=True)
class Temperature:
    celsius: float

    @property
    def fahrenheit(self):
        return self.celsius * 9 / 5 + 32

    @classmethod
    def from_fahrenheit(cls, f):
        return cls((f - 32) * 5 / 9)


def warmest(temps):
    return max(temps, key=lambda t: t.celsius)
