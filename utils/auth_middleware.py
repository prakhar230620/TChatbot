from functools import wraps
from flask import redirect, request, session, url_for
from config.user import User
from urllib.parse import urlparse, urljoin

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

def validate_session(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return redirect('http://localhost:5000/login')

        user = User.get_user_by_email(user_id)
        if not user:
            return redirect('http://localhost:5000/login')

        session['user_id'] = user.email
        session['name'] = user.name
        session['is_admin'] = user.is_admin

        return f(*args, **kwargs)
    return decorated_function