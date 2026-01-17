import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import type { Resume, CoverLetter } from '../types';

export const Documents: React.FC = () => {
  const queryClient = useQueryClient();
  const [resumeUploadModalOpen, setResumeUploadModalOpen] = useState(false);
  const [coverLetterModalOpen, setCoverLetterModalOpen] = useState(false);
  const [coverLetterType, setCoverLetterType] = useState<'text' | 'file'>('text');
  const [coverLetterViewModalOpen, setCoverLetterViewModalOpen] = useState(false);
  const [viewingCoverLetter, setViewingCoverLetter] = useState<CoverLetter | null>(null);
  const [coverLetterViewText, setCoverLetterViewText] = useState<string>('');
  const [deleteConfirmModalOpen, setDeleteConfirmModalOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<{ type: 'resume' | 'cover_letter'; id: number; name: string } | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['documents'],
    queryFn: async () => {
      const result = await apiClient.getDocuments();
      return {
        resumes: result.resumes as Resume[],
        cover_letters: result.cover_letters as CoverLetter[],
      };
    },
  });

  const uploadResumeMutation = useMutation({
    mutationFn: async (formData: FormData) => apiClient.uploadResume(formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      setResumeUploadModalOpen(false);
      alert('Resume uploaded successfully!');
    },
    onError: (error: Error) => {
      alert(`Error uploading resume: ${error.message}`);
    },
  });

  const createCoverLetterMutation = useMutation({
    mutationFn: async (formData: FormData) => apiClient.createCoverLetter(formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      setCoverLetterModalOpen(false);
      setCoverLetterType('text');
      alert('Cover letter created successfully!');
    },
    onError: (error: Error) => {
      alert(`Error creating cover letter: ${error.message}`);
    },
  });

  const deleteResumeMutation = useMutation({
    mutationFn: async (resumeId: number) => {
      await apiClient.deleteResume(resumeId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      setDeleteConfirmModalOpen(false);
      setItemToDelete(null);
    },
    onError: (error: Error) => {
      alert(`Error deleting resume: ${error.message}`);
    },
  });

  const deleteCoverLetterMutation = useMutation({
    mutationFn: async (coverLetterId: number) => {
      await apiClient.deleteCoverLetter(coverLetterId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      setDeleteConfirmModalOpen(false);
      setItemToDelete(null);
    },
    onError: (error: Error) => {
      alert(`Error deleting cover letter: ${error.message}`);
    },
  });

  const handleResumeUpload = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    uploadResumeMutation.mutate(formData);
  };

  const handleCoverLetterCreate = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    createCoverLetterMutation.mutate(formData);
  };

  const handleDelete = () => {
    if (!itemToDelete) return;
    if (itemToDelete.type === 'resume') {
      deleteResumeMutation.mutate(itemToDelete.id);
    } else {
      deleteCoverLetterMutation.mutate(itemToDelete.id);
    }
  };

  const handleViewCoverLetter = async (coverLetter: CoverLetter) => {
    if (!coverLetter.file_path) {
      try {
        const response = await apiClient.getCoverLetter(coverLetter.cover_letter_id);
        setCoverLetterViewText(response.cover_letter_text || '');
        setViewingCoverLetter(coverLetter);
        setCoverLetterViewModalOpen(true);
      } catch (error) {
        alert('Error loading cover letter text');
      }
    }
  };

  const handleDownloadResume = (resumeId: number) => {
    apiClient
      .downloadResume(resumeId)
      .then((blob) => {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `resume-${resumeId}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      })
      .catch(() => {
        alert('Failed to download resume');
      });
  };

  const handleDownloadCoverLetter = (coverLetterId: number) => {
    apiClient
      .downloadCoverLetter(coverLetterId)
      .then((blob) => {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `cover-letter-${coverLetterId}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      })
      .catch(() => {
        alert('Failed to download cover letter');
      });
  };

  const getFileIcon = (fileType?: string, filePath?: string) => {
    if (fileType === 'application/pdf' || (filePath && filePath.includes('.pdf'))) {
      return 'fa-file-pdf';
    }
    if (fileType?.includes('wordprocessingml') || (filePath && filePath.includes('.docx'))) {
      return 'fa-file-word';
    }
    if (filePath) {
      return 'fa-file';
    }
    return 'fa-file-alt';
  };

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading documents</div>;

  const resumes = (data?.resumes || []) as Resume[];
  const coverLetters = (data?.cover_letters || []) as CoverLetter[];

  return (
    <div>
      <div className="page-header">
        <h1>Documents</h1>
        <p className="page-subtitle">Manage your resumes and cover letters</p>
      </div>

      <div className="documents-container">
        {/* Resumes Section */}
        <div className="section-card">
          <div className="section-header">
            <h2>
              <i className="fas fa-file-pdf"></i> Resumes
            </h2>
            <button className="btn btn-primary" onClick={() => setResumeUploadModalOpen(true)}>
              <i className="fas fa-plus"></i> Upload Resume
            </button>
          </div>

          {resumes.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <i className="fas fa-file-pdf"></i>
              </div>
              <h2 className="empty-state-title">No Resumes Yet</h2>
              <p className="empty-state-message">
                Upload your resume to attach it to job applications. You can upload multiple versions for different types
                of positions.
              </p>
              <button className="btn btn-primary" onClick={() => setResumeUploadModalOpen(true)}>
                <i className="fas fa-plus"></i> Upload Your First Resume
              </button>
            </div>
          ) : (
            <div className="documents-list">
              {resumes.map((resume: Resume) => (
                <div key={resume.resume_id} className="document-item">
                  <div className="document-info">
                    <div className="document-icon">
                      <i className={`fas ${getFileIcon(resume.file_type)}`}></i>
                    </div>
                    <div className="document-details">
                      <span className="document-name">{resume.resume_name}</span>
                      <span className="document-meta">
                        {resume.file_size ? `${(resume.file_size / 1024).toFixed(1)} KB` : ''}
                        {resume.file_size && resume.created_at ? ' • ' : ''}
                        {resume.created_at
                          ? new Date(resume.created_at).toLocaleDateString('en-US', {
                              year: 'numeric',
                              month: '2-digit',
                              day: '2-digit',
                            })
                          : 'Unknown date'}
                      </span>
                    </div>
                  </div>
                  <div className="document-actions">
                    <button
                      className="btn btn-sm btn-secondary"
                      onClick={() => handleDownloadResume(resume.resume_id)}
                      title="Download"
                    >
                      <i className="fas fa-download"></i>
                    </button>
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => {
                        setItemToDelete({ type: 'resume', id: resume.resume_id, name: resume.resume_name });
                        setDeleteConfirmModalOpen(true);
                      }}
                      title="Delete"
                    >
                      <i className="fas fa-trash"></i>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Cover Letters Section */}
        <div className="section-card">
          <div className="section-header">
            <h2>
              <i className="fas fa-file-alt"></i> Cover Letters
            </h2>
            <button className="btn btn-primary" onClick={() => setCoverLetterModalOpen(true)}>
              <i className="fas fa-plus"></i> Create Cover Letter
            </button>
          </div>

          {coverLetters.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">
                <i className="fas fa-file-alt"></i>
              </div>
              <h2 className="empty-state-title">No Cover Letters Yet</h2>
              <p className="empty-state-message">
                Create cover letters to personalize your job applications. You can write them manually or generate them
                using AI for specific job postings.
              </p>
              <button className="btn btn-primary" onClick={() => setCoverLetterModalOpen(true)}>
                <i className="fas fa-plus"></i> Create Your First Cover Letter
              </button>
            </div>
          ) : (
            <div className="documents-list">
              {coverLetters.map((coverLetter: CoverLetter) => (
                <div key={coverLetter.cover_letter_id} className="document-item">
                  <div className="document-info">
                    <div className="document-icon">
                      <i className={`fas ${getFileIcon(undefined, coverLetter.file_path)}`}></i>
                    </div>
                    <div className="document-details">
                      <span className="document-name">{coverLetter.cover_letter_name}</span>
                      <span className="document-meta">
                        {coverLetter.file_path ? 'File' : 'Text'}
                        {' • '}
                        {coverLetter.created_at
                          ? new Date(coverLetter.created_at).toLocaleDateString('en-US', {
                              year: 'numeric',
                              month: '2-digit',
                              day: '2-digit',
                            })
                          : 'Unknown date'}
                      </span>
                    </div>
                  </div>
                  <div className="document-actions">
                    {coverLetter.file_path ? (
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={() => handleDownloadCoverLetter(coverLetter.cover_letter_id)}
                        title="Download"
                      >
                        <i className="fas fa-download"></i>
                      </button>
                    ) : (
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={() => handleViewCoverLetter(coverLetter)}
                        title="View"
                      >
                        <i className="fas fa-eye"></i>
                      </button>
                    )}
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => {
                        setItemToDelete({
                          type: 'cover_letter',
                          id: coverLetter.cover_letter_id,
                          name: coverLetter.cover_letter_name,
                        });
                        setDeleteConfirmModalOpen(true);
                      }}
                      title="Delete"
                    >
                      <i className="fas fa-trash"></i>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Resume Upload Modal */}
      {resumeUploadModalOpen && (
        <div className="modal-overlay active" onClick={() => setResumeUploadModalOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Add Resume</h3>
              <button className="modal-close" onClick={() => setResumeUploadModalOpen(false)} aria-label="Close">
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-content">
              <form onSubmit={handleResumeUpload} id="resumeUploadForm">
                <div className="form-group">
                  <label htmlFor="resume_name">Resume Name:</label>
                  <input
                    type="text"
                    name="resume_name"
                    id="resume_name"
                    className="form-control"
                    placeholder="e.g., Data Engineer Resume v2"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="resume_file">Select File (PDF or DOCX, max 5MB):</label>
                  <input type="file" name="file" id="resume_file" accept=".pdf,.docx" required />
                </div>
                <div className="form-actions">
                  <button type="submit" className="btn btn-primary" disabled={uploadResumeMutation.isPending}>
                    {uploadResumeMutation.isPending ? 'Uploading...' : 'Upload'}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setResumeUploadModalOpen(false)}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Cover Letter Modal */}
      {coverLetterModalOpen && (
        <div className="modal-overlay active" onClick={() => setCoverLetterModalOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Add Cover Letter</h3>
              <button className="modal-close" onClick={() => setCoverLetterModalOpen(false)} aria-label="Close">
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-content">
              <form onSubmit={handleCoverLetterCreate} id="coverLetterForm">
                <div className="form-group">
                  <label htmlFor="cover_letter_name">Cover Letter Name:</label>
                  <input
                    type="text"
                    name="cover_letter_name"
                    id="cover_letter_name"
                    className="form-control"
                    placeholder="e.g., Generic Cover Letter"
                    required
                  />
                </div>
                <div className="form-group">
                  <label>Create as:</label>
                  <div className="radio-group">
                    <label>
                      <input
                        type="radio"
                        name="cover_letter_type"
                        value="text"
                        checked={coverLetterType === 'text'}
                        onChange={() => setCoverLetterType('text')}
                      />{' '}
                      Text
                    </label>
                    <label>
                      <input
                        type="radio"
                        name="cover_letter_type"
                        value="file"
                        checked={coverLetterType === 'file'}
                        onChange={() => setCoverLetterType('file')}
                      />{' '}
                      File Upload
                    </label>
                  </div>
                </div>
                {coverLetterType === 'text' ? (
                  <div className="form-group" id="coverLetterTextGroup">
                    <label htmlFor="cover_letter_text">Cover Letter Text:</label>
                    <textarea
                      name="cover_letter_text"
                      id="cover_letter_text"
                      className="form-control"
                      rows={10}
                      placeholder="Dear Hiring Manager,&#10;&#10;I am writing to express my interest..."
                    ></textarea>
                  </div>
                ) : (
                  <div className="form-group" id="coverLetterFileGroup">
                    <label htmlFor="cover_letter_file">Select File (PDF or DOCX, max 5MB):</label>
                    <input type="file" name="file" id="cover_letter_file" accept=".pdf,.docx" />
                  </div>
                )}
                <div className="form-actions">
                  <button type="submit" className="btn btn-primary" disabled={createCoverLetterMutation.isPending}>
                    {createCoverLetterMutation.isPending ? 'Creating...' : 'Create'}
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setCoverLetterModalOpen(false)}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmModalOpen && itemToDelete && (
        <div className="modal-overlay active" onClick={() => setDeleteConfirmModalOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Confirm Delete</h3>
              <button className="modal-close" onClick={() => setDeleteConfirmModalOpen(false)} aria-label="Close">
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-content">
              <p id="deleteConfirmMessage">
                Are you sure you want to delete &quot;{itemToDelete.name}&quot;? This action cannot be undone.
              </p>
              <div className="form-actions">
                <button type="button" className="btn btn-danger" onClick={handleDelete}>
                  Delete
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setDeleteConfirmModalOpen(false)}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Cover Letter Text View Modal */}
      {coverLetterViewModalOpen && viewingCoverLetter && (
        <div className="modal-overlay active" onClick={() => setCoverLetterViewModalOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 id="coverLetterTextViewTitle">{viewingCoverLetter.cover_letter_name}</h3>
              <button className="modal-close" onClick={() => setCoverLetterViewModalOpen(false)} aria-label="Close">
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-content">
              <div className="cover-letter-text-view" id="coverLetterTextViewContent">
                {coverLetterViewText ? <p>{coverLetterViewText}</p> : <p>No cover letter text available.</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
