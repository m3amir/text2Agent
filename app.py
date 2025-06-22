#!/usr/bin/env python3
"""
Simple Flask app for Cognito user registration
"""

from flask import Flask, request, redirect, flash, session
import os
import sys

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.cognito import CognitoAuth

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'simple-secret-key')

@app.route('/')
def index():
    """Registration page"""
    messages = []
    if session.get('_flashes'):
        messages = [f'<div class="alert alert-danger">{msg[1]}</div>' for msg in session['_flashes'] if msg[0] == 'error']
        messages += [f'<div class="alert alert-success">{msg[1]}</div>' for msg in session['_flashes'] if msg[0] == 'success']
        session['_flashes'] = []
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cognito Registration</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
            .card {{ border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
        </style>
    </head>
    <body>
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body p-5">
                            <h2 class="text-center mb-4">Sign Up</h2>
                            {''.join(messages)}
                            <form method="POST" action="/signup">
                                <div class="mb-3">
                                    <label class="form-label">Username</label>
                                    <input type="text" name="username" class="form-control" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Email</label>
                                    <input type="email" name="email" class="form-control" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Password</label>
                                    <input type="password" name="password" class="form-control" required minlength="8">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Confirm Password</label>
                                    <input type="password" name="confirm_password" class="form-control" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Account Type</label>
                                    <select name="user_tier" class="form-select" required>
                                        <option value="standard" selected>Standard (Free)</option>
                                        <option value="premium">Premium ($9.99/month)</option>
                                    </select>
                                    <div class="form-text">You can upgrade or downgrade your account type later.</div>
                                </div>
                                <button type="submit" class="btn btn-primary w-100">Sign Up</button>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/signup', methods=['POST'])
def signup():
    """Handle registration"""
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    confirm_password = request.form['confirm_password']
    user_tier = request.form.get('user_tier', 'standard')
    
    # Basic validation
    if not all([username, email, password, confirm_password]):
        flash('All fields are required', 'error')
        return redirect('/')
    
    if password != confirm_password:
        flash('Passwords do not match', 'error')
        return redirect('/')
    
    if len(password) < 8:
        flash('Password must be at least 8 characters long', 'error')
        return redirect('/')
    
    # Validate user tier
    if user_tier not in ['standard', 'premium']:
        flash('Invalid account type selected', 'error')
        return redirect('/')
    
    # Attempt registration with user tier
    auth = CognitoAuth()
    result = auth.sign_up(username, email, password, user_tier)
    
    if result['success']:
        tier_text = 'Premium' if user_tier == 'premium' else 'Standard'
        flash(f'Registration successful! {tier_text} account created. Please check your email for a confirmation code.', 'success')
        session['pending_username'] = username
        session['user_tier'] = user_tier
        return redirect('/confirm')
    else:
        flash(f"Registration failed: {result['message']}", 'error')
        return redirect('/')

@app.route('/confirm')
def confirm():
    """Confirmation page"""
    username = session.get('pending_username', '')
    messages = []
    if session.get('_flashes'):
        messages = [f'<div class="alert alert-danger">{msg[1]}</div>' for msg in session['_flashes'] if msg[0] == 'error']
        messages += [f'<div class="alert alert-success">{msg[1]}</div>' for msg in session['_flashes'] if msg[0] == 'success']
        session['_flashes'] = []
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Confirm Registration</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
            .card {{ border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
        </style>
    </head>
    <body>
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body p-5">
                            <h2 class="text-center mb-4">Confirm Your Email</h2>
                            {''.join(messages)}
                            <form method="POST" action="/confirm">
                                <div class="mb-3">
                                    <label class="form-label">Username</label>
                                    <input type="text" name="username" class="form-control" value="{username}" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Confirmation Code</label>
                                    <input type="text" name="confirmation_code" class="form-control" required>
                                </div>
                                <button type="submit" class="btn btn-primary w-100">Confirm</button>
                            </form>
                            <div class="text-center mt-3">
                                <a href="/" class="btn btn-link">Back to Sign Up</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/confirm', methods=['POST'])
def confirm_post():
    """Handle confirmation"""
    username = request.form['username']
    confirmation_code = request.form['confirmation_code']
    
    if not all([username, confirmation_code]):
        flash('Both username and confirmation code are required', 'error')
        return redirect('/confirm')
    
    # Attempt confirmation
    auth = CognitoAuth()
    result = auth.confirm_sign_up(username, confirmation_code)
    
    if result['success']:
        flash('Email confirmed successfully! Registration complete.', 'success')
        session.pop('pending_username', None)
        return redirect('/success')
    else:
        flash(f"Confirmation failed: {result['message']}", 'error')
        return redirect('/confirm')

@app.route('/success')
def success():
    """Success page"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Registration Complete</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
            .card {{ border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
        </style>
    </head>
    <body>
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body p-5 text-center">
                            <h2 class="text-success mb-4">✅ Registration Complete!</h2>
                            <p class="lead">Your account has been successfully created and confirmed.</p>
                            <a href="/" class="btn btn-primary">Register Another User</a>
                            <a href="/admin" class="btn btn-outline-secondary">Admin Panel</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/admin')
def admin():
    """Admin panel for user management"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Panel</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
            .card {{ border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }}
        </style>
    </head>
    <body>
        <div class="container mt-5">
            <div class="row justify-content-center">
                <div class="col-md-8">
                    <div class="card">
                        <div class="card-body p-5">
                            <h2 class="text-center mb-4">🔧 Admin Panel</h2>
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-body">
                                            <h5 class="card-title">Get User Info</h5>
                                            <form method="POST" action="/admin/user-info">
                                                <div class="mb-3">
                                                    <label class="form-label">Username</label>
                                                    <input type="text" name="username" class="form-control" required>
                                                </div>
                                                <button type="submit" class="btn btn-info w-100">Get Info</button>
                                            </form>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="col-md-6">
                                    <div class="card">
                                        <div class="card-body">
                                            <h5 class="card-title">Update User Tier</h5>
                                            <form method="POST" action="/admin/update-tier">
                                                <div class="mb-3">
                                                    <label class="form-label">Username</label>
                                                    <input type="text" name="username" class="form-control" required>
                                                </div>
                                                <div class="mb-3">
                                                    <label class="form-label">New Tier</label>
                                                    <select name="new_tier" class="form-select" required>
                                                        <option value="standard">Standard</option>
                                                        <option value="premium">Premium</option>
                                                    </select>
                                                </div>
                                                <button type="submit" class="btn btn-warning w-100">Update Tier</button>
                                            </form>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="text-center mt-4">
                                <a href="/" class="btn btn-outline-secondary">Back to Registration</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/admin/user-info', methods=['POST'])
def admin_user_info():
    """Get user information"""
    username = request.form['username']
    
    if not username:
        flash('Username is required', 'error')
        return redirect('/admin')
    
    auth = CognitoAuth()
    result = auth.get_user_attributes(username)
    
    if result['success']:
        user_tier = result['user_tier']
        email = result['email']
        status = result['user_status']
        
        flash(f'User Info - Username: {username}, Email: {email}, Tier: {user_tier.upper()}, Status: {status}', 'success')
    else:
        flash(f"Failed to get user info: {result['message']}", 'error')
    
    return redirect('/admin')

@app.route('/admin/update-tier', methods=['POST'])
def admin_update_tier():
    """Update user tier"""
    username = request.form['username']
    new_tier = request.form['new_tier']
    
    if not all([username, new_tier]):
        flash('Both username and new tier are required', 'error')
        return redirect('/admin')
    
    if new_tier not in ['standard', 'premium']:
        flash('Invalid tier selected', 'error')
        return redirect('/admin')
    
    auth = CognitoAuth()
    result = auth.update_user_tier(username, new_tier)
    
    if result['success']:
        flash(f'User tier updated successfully! {username} is now {new_tier.upper()}', 'success')
    else:
        flash(f"Failed to update user tier: {result['message']}", 'error')
    
    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 