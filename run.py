#!/usr/bin/env python3
"""
Run script for GovCon AI Assessment Platform
"""

import os
from app import app

if __name__ == '__main__':
    # Set default environment variables if not set
    if not os.getenv('SECRET_KEY'):
        os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'
    
    if not os.getenv('FLASK_ENV'):
        os.environ['FLASK_ENV'] = 'development'
    
    print("🧠 Starting GovCon AI Assessment Platform...")
    print("📊 Dashboard: http://localhost:5010")
    print("📁 Upload CSV: http://localhost:5010/upload_csv")
    print("⚠️  Make sure to set your OPENAI_API_KEY in environment variables")
    print("🔧 Press Ctrl+C to stop the server")
    print("-" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5010) 