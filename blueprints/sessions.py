from flask import Blueprint, render_template, request
from flask_login import login_required

from blueprints.auth import require_staff
from models import CONSULTATION_STATUSES, Consultation

sessions_bp = Blueprint("sessions", __name__, url_prefix="/painel/sessoes")
sessions_bp.before_request(require_staff)


@sessions_bp.route("/")
@login_required
def list_sessions():
    status = request.args.get("status") or None

    query = Consultation.query
    if status:
        query = query.filter_by(status=status)
    consultations = query.order_by(Consultation.scheduled_at.desc()).all()

    counts = {key: Consultation.query.filter_by(status=key).count() for key, _label in CONSULTATION_STATUSES}
    counts["all"] = Consultation.query.count()

    return render_template(
        "sessions_list.html",
        consultations=consultations,
        counts=counts,
        active_status=status,
    )
