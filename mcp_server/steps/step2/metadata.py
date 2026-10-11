from PIL import Image

EDITING_TOOLS = ["photoshop", "gimp", "snapseed", "picsart", "canva"]


def extract_metadata_signal(image: Image.Image) -> dict:
    exif = image.getexif()
    has_camera_tags = any((tag in exif for tag in (271, 272, 306)))
    software_tag = exif.get(305)
    flagged_software = None
    if software_tag and any((tool in str(software_tag).lower() for tool in EDITING_TOOLS)):
        flagged_software = str(software_tag)
    return {"has_camera_metadata": has_camera_tags, "flagged_software": flagged_software}
