def mean(values):
    total = 0.0
    for v in values:
        total += v
    if not values:
        return 0.0
    return total / len(values)


def geometric_mean(values):
    product = 1.0
    for v in values:
        product *= v
    if not values:
        return 0.0
    return product ** (1.0 / len(values))
