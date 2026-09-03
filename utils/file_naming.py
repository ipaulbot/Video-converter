import os


def get_unique_path(path: str) -> str:
    """Return a browser-style unique path without overwriting an existing file."""
    if not os.path.exists(path):
        return path

    directory, filename = os.path.split(path)
    stem, ext = os.path.splitext(filename)
    counter = 1

    while True:
        candidate = os.path.join(directory, f"{stem} ({counter}){ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1
