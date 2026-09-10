from flask import Blueprint, render_template, request
from flask_login import login_required

from blueprints.auth import require_staff
from models import PAYMENT_STATUSES, Payment

payments_bp = Blueprint("payments", __name__, url_prefix="/painel/pagamentos")
payments_bp.before_request(require_staff)


@payments_bp.route("/")
@login_required
def list_payments():
    status = request.args.get("status") or None

    query = Payment.query
    if status:
        query = query.filter_by(status=status)
    payments = query.order_by(Payment.due_date.asc()).all()

    counts = {key: Payment.query.filter_by(status=key).count() for key, _label in PAYMENT_STATUSES}
    counts["all"] = Payment.query.count()

    return render_template(
        "payments_list.html",
        payments=payments,
        counts=counts,
        active_status=status,
    )
