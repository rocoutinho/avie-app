from flask import Blueprint, render_template
from flask_login import login_required

from blueprints.auth import require_staff
from blueprints.client_area import DOSSIE_SERVICE_LABELS
from models import StyleReport

dossies_bp = Blueprint("dossies", __name__, url_prefix="/painel/dossies")
dossies_bp.before_request(require_staff)


@dossies_bp.route("/")
@login_required
def list_dossies():
    reports = StyleReport.query.order_by(StyleReport.created_at.desc()).all()

    rows = []
    for report in reports:
        if not report.is_dossie:
            continue
        services = [label for field, label, _icon in DOSSIE_SERVICE_LABELS if getattr(report, field)]
        rows.append({"report": report, "services": services})

    return render_template("dossies_list.html", rows=rows)
