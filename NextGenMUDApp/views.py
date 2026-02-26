from django.http import HttpResponse
from django.shortcuts import render


def index(request):
    return render(request, 'NextGenMUDApp/index.html')


def favicon(request):
    """Return 204 No Content so browsers stop requesting /favicon.ico."""
    return HttpResponse(status=204)
