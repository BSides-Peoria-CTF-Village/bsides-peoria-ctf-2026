import os
from flask import Blueprint, session, render_template

bp = Blueprint('protected', __name__)


@bp.route('/staff')
def staff_dashboard():
    if session.get('user') != 'staff':
        return "Access Denied: Please log in as Staff.", 403

    staff_flag = os.environ.get("STAFF_FLAG", "<STAFF_FLAG not set>")

    return f"""
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <div class="container" style="margin-top:50px">
        <h1>Staff Dashboard</h1>
        <div class="alert alert-success">
            <strong>Welcome, Staff Member.</strong><br>
            Authentication successful.<br>
            Your Session Flag: <b>{staff_flag}</b>
        </div>
        <a href="/logout" class="btn btn-sm btn-danger">Logout</a>
    </div>
    """


@bp.route('/admin')
def admin_dashboard():
    if session.get('user') != 'admin':
        return "Access Denied: Admins Only.", 403

    admin_flag = os.environ.get("ADMIN_FLAG", "<ADMIN_FLAG not set>")
    return render_template('admin.html', flag=admin_flag)


@bp.route('/admin/seller-keys')
def seller_keys():
    if session.get('user') != 'admin':
        return "Access Denied: Admins Only.", 403
    return render_template('seller_keys.html')
