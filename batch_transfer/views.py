from django.shortcuts import render

def new_batch_transfer(request):
    return render(request, 'batch_transfer/new_batch_transfer.html', {})