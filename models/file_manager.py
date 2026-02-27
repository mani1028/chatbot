from database import db
from datetime import datetime

class TemplateFile(db.Model):
    """Files associated with a Sector Template (e.g., PDFs, images)"""
    __tablename__ = 'template_files'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('sector_templates.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False) # Relative path on server
    file_type = db.Column(db.String(50), nullable=True)   # e.g., 'pdf', 'docx'
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship back to SectorTemplate
    template = db.relationship('SectorTemplate', backref=db.backref('files', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'template_id': self.template_id,
            'filename': self.filename,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'uploaded_at': self.uploaded_at.isoformat()
        }

class SiteFile(db.Model):
    """Files provisioned for a specific Client Site"""
    __tablename__ = 'site_files'

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship back to Site
    site = db.relationship('Site', backref=db.backref('files', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'site_id': self.site_id,
            'filename': self.filename,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'created_at': self.created_at.isoformat()
        }