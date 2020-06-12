from django.shortcuts import render

def new_batch_transfer(request):
    return render(request, 'batch/index.html', {})