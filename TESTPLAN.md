TEST PLAN

Jeux de données minimaux
- Users: 1 admin (ADMIN), 2 techniciens (TECH)
- Articles: 2 actifs
- StockTech: tech1/article1 = 10

Unit tests
- Reservation.can_approve/approve met status=APPROVED, réserve reserved_qty
- StockService.adjust_stock: delta, mouvements, audit
- StockService.transfer_stock: deux mouvements, audit

Intégration
- POST /api/admin/adjust-stock/ add/remove/set
- POST /api/reservations/create/ → approve/cancel
- POST /api/transfers/
- Workflow Demande: submit → approve_all → prepare → handover

E2E minimal Tech→Admin→Handover
1. Tech ajoute au panier et soumet
2. Admin approve_all
3. Admin prepare
4. Admin handover PIN (ou signature)

Sécurité & i18n
- CSP présents, CSRF exempt quick endpoints, 403 permissions

Commandes
- python manage.py test


