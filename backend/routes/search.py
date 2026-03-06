"""
routes/search.py  –  Search & Filter Module
Maps to: SearchFilterModule, FR-8
Supports filtering by title, status, quantity, city
"""

from flask import Blueprint, request, jsonify
from db import get_connection

search_bp = Blueprint('search', __name__)


@search_bp.route('/requirements', methods=['GET'])
def search_requirements():
    title    = request.args.get('title', '').strip()
    status   = request.args.get('status', '').strip().upper()
    city     = request.args.get('city', '').strip()
    min_qty  = request.args.get('min_qty')
    max_qty  = request.args.get('max_qty')
    sort_by  = request.args.get('sort_by', 'date')   # date | quantity | title

    # ── input validation ──────────────────────────────────────────────────────
    valid_statuses = ('', 'OPEN', 'PARTIALLY_FULFILLED', 'FULFILLED')
    if status and status not in valid_statuses:
        return jsonify({'error': f'Invalid status. Choose from {valid_statuses[1:]}'}), 400

    valid_sorts = ('date', 'quantity', 'title')
    if sort_by not in valid_sorts:
        sort_by = 'date'

    # ── build query dynamically ───────────────────────────────────────────────
    where_clauses = []
    params        = {}

    if title:
        where_clauses.append("LOWER(r.title) LIKE :title")
        params['title'] = f'%{title.lower()}%'

    if status:
        where_clauses.append("r.status = :status")
        params['status'] = status
    else:
        where_clauses.append("r.status != 'FULFILLED'")

    if city:
        where_clauses.append("LOWER(n.city) LIKE :city")
        params['city'] = f'%{city.lower()}%'

    if min_qty:
        where_clauses.append("r.quantity >= :min_qty")
        params['min_qty'] = int(min_qty)

    if max_qty:
        where_clauses.append("r.quantity <= :max_qty")
        params['max_qty'] = int(max_qty)

    order_map = {
        'date':     'r.created_at DESC',
        'quantity': 'r.quantity DESC',
        'title':    'r.title ASC'
    }
    order_clause = order_map[sort_by]

    where_sql = (' WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    sql = f"""
        SELECT r.requirement_id, r.title, r.description, r.quantity,
               r.status, r.created_at,
               n.organization_name, n.city, n.ngo_id
        FROM requirements r
        JOIN ngo_profiles n ON r.ngo_id = n.ngo_id
        {where_sql}
        ORDER BY {order_clause}
    """

    conn = get_connection()
    cur  = conn.cursor()
    try:
        # Validate criteria (mirrors validateCriteria() in class diagram)
        if not _validate_criteria(params):
            return jsonify({'error': 'Invalid search criteria provided.'}), 400

        cur.execute(sql, params)
        rows = cur.fetchall()
        results = [{
            'requirement_id': r[0], 'title': r[1], 'description': r[2],
            'quantity': r[3], 'status': r[4], 'created_at': str(r[5]),
            'ngo_name': r[6], 'city': r[7], 'ngo_id': r[8]
        } for r in rows]

        if not results:
            return jsonify({'message': 'No requirements found.', 'results': []}), 200

        return jsonify({'results': results, 'count': len(results)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        conn.close()


def _validate_criteria(params: dict) -> bool:
    """Basic validation – mirrors validateCriteria() in SearchFilterService."""
    if 'min_qty' in params and 'max_qty' in params:
        if params['min_qty'] > params['max_qty']:
            return False
    return True
