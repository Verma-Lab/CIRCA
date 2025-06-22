import re
from pathlib import Path

# Read the main.py file
file_path = Path("/Users/hritvik/CIRCA/backend-python/main.py")
with open(file_path, 'r') as f:
    content = f.read()

# Define patterns to update
patterns_to_update = [
    # Update access control checks to use is_doctor_or_admin
    (r'(if\s+not\s+current_user\.is_doctor\s+and\s+not\s+user_has_patient_access\()', 
     'if not is_doctor_or_admin(current_user) and not user_has_patient_access('),
     
    # Update doctor-only checks
    (r'(if\s+not\s+current_user\.is_doctor:)', 
     'if not is_doctor_or_admin(current_user):'),
     
    # Update doctor role checks
    (r'(if\s+current_user\.is_doctor\s+or\s+current_user\.role\s*==\s*["\']administrator["\']:)',
     'if is_doctor_or_admin(current_user):'),
     
    # Update doctor role in conditions
    (r'(\|\|\s*current_user\.role\s*==\s*["\']administrator["\'])',
     '')  # Remove redundant checks since is_doctor_or_admin handles it
]

# Apply all replacements
updated_content = content
for pattern, replacement in patterns_to_update:
    updated_content = re.sub(pattern, replacement, updated_content)

# Write the updated content back to the file
with open(file_path, 'w') as f:
    f.write(updated_content)

print("Access control checks have been updated to include administrators.")
