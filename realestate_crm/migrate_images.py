import os
import sys
import django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "realestate_crm.settings")
django.setup()

from core.models import Property
from django.core.files import File

def migrate_property_images():
    for prop in Property.objects.all():
        if prop.thumbnail and not str(prop.thumbnail.url).startswith("https://res.cloudinary.com"):
            try:
                print(f"Uploading: {prop.thumbnail.path}")

                with open(prop.thumbnail.path, 'rb') as f:
                    prop.thumbnail.save(
                        prop.thumbnail.name,
                        File(f),
                        save=True
                    )

                print(f"✅ Uploaded: {prop.title}")

            except Exception as e:
                print(f"❌ Error: {e}")

if __name__ == "__main__":
    migrate_property_images()