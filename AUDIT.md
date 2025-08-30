# Audit d'alignement fonctionnel (Admin/Technicien)

Ce document cartographie les exigences produit avec l'implémentation actuelle et les compléments livrés (stock admin, réservations, transferts, bannière post-login).

## 1) Mapping exigences ↔ code

- Comptes Admin/Tech: `apps/users/models.py` (`Profile.role`), permissions DRF `apps/api/permissions.py`.
- Stock global Admin (accès stock tech): endpoints `GET /api/tech/<id>/stock/` (IsAdmin), ajoutés: `POST /api/admin/adjust-stock/` (IsAdmin) → `apps/api/views/inventory_views.py`.
- Imputer/retirer du stock technicien: service `StockService.adjust_stock` (existant) et nouvel endpoint `admin_adjust_stock`.
- Notification post-login: bannière PWA `templates/pwa/home.html` + contexte `apps/pwa/views.py`.
- Base matériel: Articles CRUD (`apps/api/views/inventory_views.py` avec `ArticlePermissions`).
- Tech: consultation stock véhicule `/api/my/stock/`, panier `/api/my/cart/*`, soumission `/api/my/cart/submit/`.
- Demandes: workflow AdminWorkflow (approve/refuse/prepare/handover) `apps/orders/services/admin_workflow.py`.
- QR: génération + PDF `apps/inventory/services/qr_service.py`, API `apps/api/views/qr_views.py`.
- Seuils: modèles `Threshold`, alertes `ThresholdAlert`, services `threshold_service.py`, `stock_service._check_threshold_for_stock`.
- Réservations: nouveau modèle `Reservation` `apps/orders/models.py`, endpoints `reservations/*` `apps/api/views/orders_views.py`.
- Transferts Tech↔Tech: service existant `StockService.transfer_stock`, PDF stub `TransferPDFService`, endpoint `/api/transfers/`.
- Audit: `apps/audit/models.py`, `apps/audit/services/audit_service.py` — enrichi par nouveaux endpoints.
- Intégrations fournisseurs (CSV/Excel): à faire (Gap P1).
- Notifications temps réel/digest: à faire (Gap P1/P2).

## 2) Gap-analysis (P0→P2)

- P0
  - Admin adjust stock (FAIT): endpoint + audit.
  - Réservations (FAIT): modèle, approve/cancel, impact dispo.
  - Transferts (FAIT): endpoint + PDF stub + audit.
  - Bannière post-login (FAIT): PWA home.
- P1
  - RMA/SAV: modèle, états, endpoints, réintégration stock.
  - Notifications (email/webhook Slack/Teams): adapters + flags.
  - Import CSV/Excel: admin action + management command + endpoint.
  - Justification partielle obligatoire: champ raison sur partial approve.
- P2
  - Digest quotidien (Celery beat) pour seuils/demandes/transferts.
  - Push/websocket temps réel.
  - PDF QR gabarits avancés/templating.

## 3) Ce qui est couvert par les ajouts

- Admin peut imputer/retirer/poser une quantité exacte via `/api/admin/adjust-stock/` (IsAdmin), transactionnel et audité.
- Réservations créables par Tech (pour soi) ou Admin (pour n'importe quel Tech), validation Admin qui réserve `StockTech.reserved_qty`.
- Transferts entre techniciens avec double mouvement et PDF de bon de transfert (stub reportlab).
- Affichage de notifications récentes sur la page d'accueil PWA côté technicien.


