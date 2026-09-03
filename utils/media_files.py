import os


def collect_supported_media_paths(paths, supported_formats):
    """Expand files/folders into supported media file paths, preserving order."""
    supported = tuple(ext.lower() for ext in supported_formats)
    collected = []
    seen = set()

    def add_if_media(path):
        normalized = os.path.abspath(path)
        if normalized in seen:
            return
        ext = os.path.splitext(normalized)[1].lower()
        if os.path.isfile(normalized) and ext in supported:
            seen.add(normalized)
            collected.append(normalized)

    for path in paths or []:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs.sort()
                for filename in sorted(files):
                    add_if_media(os.path.join(root, filename))
        else:
            add_if_media(path)

    return collected
