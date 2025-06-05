#!/usr/bin/env python3
"""
Simple Flask app for Cognito user registration
"""

from flask import Flask, request, redirect, flash, session
import os
import sys

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.cognito import register_user, confirm_user

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
    
    # Attempt registration
    result = register_user(username, email, password)
    
    if result['success']:
        flash('Registration successful! Please check your email for a confirmation code.', 'success')
        session['pending_username'] = username
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
    result = confirm_user(username, confirmation_code)
    
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
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 