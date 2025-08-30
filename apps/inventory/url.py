from django.urls import path, include
from apps.inventory.views import item_list

urlpatterns = [
    path("admin/", admin.site.urls),
    # ... tes autres routes ...
    path("items/", item_list, name="items"),   # <- AJOUT
]
