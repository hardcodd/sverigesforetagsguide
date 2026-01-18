from django.http import HttpResponse
from django.shortcuts import render


def import_organizations(request):
    return render(request, "catalog/admin/import_organizations.html", {})
