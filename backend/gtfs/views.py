from django.shortcuts import render

# Create your views here.


def gtfs(request):
    return render(request, "gtfs.html")
