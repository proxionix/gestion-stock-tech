ENDPOINTS REST

Colonnes: Path, Methods, Permissions, Payload, Response, Errors

- /api/auth/login/ | POST | AllowAny | {username,password} | {tokens,user} | 400
- /api/auth/refresh/ | POST | AllowAny | {refresh_token} | {access_token,...} | 400/401
- /api/auth/me/ | GET | IsAuthenticated | - | user | 401
- /api/auth/logout/ | POST | IsAuthenticated | - | {message} | 401

- /api/articles/ | GET,POST | ArticlePermissions | Article | list/create | 403/400
- /api/articles/{id}/ | GET,PATCH,DELETE | ArticlePermissions | Article | article | 403/404/400

- /api/my/stock/ | GET | IsTechnicianOrAdmin + Tech check | - | {stock_items} | 403
- /api/tech/{tech_id}/stock/ | GET | IsAdmin | - | {stock_items} | 404
- /api/use/ | POST | IsTechnicianOrAdmin + Tech check | {article_id,quantity,location_text,notes?} | {movement_id,balance_after} | 400/403
- /api/admin/adjust-stock/ | POST | IsAdmin | {technician_id,article_id,operation:add|remove|set,quantity,reason?,notes?} | {movement_id,balance_after} | 400/404

- /api/my/cart/ | GET | IsTechnicianOrAdmin + Tech check | - | cart summary | 403
- /api/my/cart/add/ | POST | IsTechnicianOrAdmin + Tech check | {article_id,quantity,notes?} | {line_id,quantity} | 400/403
- /api/my/cart/line/{line_id}/ | PATCH | IsTechnicianOrAdmin + Tech check | {quantity} | {line_id,quantity}|{message} | 400/403
- /api/my/cart/submit/ | POST | IsTechnicianOrAdmin + Tech check | {notes?} | {demande_id,status} | 400/403

- /api/demandes/ | GET | DemandPermissions | filters | paginated Demandes | 403
- /api/demandes/{id}/ | GET | DemandPermissions | - | Demande | 403/404
- /api/demandes/queue/ | GET | IsAdmin | ?status | {demands} | -
- /api/demandes/{id}/approve_all/ | POST | IsAdmin | {notes?} | {status} | 404/400
- /api/demandes/{id}/approve_partial/ | POST | IsAdmin | {line_approvals[],notes?} | {status} | 404/400
- /api/demandes/{id}/refuse/ | POST | IsAdmin | {reason} | {status} | 404/400
- /api/demandes/{id}/prepare/ | POST | IsAdmin | - | {status} | 404/400
- /api/demandes/{id}/handover/ | POST | IsAdmin | {method,device_info,pin?,signature_data?} | {status} | 404/400

- /api/reservations/ | GET | IsTechnicianOrAdmin | - | {reservations} | -
- /api/reservations/create/ | POST | IsTechnicianOrAdmin | {technician_id,article_id,qty_reserved,scheduled_for?,notes?} | {reservation_id,status} | 400/403/404
- /api/reservations/{id}/approve/ | POST | IsAdmin | - | {message,status} | 404/400
- /api/reservations/{id}/cancel/ | POST | IsAdmin | - | {message,status} | 404/400

- /api/transfers/ | POST | IsAdmin | {from_technician_id,to_technician_id,article_id,quantity,notes?} | {issue_movement_id,receipt_movement_id,transfer_note_pdf_size} | 400/404

- /api/articles/{id}/qr/ | GET | ArticlePermissions | - | qr meta | 404/403
- /api/articles/{id}/qr/print-sheet/ | POST | ArticlePermissions | {cols,rows,margin,count,include_text} | PDF | 400
- /api/articles/qr/print-multiple/ | POST | ArticlePermissions | {article_ids[],layout} | PDF | 400/404
- /api/articles/qr/templates/ | GET | ArticlePermissions | - | {templates} | -
- /api/articles/qr/regenerate-all/ | POST | ArticlePermissions + Admin check | - | {message,count} | 403

- /api/security/* | GET/POST | IsAdmin | varies | varies | -


