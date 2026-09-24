import io
import os
import tempfile
from datetime import datetime

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core import management
from django.http import HttpResponse
from django.shortcuts import redirect, render


@staff_member_required
def backup_download(request):
    """
    Poore database ka ek clean JSON backup banata hai aur turant
    download karwa deta hai — 'One Click Backup'.
    Sirf staff/admin login wale hi ye page use kar sakte hain.
    """
    buffer = io.StringIO()
    management.call_command(
        "dumpdata",
        natural_foreign=True,
        natural_primary=True,
        exclude=["contenttypes", "auth.permission", "admin.logentry", "sessions.session"],
        indent=2,
        stdout=buffer,
    )
    data = buffer.getvalue()
    filename = f"realshree_backup_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json"
    response = HttpResponse(data, content_type="application/json")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@staff_member_required
def backup_restore(request):
    """
    Backup .json file upload karke, ek click me poora data wapas
    (naye/khaali) database me daal deta hai — 'One Click Restore'.
    """
    if request.method == "POST" and request.FILES.get("backup_file"):
        uploaded = request.FILES["backup_file"]
        tmp_path = os.path.join(tempfile.gettempdir(), "restore_upload.json")
        with open(tmp_path, "wb") as f:
            for chunk in uploaded.chunks():
                f.write(chunk)
        try:
            management.call_command("loaddata", tmp_path)
            messages.success(request, "Data successfully restore ho gaya!")
        except Exception as e:
            messages.error(request, f"Restore fail hua: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        return redirect("backup_restore")

    return render(request, "admin_tools/backup_restore.html")