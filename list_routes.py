#!/usr/bin/env python3
"""
List all registered routes in the Flask app
"""

import os
os.environ['DISABLE_EMBEDDINGS'] = 'true'

from app import create_app

app = create_app()

print("Registered Routes:")
print("=" * 70)

routes = []
for rule in app.url_map.iter_rules():
    routes.append({
        'path': str(rule),
        'methods': ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'})),
        'endpoint': rule.endpoint
    })

# Sort by path
routes.sort(key=lambda x: x['path'])

# Show routes containing 'chat' or 'api'
print("\nChat/API routes:")
for route in routes:
    if 'chat' in route['path'].lower() or 'api' in route['path'].lower():
        print(f"  {route['path']:<40} [{route['methods']}]")

print("\nAll routes (first 20):")
for route in routes[:20]:
    print(f"  {route['path']:<40} [{route['methods']}]")

print(f"\nTotal routes: {len(routes)}")
