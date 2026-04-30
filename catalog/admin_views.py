from django.shortcuts import render


def import_organizations(request):
    return render(request, "catalog/admin/import_organizations.html", {})


def update_organizations(request):
    return render(request, "catalog/admin/update_organizations.html", {})
