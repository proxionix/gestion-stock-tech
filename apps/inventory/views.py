# ajoute en bas du fichier
from django.shortcuts import render
from .models import Article  # ou Item si ton modèle s'appelle autrement

def item_list(request):
    items = Article.objects.all().order_by('reference')
    return render(request, 'inventory/item_list.html', {'items': items})
