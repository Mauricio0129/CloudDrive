allowed_extensions = {
    # ===== IMAGES =====
    # Common
    "jpg", "jpeg", "png", "gif", "bmp", "webp", "svg",
    # Professional/RAW
    "tiff", "tif", "raw", "cr2", "nef", "arw", "dng", "orf",
    "rw2", "pef", "srw", "raf", "3fr", "fff", "erf", "mef",
    # Apple
    "heic", "heif",
    # Other
    "ico", "cur", "pbm", "pgm", "ppm", "xbm", "xpm",

    # ===== DOCUMENTS =====
    "pdf", "txt", "rtf", "md", "tex",
    # Microsoft Office
    "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "xlsm", "xlsb", "pptm", "docm",
    # OpenOffice/LibreOffice
    "odt", "ods", "odp", "odg", "odf",
    # Other
    "pages", "numbers", "key",

    # ===== DATA =====
    "csv", "tsv", "json", "xml", "yaml", "yml",
    "ini", "cfg", "conf", "toml", "properties",

    # ===== ARCHIVES =====
    "zip", "rar", "7z", "tar", "gz", "bz2", "xz",
    "tgz", "tbz", "txz", "zipx", "iso", "dmg",

    # ===== CODE =====
    # Web
    "html", "htm", "css", "scss", "sass", "less",
    "js", "jsx", "ts", "tsx", "vue", "svelte",
    # Backend
    "py", "pyc", "pyo", "pyw",
    "java", "class", "jar",
    "go", "rs", "cpp", "c", "h", "hpp",
    "cs", "vb", "fs",
    "php", "rb", "pl", "lua", "r",
    # Shell
    "sh", "bash", "zsh", "fish", "ps1", "bat", "cmd",
    # Other
    "sql", "env", "gitignore", "dockerfile",

    # ===== VIDEO =====
    "mp4", "avi", "mov", "mkv", "webm", "flv", "wmv",
    "m4v", "mpg", "mpeg", "3gp", "3g2", "mts", "m2ts",
    "vob", "ogv", "gifv", "mng", "qt", "yuv", "rm",
    "asf", "amv", "m4p", "m4v", "mp2", "mpe", "mpv",
    "mxf", "roq", "nsv", "f4v", "f4p", "f4a", "f4b",

    # ===== AUDIO =====
    "mp3", "wav", "flac", "aac", "ogg", "m4a", "wma",
    "opus", "ape", "alac", "aiff", "aif", "mid", "midi",
    "ra", "ram", "tta", "voc", "vox", "dss", "au",
    "amr", "awb", "dct", "dss", "dvf", "gsm", "iklax",

    # ===== FONTS =====
    "ttf", "otf", "woff", "woff2", "eot",

    # ===== 3D/CAD =====
    "obj", "fbx", "stl", "dae", "3ds", "blend", "max",
    "dwg", "dxf", "skp",

    # ===== EBOOKS =====
    "epub", "mobi", "azw", "azw3", "djvu",

    # ===== EXECUTABLES (might want to block uploads!) =====
    "exe", "dll", "so", "dylib", "app", "deb", "rpm",
    "apk", "ipa", "msi", "dmg",

    # ===== MISC =====
    "log", "bak", "tmp", "cache", "swp", "DS_Store",
    "torrent", "ics", "vcf", "kml", "kmz", "gpx",
}

def get_ext(name: str) -> str:
    name = name.lower()
    return name.rsplit(".", 1)[1] if "." in name else ""


def is_allowed_extension(file_name: str) -> str | bool:
    ext = get_ext(file_name)
    return ext if ext not in allowed_extensions else True


def format_db_returning_objects(data: list):
    for item in data:
        item["id"] = str(item["id"])
        item["last_interaction"] = item["last_interaction"].strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        item["created_at"] = item["created_at"].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        if item.get("parent_folder_id"):
            item["parent_folder_id"] = (
                str(item["parent_folder_id"])
                if item["parent_folder_id"] is not None
                else None
            )
    return data
