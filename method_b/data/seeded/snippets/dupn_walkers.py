import os


def count_python_files(root):
    n = 0
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                n += 1
    return n


def largest_file(root):
    best, size = None, -1
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            s = os.path.getsize(os.path.join(dirpath, f))
            if s > size:
                best, size = os.path.join(dirpath, f), s
    return best
