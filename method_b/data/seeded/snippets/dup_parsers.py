def parse_users(path):
    records = []
    with open(path, encoding="utf-8") as fh:
        header = fh.readline().strip().split(",")
        for raw in fh:
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            values = raw.split(",")
            records.append(dict(zip(header, values)))
    return records


def parse_orders(filename):
    rows = []
    with open(filename, encoding="utf-8") as f:
        cols = f.readline().strip().split(";")
        for text in f:
            text = text.strip()
            if not text or text.startswith("#"):
                continue
            fields = text.split(";")
            rows.append(dict(zip(cols, fields)))
    return rows
