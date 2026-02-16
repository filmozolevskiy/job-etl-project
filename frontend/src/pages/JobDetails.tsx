import { useMemo, useState, useEffect } from 'react';
import type { FC, FormEvent } from 'react';
import type { AxiosError } from 'axios';
import { useParams, Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';

interface ApplicationDoc {
  document_id?: number;
  resume_id?: number | null;
  resume_name?: string | null;
  resume_file_type?: string | null;
  cover_letter_id?: number | null;
  cover_letter_name?: string | null;
  cover_letter_file_path?: string | null;
  cover_letter_text?: string | null;
  user_notes?: string | null;
  is_generated?: boolean;
}

interface ResumeItem {
  resume_id: number;
  resume_name?: string | null;
  file_type?: string | null;
  file_size?: number | null;
  created_at?: string | null;
}

interface CoverLetterItem {
  cover_letter_id: number;
  cover_letter_name?: string | null;
  file_path?: string | null;
  cover_letter_text?: string | null;
  created_at?: string | null;
  is_generated?: boolean;
}

interface NoteItem {
  note_id: number;
  note_text: string;
  created_at?: string | null;
  updated_at?: string | null;
}

interface StatusHistoryEntry {
  status?: string | null;
  change_type?: string | null;
  changed_by?: string | null;
  created_at?: string | null;
  metadata?: Record<string, unknown> | null;
  notes?: string | null;
}

const MAX_NOTES_DISPLAYED = 3;
const MAX_NOTE_TEXT_LENGTH = 300;

const formatDate = (value?: string | null) => {
  if (!value) return 'Unknown';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString('en-US');
};

const formatDateTime = (value?: string | null) => {
  if (!value) return 'Recently';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('en-US');
};

const titleCase = (value?: string | null) => {
  if (!value) return 'Not specified';
  return value
    .split(/[\s_-]+/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
};

const getCompanyNameFromApplyOptions = (applyOptions?: unknown): string | null => {
  if (!applyOptions) return null;
  let parsed = applyOptions;
  if (typeof applyOptions === 'string') {
    try {
      parsed = JSON.parse(applyOptions);
    } catch {
      return null;
    }
  }
  if (Array.isArray(parsed)) {
    for (const option of parsed) {
      if (option && typeof option === 'object') {
        const obj = option as Record<string, unknown>;
        const candidate =
          (obj.company_name as string) ||
          (obj.employer_name as string) ||
          (obj.company as string);
        if (candidate) return candidate;
      }
    }
  }
  if (parsed && typeof parsed === 'object') {
    const obj = parsed as Record<string, unknown>;
    return (
      (obj.company_name as string) ||
      (obj.employer_name as string) ||
      (obj.company as string) ||
      null
    );
  }
  return null;
};

/** Build deduplicated list of job posting links from JSearch: job_apply_link and apply_options only (no generic Google Jobs URL). */
const getJobPostingLinks = (job: Record<string, unknown> | null | undefined): Array<{ url: string; label: string }> => {
  if (!job) return [];
  const seen = new Set<string>();
  const links: Array<{ url: string; label: string }> = [];
  const add = (url: string | null | undefined, label: string) => {
    if (typeof url !== 'string' || !url.trim()) return;
    const normalized = url.trim();
    if (seen.has(normalized)) return;
    seen.add(normalized);
    links.push({ url: normalized, label });
  };
  // Support both snake_case (API) and camelCase (if response is ever transformed)
  const mainLink =
    (job.job_apply_link as string | undefined) ?? (job.jobApplyLink as string | undefined);
  add(mainLink, 'View Original');
  let applyOptions = job.apply_options ?? job.applyOptions;
  if (typeof applyOptions === 'string') {
    try {
      applyOptions = JSON.parse(applyOptions) as unknown;
    } catch {
      applyOptions = undefined;
    }
  }
  let opts: unknown[] = [];
  if (Array.isArray(applyOptions)) opts = applyOptions;
  else if (applyOptions && typeof applyOptions === 'object' && !Array.isArray(applyOptions)) opts = [applyOptions];
  for (const opt of opts) {
    if (opt && typeof opt === 'object') {
      const o = opt as Record<string, unknown>;
      const applyLink = (o.apply_link as string | undefined) ?? (o.applyLink as string | undefined);
      const publisher = (o.publisher as string) || 'Apply';
      if (applyLink) add(applyLink, publisher ? `Apply via ${publisher}` : 'Apply');
    }
  }
  return links;
};

const formatStatusHistoryLabel = (entry: StatusHistoryEntry) => {
  if (entry.status === 'job_found' || entry.status === 'found' || entry.change_type === 'extraction') {
    return 'Job found';
  }
  if (entry.status === 'updated_by_system' || entry.changed_by === 'system') {
    return 'Job posting enriched and ranked';
  }
  if (entry.status === 'updated_by_ai' || entry.changed_by === 'ai_enricher' || entry.changed_by === 'chatgpt_enricher') {
    return 'Job posting enriched and reranked';
  }
  if (entry.status === 'documents_uploaded' || entry.status === 'documents_linked' || entry.change_type === 'document_change') {
    return 'Documents changed';
  }
  if (entry.status === 'documents_unlinked') {
    return 'Documents removed';
  }
  if (entry.status === 'note_added') return 'Note Added';
  if (entry.status === 'note_updated') return 'Note Updated';
  if (entry.status === 'note_deleted') return 'Note Deleted';
  if (entry.status === 'status_changed' || entry.change_type === 'status_change' || entry.change_type === 'user_update') {
    if (entry.metadata && typeof entry.metadata.new_status === 'string') {
      return `Status Changed to ${titleCase(entry.metadata.new_status)}`;
    }
    return 'Status Changed';
  }
  if (entry.status) return titleCase(entry.status);
  if (entry.change_type) return titleCase(entry.change_type);
  return 'Update';
};

const isDocumentHistoryEntry = (entry: StatusHistoryEntry) => {
  const status = entry.status || '';
  const changeType = entry.change_type || '';
  return (
    status === 'documents_uploaded' ||
    status === 'documents_linked' ||
    status === 'documents_unlinked' ||
    changeType === 'document_change'
  );
};

const formatChangedByLabel = (changedBy?: string | null, status?: string | null, changeType?: string | null) => {
  if (!changedBy) return null;
  if (changedBy === 'system') return 'System';
  if (changedBy === 'ai_enricher' || changedBy === 'chatgpt_enricher') return 'Ai Agent';
  if (changedBy === 'user' && (status === 'status_changed' || changeType === 'status_change')) return 'User';
  return changedBy.replace(/_/g, ' ').replace(/\b\w/g, (match) => match.toUpperCase());
};

const formatEnrichmentDetails = (metadata: Record<string, unknown>) => {
  const enrichmentType = metadata.enrichment_type;
  if (!enrichmentType || typeof enrichmentType !== 'string') {
    return null;
  }

  const extracted: string[] = [];
  if (enrichmentType === 'system') {
    if (metadata.skills_extracted) extracted.push(`skills${typeof metadata.skills_extracted === 'number' ? ` (${metadata.skills_extracted})` : ''}`);
    if (metadata.seniority_level) extracted.push('seniority level');
    if (metadata.remote_work_type) extracted.push('remote type');
    if (metadata.salary_extracted) extracted.push('salary');
    return extracted.length > 0 ? `Extracted: ${extracted.join(', ')}` : 'Extracted: skills, seniority level, remote type, salary';
  }

  if (enrichmentType === 'ai_enricher' || enrichmentType === 'chatgpt_enricher') {
    if (metadata.summary_extracted) extracted.push('job summary');
    if (metadata.skills_extracted) extracted.push(`skills${typeof metadata.skills_extracted === 'number' ? ` (${metadata.skills_extracted})` : ''}`);
    if (metadata.location_extracted) extracted.push('location');
    if (metadata.seniority_level) extracted.push('seniority level');
    if (metadata.remote_work_type) extracted.push('remote type');
    if (metadata.salary_extracted) extracted.push('salary');
    return extracted.length > 0
      ? `Extracted: ${extracted.join(', ')}`
      : 'Extracted: job summary, skills, location, seniority level, remote type, salary';
  }

  return 'Enrichment fields updated';
};

const formatStatusHistoryDetails = (entry: StatusHistoryEntry) => {
  const metadata = entry.metadata || {};
  if (metadata && typeof metadata === 'object') {
    const meta = metadata as Record<string, unknown>;
    if (meta.old_status && meta.new_status) {
      return `Changed from ${titleCase(String(meta.old_status))} to ${titleCase(String(meta.new_status))}`;
    }
    if (meta.new_status) {
      return `Set to ${titleCase(String(meta.new_status))}`;
    }
    if (meta.action === 'uploaded') {
      if (meta.resume_id && meta.cover_letter_id) return 'Resume and cover letter uploaded';
      if (meta.resume_id) return 'Resume uploaded';
      if (meta.cover_letter_id || meta.has_cover_letter_text) return 'Cover letter uploaded';
      return 'Documents uploaded';
    }
    if (meta.action === 'changed') {
      const changedDocs: string[] = [];
      if (meta.resume_id) changedDocs.push('Resume');
      if (meta.cover_letter_id || meta.has_cover_letter_text) changedDocs.push('Cover letter');
      return changedDocs.length > 0 ? `${changedDocs.join(' and ')} updated` : 'Documents updated';
    }
    if (meta.resume_id || meta.cover_letter_id) {
      const linkedDocs: string[] = [];
      if (meta.resume_id) linkedDocs.push('Resume linked');
      if (meta.cover_letter_id) linkedDocs.push('Cover letter linked');
      if (linkedDocs.length > 0) return linkedDocs.join(', ');
    }
    const enrichmentDetails = formatEnrichmentDetails(meta);
    if (enrichmentDetails) return enrichmentDetails;
  }
  return entry.notes || null;
};

const getApiErrorMessage = (error: unknown, fallback: string) => {
  const axiosError = error as AxiosError<{ error?: string; msg?: string }>;
  const responseData = axiosError?.response?.data;
  if (responseData?.error) return responseData.error;
  if (responseData?.msg) return responseData.msg;
  if (axiosError?.message) return axiosError.message;
  if (error instanceof Error) return error.message;
  return fallback;
};

const RANKING_FACTOR_LABELS: Record<string, string> = {
  location_match: 'Location Match',
  salary_match: 'Salary Match',
  company_size_match: 'Company Size Match',
  skills_match: 'Skills Match',
  keyword_match: 'Title/Keyword Match',
  employment_type_match: 'Employment Type Match',
  seniority_match: 'Seniority Level Match',
  remote_type_match: 'Remote Work Match',
  recency: 'Posting Recency',
};

const RANKING_MAX_WEIGHTS: Record<string, number> = {
  location_match: 15.0,
  salary_match: 15.0,
  company_size_match: 10.0,
  skills_match: 15.0,
  keyword_match: 15.0,
  employment_type_match: 5.0,
  seniority_match: 10.0,
  remote_type_match: 10.0,
  recency: 5.0,
};

const formatRankingLabel = (value: string) =>
  RANKING_FACTOR_LABELS[value] ||
  value.replace(/_/g, ' ').replace(/\b\w/g, (match) => match.toUpperCase());

const formatRankingValue = (value: number) => value.toFixed(1);

export const JobDetails: FC = () => {
  const { id } = useParams<{ id: string }>();
  const jobId = id || '';
  const queryClient = useQueryClient();

  const [status, setStatus] = useState('');
  const [rankingModalOpen, setRankingModalOpen] = useState(false);
  const [resumeModalOpen, setResumeModalOpen] = useState(false);
  const [coverLetterModalOpen, setCoverLetterModalOpen] = useState(false);
  const [resumeTab, setResumeTab] = useState<'upload' | 'select'>('upload');
  const [coverLetterTab, setCoverLetterTab] = useState<'create' | 'select' | 'generate'>('create');
  const [coverLetterType, setCoverLetterType] = useState<'text' | 'file'>('text');
  const [coverLetterName, setCoverLetterName] = useState('');
  const [coverLetterFile, setCoverLetterFile] = useState<File | null>(null);
  const [selectedResumeId, setSelectedResumeId] = useState<number | ''>('');
  const [resumeName, setResumeName] = useState('');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [selectedCoverLetterId, setSelectedCoverLetterId] = useState<number | ''>('');
  const [coverLetterText, setCoverLetterText] = useState('');
  const [generateResumeId, setGenerateResumeId] = useState<number | ''>('');
  const [generateComments, setGenerateComments] = useState('');
  const [generatedCoverLetterText, setGeneratedCoverLetterText] = useState('');
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationHistoryOpen, setGenerationHistoryOpen] = useState(false);
  const [newNoteText, setNewNoteText] = useState('');
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editingNoteText, setEditingNoteText] = useState('');
  const [allNotesModalOpen, setAllNotesModalOpen] = useState(false);
  const [allHistoryModalOpen, setAllHistoryModalOpen] = useState(false);
  const [expandedNoteIds, setExpandedNoteIds] = useState<Set<number>>(new Set());

  const { data: jobData, isLoading, error } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => apiClient.getJob(jobId),
    enabled: !!jobId,
    staleTime: 0, // Always refetch so apply links are fresh (avoids stale cache)
  });

  const job = (jobData as { job: unknown })?.job as Record<string, unknown>;

  // Diagnostic: log what API sent for apply links (helps debug "Not available" on some jobs)
  useEffect(() => {
    if (!job || !jobId) return;
    const hasLink = !!(job.job_apply_link ?? (job as Record<string, unknown>).jobApplyLink);
    const opts = job.apply_options ?? (job as Record<string, unknown>).applyOptions;
    const optsLen = Array.isArray(opts) ? opts.length : opts ? '?object' : 0;
    if (!hasLink || (optsLen === 0 && !hasLink)) {
      console.log('[JobDetails] Apply links debug:', {
        jobId: jobId.slice(0, 24),
        job_apply_link: hasLink ? 'present' : 'missing',
        apply_options: optsLen,
        keys: job ? Object.keys(job).filter((k) => k.includes('apply') || k.includes('link')).slice(0, 10) : [],
      });
    }
  }, [job, jobId]);

  const { data: docsData } = useQuery({
    queryKey: ['jobApplicationDocuments', jobId],
    queryFn: () => apiClient.getJobApplicationDocuments(jobId),
    enabled: !!jobId,
  });

  const { data: notesData } = useQuery({
    queryKey: ['jobNotes', jobId],
    queryFn: () => apiClient.getJobNotes(jobId),
    enabled: !!jobId,
  });

  const { data: historyData } = useQuery({
    queryKey: ['jobHistory', jobId],
    queryFn: () => apiClient.getJobStatusHistory(jobId),
    enabled: !!jobId,
  });

  const { data: generationHistory } = useQuery({
    queryKey: ['jobCoverLetterHistory', jobId],
    queryFn: () => apiClient.getCoverLetterGenerationHistory(jobId),
    enabled: !!jobId && generationHistoryOpen,
  });

  const updateStatusMutation = useMutation({
    mutationFn: (newStatus: string) => apiClient.updateJobStatus(jobId, newStatus),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', jobId] });
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['jobHistory', jobId] });
    },
  });

  const updateDocumentsMutation = useMutation({
    mutationFn: (payload: {
      resume_id?: number | null;
      cover_letter_id?: number | null;
      cover_letter_text?: string | null;
      user_notes?: string | null;
    }) => apiClient.updateJobApplicationDocuments(jobId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobApplicationDocuments', jobId] });
      queryClient.invalidateQueries({ queryKey: ['jobHistory', jobId] });
    },
  });

  const uploadResumeMutation = useMutation({
    mutationFn: (formData: FormData) => apiClient.uploadJobResume(jobId, formData),
    onSuccess: (response) => {
      updateDocumentsMutation.mutate({
        resume_id: response.resume_id,
      });
      setResumeModalOpen(false);
      setResumeFile(null);
      setResumeName('');
      setSelectedResumeId('');
    },
  });

  const addNoteMutation = useMutation({
    mutationFn: (noteText: string) => apiClient.addJobNote(jobId, noteText),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobNotes', jobId] });
      queryClient.invalidateQueries({ queryKey: ['jobHistory', jobId] });
      setNewNoteText('');
    },
  });

  const updateNoteMutation = useMutation({
    mutationFn: ({ noteId, noteText }: { noteId: number; noteText: string }) =>
      apiClient.updateJobNote(jobId, noteId, noteText),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobNotes', jobId] });
      setEditingNoteId(null);
      setEditingNoteText('');
    },
  });

  const deleteNoteMutation = useMutation({
    mutationFn: (noteId: number) => apiClient.deleteJobNote(jobId, noteId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobNotes', jobId] });
    },
  });

  const generateCoverLetterMutation = useMutation({
    mutationFn: (payload: { resume_id: number; user_comments?: string }) =>
      apiClient.generateCoverLetter(jobId, payload),
    onMutate: () => {
      setIsGenerating(true);
      setGenerateError(null);
      setGeneratedCoverLetterText('');
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['jobApplicationDocuments', jobId] });
      queryClient.invalidateQueries({ queryKey: ['jobCoverLetterHistory', jobId] });
      setGeneratedCoverLetterText(response.cover_letter_text || '');
    },
    onError: (error) => {
      setGenerateError(getApiErrorMessage(error, 'Failed to generate cover letter'));
    },
    onSettled: () => {
      setIsGenerating(false);
    },
  });

  const currentStatus = (job?.job_status as string) || '';
  const applicationDoc = (docsData as { application_doc: unknown })?.application_doc as ApplicationDoc | null;
  const userResumes = ((docsData as { user_resumes: unknown[] })?.user_resumes || []) as ResumeItem[];
  const userCoverLetters = ((docsData as { user_cover_letters: unknown[] })?.user_cover_letters || []) as CoverLetterItem[];
  const notes = ((notesData as { notes: unknown[] })?.notes || []) as NoteItem[];
  const statusHistory = ((historyData as { history: unknown[] })?.history || []) as StatusHistoryEntry[];
  const coverLetterHistory = ((generationHistory as { history: unknown[] })?.history || []) as CoverLetterItem[];

  const sortedNotes = useMemo(() => {
    return [...notes].sort((a, b) => {
      const aTime = a.created_at ? new Date(a.created_at).getTime() : 0;
      const bTime = b.created_at ? new Date(b.created_at).getTime() : 0;
      return aTime - bTime;
    });
  }, [notes]);

  const sortedHistory = useMemo(() => {
    return statusHistory
      .filter((entry) => !isDocumentHistoryEntry(entry))
      .sort((a, b) => {
      const aTime = a.created_at ? new Date(a.created_at).getTime() : 0;
      const bTime = b.created_at ? new Date(b.created_at).getTime() : 0;
      return aTime - bTime;
    });
  }, [statusHistory]);

  const displayedNotes = sortedNotes.slice(-MAX_NOTES_DISPLAYED);
  const displayedHistory = sortedHistory.slice(-3);

  const parsedSkills = useMemo(() => {
    const raw = job?.extracted_skills;
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    if (typeof raw === 'string') {
      try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
      } catch {
        return raw.split(',').map((skill) => skill.trim()).filter(Boolean);
      }
    }
    return [];
  }, [job]);

  const score = Math.round((job?.rank_score as number) || 0);
  const jobSummary = (job?.job_summary as string) || (job?.job_description as string) || '';
  const campaignCount = Number(job?.campaign_count ?? 0);
  const campaignNames = (job?.campaign_names as string[] | null) ?? [];
  const sharedCampaignNote =
    campaignCount > 1
      ? `Note: This job appears in ${campaignCount} of your campaigns${
          campaignNames.length ? ` (${campaignNames.join(', ')})` : ''
        }. Statuses and notes are shared to avoid applying multiple times to the same position.`
      : null;

  const displayCompanyName = useMemo(() => {
    const existingName = (job?.company_name as string) || '';
    if (existingName && existingName.toLowerCase() !== 'unknown') return existingName;
    return getCompanyNameFromApplyOptions(job?.apply_options) || 'Company not specified';
  }, [job]);

  const updateApplicationDocuments = (overrides: {
    resume_id?: number | null;
    cover_letter_id?: number | null;
    cover_letter_text?: string | null;
  }) => {
    updateDocumentsMutation.mutate({
      resume_id: overrides.resume_id ?? applicationDoc?.resume_id ?? null,
      cover_letter_id: overrides.cover_letter_id ?? applicationDoc?.cover_letter_id ?? null,
      cover_letter_text: overrides.cover_letter_text ?? applicationDoc?.cover_letter_text ?? null,
    });
  };

  const handleStatusChange = (newStatus: string) => {
    setStatus(newStatus);
    updateStatusMutation.mutate(newStatus);
  };

  const handleResumeLink = () => {
    if (!selectedResumeId) return;
    updateApplicationDocuments({
      resume_id: Number(selectedResumeId),
    });
    setResumeModalOpen(false);
  };

  const handleResumeUpload = () => {
    if (!resumeFile) return;
    const formData = new FormData();
    formData.append('file', resumeFile);
    if (resumeName) {
      formData.append('resume_name', resumeName);
    }
    uploadResumeMutation.mutate(formData);
  };

  const handleResumeUploadSubmit = (event: FormEvent) => {
    event.preventDefault();
    handleResumeUpload();
  };

  const handleCoverLetterSelect = () => {
    if (!selectedCoverLetterId) return;
    updateApplicationDocuments({
      cover_letter_id: Number(selectedCoverLetterId),
      cover_letter_text: null,
    });
    setCoverLetterModalOpen(false);
  };

  const handleCoverLetterHistoryLink = (coverLetterId: number) => {
    updateApplicationDocuments({
      cover_letter_id: coverLetterId,
      cover_letter_text: null,
    });
    setGenerationHistoryOpen(false);
    setCoverLetterModalOpen(false);
  };

  const handleCreateCoverLetter = () => {
    const formData = new FormData();
    formData.append('cover_letter_name', coverLetterName || `Cover Letter - ${displayCompanyName}`);

    if (coverLetterType === 'file') {
      if (!coverLetterFile) return;
      formData.append('file', coverLetterFile);
    } else {
      if (!coverLetterText.trim()) return;
      formData.append('cover_letter_text', coverLetterText.trim());
    }

    apiClient
      .createJobCoverLetter(jobId, formData)
      .then((response) => {
        updateApplicationDocuments({
          cover_letter_id: response.cover_letter_id,
          cover_letter_text: response.cover_letter_text || null,
        });
        setCoverLetterModalOpen(false);
        setCoverLetterText('');
        setCoverLetterName('');
        setCoverLetterFile(null);
      })
      .catch(() => {
        alert('Failed to create cover letter.');
      });
  };

  const handleCoverLetterGenerate = () => {
    if (!generateResumeId) return;
    generateCoverLetterMutation.mutate({
      resume_id: Number(generateResumeId),
      user_comments: generateComments || undefined,
    });
  };

  const handleSaveGeneratedCoverLetter = () => {
    if (!generatedCoverLetterText.trim()) return;
    const formData = new FormData();
    formData.append(
      'cover_letter_name',
      coverLetterName || `Generated Cover Letter - ${new Date().toLocaleDateString()}`
    );
    formData.append('cover_letter_text', generatedCoverLetterText.trim());

    apiClient
      .createJobCoverLetter(jobId, formData)
      .then((response) => {
        updateApplicationDocuments({ cover_letter_id: response.cover_letter_id });
        setCoverLetterModalOpen(false);
    setGeneratedCoverLetterText('');
      })
      .catch(() => {
        alert('Failed to save generated cover letter.');
      });
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
        alert('Failed to download resume.');
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
        alert('Failed to download cover letter.');
      });
  };

  const handleDownloadInlineCoverLetter = (text: string) => {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'cover-letter.txt';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };

  const toggleNoteExpansion = (noteId: number) => {
    setExpandedNoteIds((prev) => {
      const next = new Set(prev);
      if (next.has(noteId)) {
        next.delete(noteId);
      } else {
        next.add(noteId);
      }
      return next;
    });
  };

  const renderNoteText = (note: NoteItem, allowToggle = true) => {
    const fullText = note.note_text || '';
    const isLong = fullText.length > MAX_NOTE_TEXT_LENGTH;
    const isExpanded = expandedNoteIds.has(note.note_id);
    const displayText = isLong && !isExpanded ? `${fullText.slice(0, MAX_NOTE_TEXT_LENGTH)}...` : fullText;

    return (
      <>
        <div className="notes-text">{displayText}</div>
        {allowToggle && isLong && (
          <button
            type="button"
            className="btn-link"
            onClick={() => toggleNoteExpansion(note.note_id)}
            style={{ color: 'var(--color-primary)', textDecoration: 'underline', fontSize: '0.875rem' }}
          >
            {isExpanded ? 'Show less' : 'Show more'}
          </button>
        )}
      </>
    );
  };

  const openRankingModal = () => setRankingModalOpen(true);
  const closeRankingModal = () => setRankingModalOpen(false);

  const renderRankingBreakdown = () => {
    const breakdown = job?.rank_explain as Record<string, unknown> | undefined;
    if (!breakdown || Object.keys(breakdown).length === 0) {
      return <p>No ranking breakdown available.</p>;
    }

    const entries = Object.entries(breakdown)
      .filter(([key, value]) => key !== 'total_score' && typeof value === 'number')
      .sort(([, valueA], [, valueB]) => Number(valueB) - Number(valueA));

    return (
      <div>
        {entries.map(([key, value]) => {
          const numericValue = Number(value);
          const defaultMax = RANKING_MAX_WEIGHTS[key] ?? 15.0;
          const maxValue = Math.max(defaultMax, numericValue);
          const percent = maxValue > 0 ? (numericValue / maxValue) * 100 : 0;
          const level = percent >= 80 ? 'high' : percent >= 50 ? 'medium' : 'low';
          return (
            <div key={key} className="ranking-progress-item">
              <div className="ranking-progress-header">
                <span className="ranking-factor-label">{formatRankingLabel(key)}</span>
                <span className="ranking-factor-value">
                  {formatRankingValue(numericValue)} / {formatRankingValue(maxValue)}
                </span>
              </div>
              <div className="ranking-progress-bar">
                <div
                  className={`ranking-progress-fill ${level}`}
                  style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
                ></div>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  if (isLoading) return <div>Loading...</div>;
  if (error) return <div>Error loading job</div>;

  const backLink = job?.campaign_id ? `/campaigns/${job.campaign_id}` : '/jobs';
  const companyLogo = typeof job?.company_logo === 'string' ? job.company_logo : null;
  const companyLink = typeof job?.company_link === 'string' ? job.company_link : null;
  const hasRankExplain = Boolean(job?.rank_explain);

  return (
    <div>
      <div className="page-header">
        <h1>Job Details</h1>
        <Link to={backLink} className="back-link">
          ← Back to {job?.campaign_id ? 'Campaign' : 'Jobs'}
        </Link>
      </div>

      <div className="job-header-card">
        {companyLogo && (
          <div className="company-logo-large">
            <img
              src={companyLogo}
              alt={displayCompanyName}
              style={{ width: '100%', height: '100%', objectFit: 'contain', borderRadius: '8px' }}
              loading="lazy"
            />
          </div>
        )}
        <div className="job-header-info">
          <h2>{(job?.job_title as string) || 'Unknown Job Title'}</h2>
          <div className="company-name-large">
            <span>{displayCompanyName}</span>
            {companyLink && (
              <a href={companyLink} target="_blank" className="glassdoor-link" rel="noreferrer">
                <i className="fas fa-external-link-alt"></i> View on Glassdoor
              </a>
            )}
          </div>

          <div className="job-summary">
            <h3>Job Summary</h3>
            <div className="job-summary-content">
              {jobSummary ? jobSummary : <span style={{ opacity: 0.5 }}>No job summary available</span>}
            </div>
            {sharedCampaignNote && (
              <p
                style={{
                  marginTop: 'var(--spacing-sm)',
                  color: 'var(--color-text-muted)',
                  fontSize: 'var(--font-size-sm)',
                }}
              >
                {sharedCampaignNote}
              </p>
            )}
          </div>

          <div className="job-additional-info">
            <h3>Additional Information</h3>
            <div className="additional-info-grid">
              <div className="info-item">
                <span className="info-label">
                  <i className="fas fa-code"></i>
                  Skills
                </span>
                <div className="skills-list">
                  {parsedSkills.length > 0 ? (
                    parsedSkills.map((skill) => (
                      <span key={skill} className="skill-tag">
                        {skill}
                      </span>
                    ))
                  ) : (
                    <span className="skill-tag" style={{ opacity: 0.5 }}>
                      No skills listed
                    </span>
                  )}
                </div>
              </div>

              <div className="info-item">
                <span className="info-label">
                  <i className="fas fa-dollar-sign"></i>
                  Salary
                </span>
                <span className="info-value">
                  {job?.job_min_salary || job?.job_max_salary ? (
                    <>
                      {job?.job_min_salary && job?.job_max_salary
                        ? `$${Number(job.job_min_salary).toLocaleString()} - $${Number(
                            job.job_max_salary
                          ).toLocaleString()}`
                        : job?.job_min_salary
                          ? `$${Number(job.job_min_salary).toLocaleString()}+`
                          : `Up to $${Number(job.job_max_salary).toLocaleString()}`}
                      {job?.job_salary_period ? ` / ${job.job_salary_period}` : ''}
                      {job?.job_salary_currency ? ` ${job.job_salary_currency}` : ''}
                    </>
                  ) : (
                    'Not specified'
                  )}
                </span>
              </div>

              <div className="info-item">
                <span className="info-label">
                  <i className="fas fa-user-tie"></i>
                  Seniority Level
                </span>
                <span className="info-value">{titleCase(job?.seniority_level as string)}</span>
              </div>

              <div className="info-item">
                <span className="info-label">
                  <i className="fas fa-home"></i>
                  Remote Type
                </span>
                <span className="info-value">{titleCase(job?.remote_work_type as string)}</span>
              </div>

              <div className="info-item">
                <span className="info-label">
                  <i className="fas fa-map-marker-alt"></i>
                  Location
                </span>
                <span className="info-value">{(job?.job_location as string) || 'Not specified'}</span>
              </div>

              <div className="info-item">
                <span className="info-label">
                  <i className="fas fa-building"></i>
                  Company Size
                </span>
                <span className="info-value">{(job?.company_size as string) || 'Not specified'}</span>
              </div>
            </div>
          </div>

          <div className="job-meta-large">
            <div className="meta-item-large">
              <span className="meta-label">Posted At</span>
              <span className="meta-value">
                {job?.posted_at ? formatDate(job.posted_at as string) : formatDate(job?.ranked_at as string)}
              </span>
            </div>
            <div className="meta-item-large">
              <span className="meta-label">Rank</span>
              <span className="meta-value">
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span>
                    {score} - {score >= 80 ? 'Perfect Fit' : score >= 60 ? 'Good Fit' : 'Moderate Fit'}
                  </span>
                  {hasRankExplain && (
                    <button className="fit-info-icon" title="View ranking breakdown" onClick={openRankingModal}>
                      <i className="fas fa-info-circle"></i>
                    </button>
                  )}
                </span>
              </span>
            </div>
            <div className="meta-item-large">
              <span className="meta-label">Current Status</span>
              <span className="meta-value">
                <select
                  className="status-select-large"
                  value={status || currentStatus || 'waiting'}
                  onChange={(e) => handleStatusChange(e.target.value)}
                >
                  <option value="waiting">Waiting</option>
                  <option value="approved">Approved</option>
                  <option value="applied">Applied</option>
                  <option value="interview">Interview</option>
                  <option value="offer">Offer</option>
                  <option value="rejected">Rejected</option>
                  <option value="archived">Archived</option>
                </select>
              </span>
            </div>
            <div className="meta-item-large">
              <span className="meta-label">Job Posting</span>
              <span className="meta-value">
                {(() => {
                  const postingLinks = getJobPostingLinks(job ?? undefined);
                  if (postingLinks.length === 0) {
                    return <span style={{ opacity: 0.5 }}>Not available</span>;
                  }
                  return (
                    <span className="job-posting-links" style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                      {postingLinks.map(({ url, label }) => (
                        <a key={url} href={url} target="_blank" rel="noreferrer">
                          {label} →
                        </a>
                      ))}
                    </span>
                  );
                })()}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="section-card application-documents-section">
        <div className="section-header">
          <h2>Application Documents</h2>
        </div>
        <div className="documents-grid">
          <div className="document-item">
            <div className="document-item-header">
              <h3>Resume</h3>
              <button className="btn btn-primary btn-sm" onClick={() => setResumeModalOpen(true)}>
                <i className={`fas fa-${applicationDoc?.resume_id ? 'edit' : 'plus'}`}></i>{' '}
                {applicationDoc?.resume_id ? 'Change' : 'Add'}
              </button>
            </div>
            {applicationDoc?.resume_id ? (
              <div className="document-current">
                <div className="document-info">
                  <i className="fas fa-file-pdf"></i>
                  <span className="document-name">{applicationDoc.resume_name || 'Resume'}</span>
                  {applicationDoc.resume_file_type && (
                    <span className="document-size">
                      {applicationDoc.resume_file_type === 'application/pdf'
                        ? 'PDF'
                        : applicationDoc.resume_file_type.includes('wordprocessingml')
                          ? 'DOCX'
                          : applicationDoc.resume_file_type}
                    </span>
                  )}
                </div>
                <div className="document-actions">
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => handleDownloadResume(applicationDoc.resume_id as number)}
                  >
                    <i className="fas fa-download"></i> Download
                  </button>
                </div>
              </div>
            ) : (
              <div className="document-empty">
                <i
                  className="fas fa-file-pdf"
                  style={{
                    fontSize: '2rem',
                    color: 'var(--color-text-muted)',
                    marginBottom: 'var(--spacing-sm)',
                    opacity: 0.5,
                  }}
                ></i>
                <p>No resume linked to this job application.</p>
                <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', marginTop: 'var(--spacing-xs)' }}>
                  Upload your resume to track application materials
                </p>
              </div>
            )}
          </div>

          <div className="document-item">
            <div className="document-item-header">
              <h3>Cover Letter</h3>
              <button className="btn btn-secondary btn-sm" onClick={() => setCoverLetterModalOpen(true)}>
                <i className={`fas fa-${applicationDoc?.cover_letter_id || applicationDoc?.cover_letter_text ? 'edit' : 'plus'}`}></i>{' '}
                {applicationDoc?.cover_letter_id || applicationDoc?.cover_letter_text ? 'Change' : 'Add'}
              </button>
            </div>
            {applicationDoc?.cover_letter_id || applicationDoc?.cover_letter_text ? (
              <div className="document-current">
                <div className="document-info">
                  <i className="fas fa-file-alt"></i>
                  <span className="document-name">
                    {applicationDoc.cover_letter_id
                      ? applicationDoc.cover_letter_name || 'Cover Letter'
                      : 'Text Cover Letter'}
                  </span>
                </div>
                <div className="document-actions">
                  {applicationDoc.cover_letter_id && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleDownloadCoverLetter(applicationDoc.cover_letter_id as number)}
                    >
                      <i className="fas fa-download"></i> Download
                    </button>
                  )}
                  {applicationDoc.cover_letter_text && !applicationDoc.cover_letter_id && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleDownloadInlineCoverLetter(applicationDoc.cover_letter_text as string)}
                    >
                      <i className="fas fa-download"></i> Download as Text
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="document-empty">
                <i
                  className="fas fa-file-alt"
                  style={{
                    fontSize: '2rem',
                    color: 'var(--color-text-muted)',
                    marginBottom: 'var(--spacing-sm)',
                    opacity: 0.5,
                  }}
                ></i>
                <p>No cover letter linked to this job application.</p>
                <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-text-muted)', marginTop: 'var(--spacing-xs)' }}>
                  Create a cover letter to personalize your application
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="section-card comments-section">
        <div className="section-header">
          <h2>Application Notes</h2>
          {sortedNotes.length > MAX_NOTES_DISPLAYED && (
            <button className="btn btn-secondary" onClick={() => setAllNotesModalOpen(true)}>
              <i className="fas fa-list"></i> View All Notes ({sortedNotes.length})
            </button>
          )}
        </div>
        <div id="notesListContainer">
          <div id="notesList" style={{ minHeight: '100px' }}>
          {sortedNotes.length === 0 ? (
              <div className="notes-display">No notes yet.</div>
            ) : (
              displayedNotes.map((note) => (
                <div key={note.note_id} className="notes-display">
                  {renderNoteText(note)}
                  <div className="notes-meta">{formatDateTime(note.updated_at || note.created_at)}</div>
                </div>
              ))
            )}
          </div>
        </div>
        <hr style={{ margin: 'var(--spacing-lg) 0', border: 'none', borderTop: '1px solid var(--color-border)' }} />
        <div className="form-group" style={{ marginTop: 'var(--spacing-lg)' }}>
          <label htmlFor="note_text">Add New Note:</label>
          <textarea
            id="note_text"
            name="note_text"
            rows={4}
            placeholder="Enter your note here..."
            style={{
              width: '100%',
              padding: 'var(--spacing-sm)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--border-radius)',
              fontFamily: 'inherit',
              fontSize: 'var(--font-size-base)',
            }}
            value={newNoteText}
            onChange={(event) => setNewNoteText(event.target.value)}
          ></textarea>
          <div style={{ marginTop: 'var(--spacing-sm)' }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => addNoteMutation.mutate(newNoteText)}
              disabled={!newNoteText.trim()}
            >
              <i className="fas fa-plus"></i> Add Note
            </button>
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="section-header">
          <h2>Job Status History</h2>
          {sortedHistory.length > 3 && (
            <button className="btn btn-secondary" onClick={() => setAllHistoryModalOpen(true)}>
              <i className="fas fa-list"></i> View All History ({sortedHistory.length})
            </button>
          )}
        </div>
        {sharedCampaignNote && (
          <p
            style={{
              marginBottom: 'var(--spacing-sm)',
              color: 'var(--color-text-muted)',
              fontSize: 'var(--font-size-sm)',
            }}
          >
            {sharedCampaignNote}
          </p>
        )}
        {sortedHistory.length > 0 ? (
          <ul className="status-history">
            {displayedHistory.map((entry, index) => {
              const changedByLabel = formatChangedByLabel(entry.changed_by, entry.status, entry.change_type);
              const details = formatStatusHistoryDetails(entry);
              return (
                <li key={`${entry.status}-${entry.created_at}-${index}`} className="status-history-item">
                  <div className="status-info">
                    <div className="status-name">{formatStatusHistoryLabel(entry)}</div>
                    <div className="status-date">{formatDateTime(entry.created_at)}</div>
                    {details && <div className="status-reason">{details}</div>}
                    {changedByLabel && (
                      <div className="status-changed-by">
                        <small>Done by: {changedByLabel}</small>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <p>No status history available for this job.</p>
        )}
      </div>

      {rankingModalOpen && (
        <div className="modal-overlay active" onClick={closeRankingModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Job Ranking Breakdown</h3>
              <button className="modal-close" onClick={closeRankingModal} aria-label="Close">
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-content">
              <div>
                <strong>{displayCompanyName}</strong> - <span>{(job?.job_title as string) || 'Unknown Title'}</span>
              </div>
              <div className="ranking-score">
                Score: <span>{score}</span>
              </div>
              <div className="ranking-breakdown">
                <h4>Match Explanation</h4>
                <p>
                  {score >= 80 ? 'Perfect Match' : score >= 60 ? 'Good Match' : 'Moderate Match'}
                </p>
              </div>
              <div className="ranking-breakdown">
                <h4>Ranking Breakdown</h4>
                {renderRankingBreakdown()}
              </div>
            </div>
          </div>
        </div>
      )}

      {resumeModalOpen && (
        <div className="modal-overlay active" onClick={() => setResumeModalOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>Add Resume</h3>
              <button className="modal-close" onClick={() => setResumeModalOpen(false)} aria-label="Close">
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-content">
              <div className="modal-tabs">
                <button
                  className={`modal-tab ${resumeTab === 'upload' ? 'active' : ''}`}
                  onClick={() => setResumeTab('upload')}
                >
                  Upload New
                </button>
                <button
                  className={`modal-tab ${resumeTab === 'select' ? 'active' : ''}`}
                  onClick={() => setResumeTab('select')}
                >
                  Select Existing
                </button>
              </div>

              {resumeTab === 'upload' && (
                <form onSubmit={handleResumeUploadSubmit}>
                  <div className="form-group">
                    <label htmlFor="resumeName">Resume Name:</label>
                    <input
                      type="text"
                      id="resumeName"
                      placeholder="e.g., Data Engineer Resume v2"
                      value={resumeName}
                      onChange={(event) => setResumeName(event.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="resumeFile">Select File (PDF or DOCX, max 5MB):</label>
                    <input
                      type="file"
                      id="resumeFile"
                      accept=".pdf,.doc,.docx"
                      onChange={(event) => setResumeFile(event.target.files?.[0] || null)}
                      required
                    />
                  </div>
                  <div className="form-actions">
                    <button className="btn btn-primary" type="submit" disabled={!resumeFile || uploadResumeMutation.isPending}>
                      Upload
                    </button>
                    <button className="btn btn-secondary" type="button" onClick={() => setResumeModalOpen(false)}>
                      Cancel
                    </button>
                  </div>
                </form>
              )}

              {resumeTab === 'select' && (
                <div className="form-group">
                  <label htmlFor="resumeSelect">Select an existing resume:</label>
                  <select
                    id="resumeSelect"
                    className="document-select"
                    value={selectedResumeId}
                    onChange={(event) => setSelectedResumeId(event.target.value ? Number(event.target.value) : '')}
                  >
                    <option value="">Choose a resume...</option>
                    {userResumes.map((resume) => (
                      <option key={resume.resume_id} value={resume.resume_id}>
                        {resume.resume_name || `Resume ${resume.resume_id}`}
                      </option>
                    ))}
                  </select>
                  <div className="form-actions">
                    <button className="btn btn-primary" type="button" onClick={handleResumeLink} disabled={!selectedResumeId}>
                      Link Resume
                    </button>
                    <button className="btn btn-secondary" type="button" onClick={() => setResumeModalOpen(false)}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {coverLetterModalOpen && (
        <div className="modal-overlay active" onClick={() => setCoverLetterModalOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>Add Cover Letter</h3>
              <button className="modal-close" onClick={() => setCoverLetterModalOpen(false)} aria-label="Close">
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-content">
              <div className="modal-tabs">
                <button
                  className={`modal-tab ${coverLetterTab === 'create' ? 'active' : ''}`}
                  onClick={() => setCoverLetterTab('create')}
                >
                  Create New
                </button>
                <button
                  className={`modal-tab ${coverLetterTab === 'select' ? 'active' : ''}`}
                  onClick={() => setCoverLetterTab('select')}
                >
                  Select Existing
                </button>
                <button
                  className={`modal-tab ${coverLetterTab === 'generate' ? 'active' : ''}`}
                  onClick={() => setCoverLetterTab('generate')}
                >
                  Generate with AI
                </button>
              </div>

              {coverLetterTab === 'create' && (
                <div className="form-group">
                  <label htmlFor="coverLetterName">Cover Letter Name:</label>
                  <input
                    type="text"
                    id="coverLetterName"
                    placeholder={`e.g., Cover Letter for ${displayCompanyName}`}
                    value={coverLetterName}
                    onChange={(event) => setCoverLetterName(event.target.value)}
                  />
                  <label style={{ marginTop: 'var(--spacing-md)' }}>Create as:</label>
                  <div className="radio-group">
                    <label className="checkbox-option">
                      <input
                        type="radio"
                        name="coverLetterType"
                        value="text"
                        checked={coverLetterType === 'text'}
                        onChange={() => setCoverLetterType('text')}
                      />
                      Text
                    </label>
                    <label className="checkbox-option">
                      <input
                        type="radio"
                        name="coverLetterType"
                        value="file"
                        checked={coverLetterType === 'file'}
                        onChange={() => setCoverLetterType('file')}
                      />
                      File Upload
                    </label>
                  </div>
                  {coverLetterType === 'text' && (
                    <div className="form-group">
                      <label htmlFor="coverLetterText">Cover Letter Text:</label>
                      <textarea
                        id="coverLetterText"
                        rows={10}
                        placeholder="Dear Hiring Manager,&#10;&#10;I am writing to express my interest..."
                        value={coverLetterText}
                        onChange={(event) => setCoverLetterText(event.target.value)}
                      ></textarea>
                    </div>
                  )}
                  {coverLetterType === 'file' && (
                    <div className="form-group">
                      <label htmlFor="coverLetterFile">Select File (PDF or DOCX, max 5MB):</label>
                      <input
                        type="file"
                        id="coverLetterFile"
                        accept=".pdf,.doc,.docx"
                        onChange={(event) => setCoverLetterFile(event.target.files?.[0] || null)}
                      />
                    </div>
                  )}
                  <div className="form-actions">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={handleCreateCoverLetter}
                      disabled={
                        coverLetterType === 'text'
                          ? !coverLetterText.trim()
                          : !coverLetterFile
                      }
                    >
                      Create
                    </button>
                    <button type="button" className="btn btn-secondary" onClick={() => setCoverLetterModalOpen(false)}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {coverLetterTab === 'select' && (
                <div className="form-group">
                  <label htmlFor="coverLetterSelect">Select Existing Cover Letter</label>
                  <select
                    id="coverLetterSelect"
                    className="document-select"
                    value={selectedCoverLetterId}
                    onChange={(event) => setSelectedCoverLetterId(event.target.value ? Number(event.target.value) : '')}
                  >
                    <option value="">Choose a cover letter...</option>
                    {userCoverLetters.map((letter) => (
                      <option key={letter.cover_letter_id} value={letter.cover_letter_id}>
                        {letter.cover_letter_name || `Cover Letter ${letter.cover_letter_id}`}
                      </option>
                    ))}
                  </select>
                  <div className="form-actions">
                    <button className="btn btn-primary" type="button" onClick={handleCoverLetterSelect} disabled={!selectedCoverLetterId}>
                      Link Cover Letter
                    </button>
                    <button type="button" className="btn btn-secondary" onClick={() => setCoverLetterModalOpen(false)}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {coverLetterTab === 'generate' && (
                <div className="form-group">
                  <label htmlFor="generateResumeSelect">Resume to use</label>
                  <select
                    id="generateResumeSelect"
                    className="document-select"
                    value={generateResumeId}
                    onChange={(event) => setGenerateResumeId(event.target.value ? Number(event.target.value) : '')}
                  >
                    <option value="">Select a resume...</option>
                    {userResumes.map((resume) => (
                      <option key={resume.resume_id} value={resume.resume_id}>
                        {resume.resume_name || `Resume ${resume.resume_id}`}
                      </option>
                    ))}
                  </select>
                  <small className="form-text text-muted">
                    The AI will use this resume to generate a personalized cover letter.
                  </small>

                  <label htmlFor="generateComments" style={{ marginTop: 'var(--spacing-md)' }}>
                    Additional comments (optional)
                  </label>
                  <textarea
                    id="generateComments"
                    rows={4}
                    value={generateComments}
                    onChange={(event) => setGenerateComments(event.target.value)}
                    placeholder="Add any specific details you want to include..."
                  ></textarea>

                  {isGenerating && (
                    <div style={{ marginTop: 'var(--spacing-md)' }}>
                      <div className="loading-spinner">
                        <i className="fas fa-spinner fa-spin"></i>
                        <p>Generating your cover letter... This may take a moment.</p>
                      </div>
                    </div>
                  )}

                  {generateError && (
                    <div
                      style={{
                        marginTop: 'var(--spacing-md)',
                        padding: 'var(--spacing-md)',
                        backgroundColor: 'var(--color-error-light, #fee)',
                        border: '1px solid var(--color-error, #f00)',
                        borderRadius: 'var(--border-radius)',
                      }}
                    >
                      <p style={{ margin: 0, color: 'var(--color-error, #c00)' }}>
                        <i className="fas fa-exclamation-circle"></i> {generateError}
                      </p>
                    </div>
                  )}

                  {generatedCoverLetterText && (
                    <div style={{ marginTop: 'var(--spacing-md)' }}>
                      <label htmlFor="generatedCoverLetterText">Generated Cover Letter (you can edit before saving):</label>
                      <textarea
                        id="generatedCoverLetterText"
                        rows={12}
                        value={generatedCoverLetterText}
                        onChange={(event) => setGeneratedCoverLetterText(event.target.value)}
                      ></textarea>
                    </div>
                  )}

                  <div className="form-actions" style={{ marginTop: 'var(--spacing-md)' }}>
                    {!generatedCoverLetterText ? (
                      <>
                        <button
                          className="btn btn-primary"
                          type="button"
                          onClick={handleCoverLetterGenerate}
                          disabled={!generateResumeId || isGenerating}
                        >
                          <i className="fas fa-magic"></i> Generate
                        </button>
                        <button type="button" className="btn btn-secondary" onClick={() => setCoverLetterModalOpen(false)}>
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <button className="btn btn-primary" type="button" onClick={handleSaveGeneratedCoverLetter}>
                          <i className="fas fa-save"></i> Save Cover Letter
                        </button>
                        <button className="btn btn-secondary" type="button" onClick={handleCoverLetterGenerate}>
                          <i className="fas fa-redo"></i> Regenerate
                        </button>
                        <button className="btn btn-secondary" type="button" onClick={() => setGenerationHistoryOpen(true)}>
                          <i className="fas fa-history"></i> History
                        </button>
                        <button type="button" className="btn btn-secondary" onClick={() => setCoverLetterModalOpen(false)}>
                          Cancel
                        </button>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {generationHistoryOpen && (
        <div className="modal-overlay active" onClick={() => setGenerationHistoryOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>Cover Letter Generation History</h3>
              <button className="modal-close" onClick={() => setGenerationHistoryOpen(false)} aria-label="Close">
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-content">
              {coverLetterHistory.length === 0 ? (
                <p>No generation history yet.</p>
              ) : (
                coverLetterHistory.map((entry) => (
                  <div key={entry.cover_letter_id} className="document-current" style={{ marginBottom: 'var(--spacing-md)' }}>
                    <div className="document-info">
                      <i className="fas fa-file-alt"></i>
                      <span className="document-name">{entry.cover_letter_name || 'Cover Letter'}</span>
                    </div>
                    <div className="document-actions">
                      <button className="btn btn-secondary btn-sm" onClick={() => handleDownloadCoverLetter(entry.cover_letter_id)}>
                        <i className="fas fa-download"></i> Download
                      </button>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleCoverLetterHistoryLink(entry.cover_letter_id)}
                        style={{ marginLeft: 'var(--spacing-xs)' }}
                      >
                        <i className="fas fa-link"></i> Link
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {allNotesModalOpen && (
        <div className="modal-overlay active" onClick={() => setAllNotesModalOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>All Notes</h3>
              <button className="modal-close" onClick={() => setAllNotesModalOpen(false)} aria-label="Close">
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-content">
              {sortedNotes.length === 0 ? (
                <p>No notes available.</p>
              ) : (
                sortedNotes.map((note) => (
                  <div key={note.note_id} className="notes-display">
                    {editingNoteId === note.note_id ? (
                      <>
                        <textarea
                          rows={3}
                          value={editingNoteText}
                          onChange={(event) => setEditingNoteText(event.target.value)}
                        ></textarea>
                        <div style={{ marginTop: 'var(--spacing-sm)' }}>
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() =>
                              updateNoteMutation.mutate({ noteId: note.note_id, noteText: editingNoteText })
                            }
                          >
                            Save
                          </button>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setEditingNoteId(null);
                              setEditingNoteText('');
                            }}
                            style={{ marginLeft: 'var(--spacing-sm)' }}
                          >
                            Cancel
                          </button>
                        </div>
                      </>
                    ) : (
                      <>
                        {renderNoteText(note, true)}
                        <div className="notes-meta">{formatDateTime(note.updated_at || note.created_at)}</div>
                        <div style={{ marginTop: 'var(--spacing-sm)' }}>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => {
                              setEditingNoteId(note.note_id);
                              setEditingNoteText(note.note_text);
                            }}
                          >
                            Edit
                          </button>
                          <button
                            className="btn btn-danger btn-sm"
                            onClick={() => deleteNoteMutation.mutate(note.note_id)}
                            style={{ marginLeft: 'var(--spacing-sm)' }}
                          >
                            Delete
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {allHistoryModalOpen && (
        <div className="modal-overlay active" onClick={() => setAllHistoryModalOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h3>All Status History</h3>
              <button className="modal-close" onClick={() => setAllHistoryModalOpen(false)} aria-label="Close">
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="modal-content">
              {sortedHistory.length === 0 ? (
                <p>No status history available.</p>
              ) : (
                <ul className="status-history">
                  {sortedHistory.map((entry, index) => {
                    const changedByLabel = formatChangedByLabel(entry.changed_by, entry.status, entry.change_type);
                    const details = formatStatusHistoryDetails(entry);
                    return (
                      <li key={`${entry.status}-${entry.created_at}-${index}`} className="status-history-item">
                        <div className="status-info">
                          <div className="status-name">{formatStatusHistoryLabel(entry)}</div>
                          <div className="status-date">{formatDateTime(entry.created_at)}</div>
                          {details && <div className="status-reason">{details}</div>}
                          {changedByLabel && (
                            <div className="status-changed-by">
                              <small>Done by: {changedByLabel}</small>
                            </div>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
