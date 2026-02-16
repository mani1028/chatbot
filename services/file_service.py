import os
import shutil
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt', 'png', 'jpg', 'jpeg', 'csv', 'json'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_template_file(file, template_id):
    """
    Saves a file uploaded for a specific template.
    Returns: (relative_path, filename, file_type)
    """
    if file.filename == '':
        return None, None, None
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        # Create directory if not exists: static/uploads/templates/{id}/
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'templates', str(template_id))
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        # Return relative path for DB storage
        relative_path = f"static/uploads/templates/{template_id}/{filename}"
        return relative_path, filename, file_ext
        
    return None, None, None

def provision_files_for_site(site_id, template_files):
    """
    Copies files from template storage to site storage.
    Returns list of new SiteFile dictionaries to be added to DB.
    """
    new_site_files = []
    
    # Target directory: static/uploads/sites/{site_id}/
    site_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'sites', str(site_id))
    os.makedirs(site_folder, exist_ok=True)
    
    for t_file in template_files:
        # Source path
        src_path = os.path.join(current_app.root_path, t_file.file_path)
        
        if os.path.exists(src_path):
            # Destination path
            dest_filename = secure_filename(t_file.filename)
            dest_path = os.path.join(site_folder, dest_filename)
            
            # Copy file
            shutil.copy2(src_path, dest_path)
            
            # Record relative path
            relative_dest_path = f"static/uploads/sites/{site_id}/{dest_filename}"
            
            new_site_files.append({
                'filename': t_file.filename,
                'file_path': relative_dest_path,
                'file_type': t_file.file_type
            })
            
    return new_site_files

def delete_file_from_disk(relative_path):
    """Deletes a file from the filesystem"""
    try:
        full_path = os.path.join(current_app.root_path, relative_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
    except Exception as e:
        print(f"Error deleting file {relative_path}: {e}")
    return False