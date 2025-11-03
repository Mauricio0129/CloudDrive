allowed_extensions = {
    # Images
    "jpg","jpeg","png","webp","gif","bmp","tiff","heic","svg",
    # Documents / Text
    "pdf","txt","csv","json","xml","md","rtf",
    # Office Files
    "doc","docx","xls","xlsx","ppt","pptx",
    # Archives
    "zip","rar","7z","tar","gz",
    # Code / Config
    "py","js","ts","html","css","ini","cfg","yml","yaml"
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
        item["last_interaction"] = item["last_interaction"].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        item["created_at"] = item["created_at"].strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        if item.get("parent_folder_id"):
            item["parent_folder_id"] = str(item["parent_folder_id"]) if item["parent_folder_id"] is not None else None
    return data