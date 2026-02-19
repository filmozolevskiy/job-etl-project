import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import type { Campaign, Job } from '../types';

const JOBS_PER_PAGE = 20;
const VALID_STATUSES = ['waiting', 'approved', 'applied', 'interview', 'offer', 'rejected', 'archived'];
const COOLDOWN_HOURS = 1;
const STATUS_POLL_INTERVAL = 2000;
const PENDING_STATE_EXPIRY_MS = 5 * 60 * 1000;

type CampaignStatusData = {
  status: string;
  message?: string;
  completed_tasks?: string[];
  failed_tasks?: string[];
  is_complete?: boolean;
  jobs_available?: boolean;
  dag_run_id?: string | null;
};

export const CampaignDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const campaignId = id ? parseInt(id, 10) : 0;

  const [searchTerm, setSearchTerm] = useState('');
  const [sortFilter, setSortFilter] = useState('');
  const [selectedStatuses, setSelectedStatuses] = useState<Set<string>>(
    new Set(['waiting', 'approved', 'applied', 'interview', 'offer'])
  );
  const [currentPage, setCurrentPage] = useState(1);
  const [statusMenuOpen, setStatusMenuOpen] = useState(false);
  const [rankingModalOpen, setRankingModalOpen] = useState(false);
  const [selectedRankingJob, setSelectedRankingJob] = useState<Job | null>(null);
  const [findJobsStatus, setFindJobsStatus] = useState<'idle' | 'pending' | 'running' | 'cooldown'>('idle');
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const [statusData, setStatusData] = useState<CampaignStatusData | null>(null);
  const [lastDagRunId, setLastDagRunId] = useState<string | null>(null);
  const [statusOverride, setStatusOverride] = useState<{
    iconClass: string;
    text: string;
    badgeClass: string;
    errorMessage: string | null;
  } | null>(null);
  const jobsAlreadyRefreshedRef = useRef(false);
  const lastDagWasForcedRef = useRef(false);
  const pendingRunRef = useRef(false);
  const activeDagRunIdRef = useRef<string | null>(null);
  const lastTriggerTimestampRef = useRef<number | null>(null);

  const { data: campaignData, isLoading: campaignLoading, error: campaignError, refetch: refetchCampaign } = useQuery({
    queryKey: ['campaign', campaignId],
    queryFn: () => apiClient.getCampaign(campaignId),
    enabled: !!campaignId,
  });

  const toggleActiveMutation = useMutation({
    mutationFn: () => apiClient.toggleCampaignActive(campaignId),
    onSuccess: (data) => {
      if (data.success) {
        refetchCampaign();
      }
    },
  });

  const { data: jobsData, isLoading: jobsLoading, error: jobsError, refetch: refetchJobs } = useQuery({
    queryKey: ['jobs', campaignId],
    queryFn: () => apiClient.getJobs(campaignId),
    enabled: !!campaignId,
  });

  const campaign = campaignData
    ? ((campaignData as { campaign: unknown }).campaign as Campaign & {
        location?: string;
        last_run_at?: string;
        derived_run_status?: { status?: string; dag_run_id?: string };
      })
    : null;
  const jobs = jobsData ? ((jobsData as { jobs: unknown[] }).jobs as Job[]) : [];

  // Calculate stats
  const stats = useMemo(() => {
    const totalJobs = jobs.length;
    const appliedJobsCount = jobs.filter((job) => job.job_status === 'applied').length;
    return { totalJobs, appliedJobsCount };
  }, [jobs]);

  // Filter and sort jobs
  const filteredAndSortedJobs = useMemo(() => {
    let filtered = jobs.filter((job) => {
      // Search filter
      if (searchTerm) {
        const searchLower = searchTerm.toLowerCase();
        const jobLocation = (job as { job_location?: string }).job_location || '';
        const matchesSearch =
          (job.job_title || '').toLowerCase().includes(searchLower) ||
          (job.company_name || '').toLowerCase().includes(searchLower) ||
          jobLocation.toLowerCase().includes(searchLower);
        if (!matchesSearch) return false;
      }

      // Status filter
      const status = job.job_status || 'waiting';
      if (!selectedStatuses.has(status)) return false;

      return true;
    });

    // Sort: work on a copy so React detects the new reference and re-renders
    const sorted = [...filtered];
    if (sortFilter === 'date-newest') {
      sorted.sort((a, b) => {
        const dateA = (a as { job_posted_at_datetime_utc?: string }).job_posted_at_datetime_utc || '';
        const dateB = (b as { job_posted_at_datetime_utc?: string }).job_posted_at_datetime_utc || '';
        return dateB.localeCompare(dateA);
      });
    } else if (sortFilter === 'date-oldest') {
      sorted.sort((a, b) => {
        const dateA = (a as { job_posted_at_datetime_utc?: string }).job_posted_at_datetime_utc || '';
        const dateB = (b as { job_posted_at_datetime_utc?: string }).job_posted_at_datetime_utc || '';
        return dateA.localeCompare(dateB);
      });
    } else if (sortFilter === 'company-az') {
      sorted.sort((a, b) => (a.company_name || '').localeCompare(b.company_name || ''));
    } else if (sortFilter === 'company-za') {
      sorted.sort((a, b) => (b.company_name || '').localeCompare(a.company_name || ''));
    } else if (sortFilter === 'location-az') {
      sorted.sort((a, b) => {
        const locA = (a as { job_location?: string }).job_location || '';
        const locB = (b as { job_location?: string }).job_location || '';
        return locA.localeCompare(locB);
      });
    } else if (sortFilter === 'location-za') {
      sorted.sort((a, b) => {
        const locA = (a as { job_location?: string }).job_location || '';
        const locB = (b as { job_location?: string }).job_location || '';
        return locB.localeCompare(locA);
      });
    } else if (sortFilter === 'status-az') {
      sorted.sort((a, b) => (a.job_status || '').localeCompare(b.job_status || ''));
    } else if (sortFilter === 'status-za') {
      sorted.sort((a, b) => (b.job_status || '').localeCompare(a.job_status || ''));
    } else if (sortFilter === 'title-az') {
      sorted.sort((a, b) => (a.job_title || '').localeCompare(b.job_title || ''));
    } else if (sortFilter === 'title-za') {
      sorted.sort((a, b) => (b.job_title || '').localeCompare(a.job_title || ''));
    } else if (sortFilter === 'fit-score') {
      sorted.sort((a, b) => {
        const scoreA = (a as { rank_score?: number }).rank_score ?? 0;
        const scoreB = (b as { rank_score?: number }).rank_score ?? 0;
        return scoreB - scoreA;
      });
    } else if (sortFilter === 'fit-score-asc') {
      sorted.sort((a, b) => {
        const scoreA = (a as { rank_score?: number }).rank_score ?? 0;
        const scoreB = (b as { rank_score?: number }).rank_score ?? 0;
        return scoreA - scoreB;
      });
    }

    return sorted;
  }, [jobs, searchTerm, selectedStatuses, sortFilter]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filteredAndSortedJobs.length / JOBS_PER_PAGE));
  const paginatedJobs = useMemo(() => {
    const startIndex = (currentPage - 1) * JOBS_PER_PAGE;
    return filteredAndSortedJobs.slice(startIndex, startIndex + JOBS_PER_PAGE);
  }, [filteredAndSortedJobs, currentPage]);

  // Status filter handlers
  const handleStatusToggle = (status: string) => {
    const newSelected = new Set(selectedStatuses);
    if (status === 'all') {
      if (newSelected.size === VALID_STATUSES.length) {
        newSelected.clear();
      } else {
        VALID_STATUSES.forEach((s) => newSelected.add(s));
      }
    } else {
      if (newSelected.has(status)) {
        newSelected.delete(status);
      } else {
        newSelected.add(status);
      }
    }
    setSelectedStatuses(newSelected);
    setCurrentPage(1);
  };

  const getStatusFilterText = () => {
    if (selectedStatuses.size === 0) return 'Status: None';
    if (selectedStatuses.size === VALID_STATUSES.length) return 'Status: All';
    if (selectedStatuses.size === 1) {
      const status = Array.from(selectedStatuses)[0];
      return `Status: ${status.charAt(0).toUpperCase() + status.slice(1)}`;
    }
    return `Status: ${selectedStatuses.size} selected`;
  };

  // Close status menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest('#statusFilterDropdown')) {
        setStatusMenuOpen(false);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  // Update page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, selectedStatuses, sortFilter]);

  const updateJobStatusMutation = useMutation({
    mutationFn: ({ jobId, status }: { jobId: string; status: string }) =>
      apiClient.updateJobStatus(jobId, status),
    onSuccess: () => {
      refetchJobs();
    },
  });

  const handleStatusUpdate = (jobId: string, status: string) => {
    updateJobStatusMutation.mutate({ jobId, status });
  };

  /** Map table column header click to sortFilter; each click toggles direction so every click updates state. */
  const handleSortByColumn = (column: string) => {
    const toggle: Record<string, [string, string]> = {
      company: ['company-az', 'company-za'],
      location: ['location-az', 'location-za'],
      status: ['status-az', 'status-za'],
      date: ['date-newest', 'date-oldest'],
      title: ['title-az', 'title-za'],
      fit: ['fit-score', 'fit-score-asc'],
    };
    const [asc, desc] = toggle[column] ?? [];
    if (!asc || !desc) return;
    const next = sortFilter === asc ? desc : asc;
    setSortFilter(next);
  };

  const triggerCampaignMutation = useMutation({
    mutationFn: (forceStart: boolean) => apiClient.triggerCampaignDag(campaignId, forceStart),
    onSuccess: (response) => {
      if (response?.dag_run_id) {
        activeDagRunIdRef.current = response.dag_run_id;
        setLastDagRunId(response.dag_run_id);
      }
      if (typeof response?.forced === 'boolean') {
        lastDagWasForcedRef.current = response.forced;
      }
    },
  });

  const setPendingState = (id: number, forced = false) => {
    try {
      localStorage.setItem(`dag_pending_${id}`, JSON.stringify({ timestamp: Date.now(), forced }));
    } catch {
      // Ignore storage failures
    }
  };

  const getPendingState = (id: number) => {
    try {
      const raw = localStorage.getItem(`dag_pending_${id}`);
      return raw ? (JSON.parse(raw) as { timestamp: number; forced?: boolean }) : null;
    } catch {
      return null;
    }
  };

  const removePendingState = (id: number) => {
    try {
      localStorage.removeItem(`dag_pending_${id}`);
    } catch {
      // Ignore storage failures
    }
  };

  const calculateCooldownSeconds = (lastRunAt?: string) => {
    if (!lastRunAt) return 0;
    const lastRun = new Date(lastRunAt);
    if (Number.isNaN(lastRun.getTime())) return 0;
    const diffSeconds = Math.floor((Date.now() - lastRun.getTime()) / 1000);
    const cooldownTotalSeconds = COOLDOWN_HOURS * 3600;
    if (diffSeconds < 0 || diffSeconds >= cooldownTotalSeconds) return 0;
    return cooldownTotalSeconds - diffSeconds;
  };

  const isRecentDagRun = (dagRunId?: string, lastRunAt?: string) => {
    const oneHourMs = 60 * 60 * 1000;
    if (dagRunId) {
      try {
        const dateStr = dagRunId.replace('manual__', '').split('+')[0].split('.')[0];
        const runDate = new Date(`${dateStr}Z`);
        if (!Number.isNaN(runDate.getTime())) {
          return Date.now() - runDate.getTime() < oneHourMs;
        }
      } catch {
        return true;
      }
    }
    if (lastRunAt) {
      const lastRun = new Date(lastRunAt);
      if (!Number.isNaN(lastRun.getTime())) {
        return Date.now() - lastRun.getTime() < oneHourMs;
      }
    }
    return false;
  };

  const getStoredCooldownSeconds = (id: number) => {
    try {
      const stored = localStorage.getItem(`cooldown_end_${id}`);
      if (!stored) return 0;
      const cooldownEndTime = Number(stored);
      if (!Number.isFinite(cooldownEndTime)) return 0;
      const remaining = Math.floor((cooldownEndTime - Date.now()) / 1000);
      if (remaining > 0) return remaining;
      localStorage.removeItem(`cooldown_end_${id}`);
      return 0;
    } catch {
      return 0;
    }
  };

  useEffect(() => {
    if (!campaignId) return;
    setStatusData(null);
    setStatusOverride(null);
    setLastDagRunId(null);
    setFindJobsStatus('idle');
    setCooldownSeconds(0);
    jobsAlreadyRefreshedRef.current = false;
    lastDagWasForcedRef.current = false;
    pendingRunRef.current = false;
    activeDagRunIdRef.current = null;
    lastTriggerTimestampRef.current = null;
  }, [campaignId]);

  useEffect(() => {
    if (!campaign || !campaignId) return;

    if (pendingRunRef.current) {
      setFindJobsStatus('pending');
      return;
    }

    if (statusData?.status === 'running') {
      removePendingState(campaignId);
      setFindJobsStatus('running');
      return;
    }
    if (statusData?.status === 'pending') {
      setFindJobsStatus('pending');
      return;
    }
    if (statusData?.status === 'success' || statusData?.status === 'error') {
      removePendingState(campaignId);
      setFindJobsStatus('idle');
      return;
    }

    const derivedStatus = campaign.derived_run_status?.status;
    const dagRunId = campaign.derived_run_status?.dag_run_id;

    if (derivedStatus === 'running' || derivedStatus === 'pending') {
      if (isRecentDagRun(dagRunId, campaign.last_run_at)) {
        removePendingState(campaignId);
        setFindJobsStatus(derivedStatus === 'running' ? 'running' : 'pending');
        return;
      }
    }

    const pending = getPendingState(campaignId);
    if (pending && Date.now() - pending.timestamp < PENDING_STATE_EXPIRY_MS) {
      setFindJobsStatus('pending');
      return;
    }
    if (pending) {
      removePendingState(campaignId);
    }

    const storedCooldown = getStoredCooldownSeconds(campaignId);
    const cooldown = storedCooldown > 0 ? storedCooldown : calculateCooldownSeconds(campaign.last_run_at);
    if (cooldown > 0) {
      setCooldownSeconds(cooldown);
      setFindJobsStatus('cooldown');
      return;
    }

    setFindJobsStatus('idle');
  }, [campaign, campaignId, statusData]);

  useEffect(() => {
    if (!campaignId) return undefined;

    let intervalId: number | undefined;

    const pollStatus = async () => {
      try {
        const dagRunId = activeDagRunIdRef.current;
        const data = await apiClient.getCampaignStatus(campaignId, dagRunId);

        const isCurrentRun = (() => {
          if (activeDagRunIdRef.current && data.dag_run_id) {
            return data.dag_run_id === activeDagRunIdRef.current;
          }
          if (lastTriggerTimestampRef.current && data.dag_run_id) {
            try {
              const runId = data.dag_run_id.replace('manual__', '').split('+')[0].split('.')[0];
              const runTime = new Date(`${runId}Z`).getTime();
              if (!Number.isNaN(runTime)) {
                return runTime >= lastTriggerTimestampRef.current - 1000;
              }
            } catch {
              return false;
            }
          }
          return !lastTriggerTimestampRef.current;
        })();

        if (pendingRunRef.current && lastTriggerTimestampRef.current && data.dag_run_id) {
          try {
            const runId = data.dag_run_id.replace('manual__', '').split('+')[0].split('.')[0];
            const runTime = new Date(`${runId}Z`).getTime();
            if (!Number.isNaN(runTime) && runTime < lastTriggerTimestampRef.current - 1000) {
              return;
            }
          } catch {
            // Ignore parse errors and continue.
          }
        }

        if (pendingRunRef.current && data.status === 'success' && data.is_complete && !data.jobs_available) {
          return;
        }

        setStatusData(data);
        if (data.status === 'running' || data.status === 'pending') {
          setStatusOverride(null);
        }
        if (data.dag_run_id) {
          setLastDagRunId(data.dag_run_id);
          if (!activeDagRunIdRef.current) {
            activeDagRunIdRef.current = data.dag_run_id;
          }
          pendingRunRef.current = false;
        }
        if (data.jobs_available && !jobsAlreadyRefreshedRef.current) {
          jobsAlreadyRefreshedRef.current = true;
          setStatusOverride({
            iconClass: 'fa-check-circle',
            text: 'Jobs Available',
            badgeClass: 'done',
            errorMessage: null,
          });
          window.setTimeout(() => {
            setStatusOverride(null);
            refetchCampaign();
            refetchJobs();
          }, 2000);
          return;
        }

        if (data.is_complete && data.status === 'success') {
          if (!isCurrentRun) {
            return;
          }
          const wasForced = lastDagWasForcedRef.current || getPendingState(campaignId)?.forced === true;
          lastDagWasForcedRef.current = false;
          removePendingState(campaignId);

          setStatusOverride({
            iconClass: 'fa-check-circle',
            text: 'Complete',
            badgeClass: 'done',
            errorMessage: null,
          });

          if (!wasForced) {
            const cooldownTotal = COOLDOWN_HOURS * 3600;
            setCooldownSeconds(cooldownTotal);
            setFindJobsStatus('cooldown');
            try {
              localStorage.setItem(`cooldown_end_${campaignId}`, String(Date.now() + cooldownTotal * 1000));
            } catch {
              // Ignore storage failures
            }
            window.setTimeout(() => {
              setStatusOverride(null);
              refetchCampaign();
              refetchJobs();
            }, 5000);
          } else {
            setFindJobsStatus('idle');
            try {
              localStorage.removeItem(`cooldown_end_${campaignId}`);
            } catch {
              // Ignore storage failures
            }
            window.setTimeout(() => {
              setStatusOverride(null);
              refetchCampaign();
              refetchJobs();
            }, 3000);
          }
          return;
        }

        if (data.is_complete && data.status === 'error') {
          if (!isCurrentRun) {
            return;
          }
          const failed = data.failed_tasks || [];
          const errorMessage =
            failed.length > 0 ? `Failed: ${failed.join(', ')}` : data.message || 'Pipeline error occurred';
          setStatusOverride({
            iconClass: 'fa-exclamation-circle',
            text: 'Error',
            badgeClass: 'error',
            errorMessage,
          });
          setFindJobsStatus('idle');
          return;
        }

        if (data.status === 'running') {
          setFindJobsStatus('running');
        } else if (data.status === 'pending') {
          setFindJobsStatus('pending');
        }
      } catch {
        // Leave existing status; polling will retry.
      }
    };

    if (findJobsStatus === 'running' || findJobsStatus === 'pending') {
      pollStatus();
      intervalId = window.setInterval(pollStatus, STATUS_POLL_INTERVAL);
    }

    return () => {
      if (intervalId) window.clearInterval(intervalId);
    };
  }, [findJobsStatus, campaignId, lastDagRunId, refetchCampaign]);

  useEffect(() => {
    if (findJobsStatus !== 'cooldown') return undefined;

    const intervalId = window.setInterval(() => {
      setCooldownSeconds((prev) => {
        if (prev <= 1) {
          window.clearInterval(intervalId);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, [findJobsStatus]);

  const openRankingModal = (job: Job) => {
    setSelectedRankingJob(job);
    setRankingModalOpen(true);
  };

  const closeRankingModal = () => {
    setRankingModalOpen(false);
    setSelectedRankingJob(null);
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

  const renderRankingBreakdown = (rankExplain: Record<string, unknown> | undefined) => {
    if (!rankExplain || Object.keys(rankExplain).length === 0) {
      return <p>No ranking breakdown available.</p>;
    }

    const entries = Object.entries(rankExplain)
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
                <div className={`ranking-progress-fill ${level}`} style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}></div>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const isAdmin = user?.role === 'admin';
  const campaignDataExtended = campaign
    ? (campaign as Campaign & {
        location?: string;
        last_run_at?: string;
        derived_run_status?: { status: string };
        ranking_weights?: unknown;
      })
    : null;

  const statusDisplay = useMemo(() => {
    if (statusOverride) {
      return statusOverride;
    }

    const taskStageMap: Record<string, string> = {
      extract_job_postings: 'Looking for jobs...',
      normalize_jobs: 'Processing jobs...',
      rank_jobs: 'Ranking jobs...',
      send_notifications: 'Preparing results...',
    };

    if (statusData?.status === 'running') {
      const completed = statusData.completed_tasks || [];
      const lastTask = completed.length > 0 ? completed[completed.length - 1] : null;
      const stage = lastTask ? taskStageMap[lastTask] || 'Processing...' : 'Starting...';
      let iconClass = 'fa-tasks';
      if (completed.includes('extract_job_postings') && !completed.includes('normalize_jobs')) {
        iconClass = 'fa-search';
      } else if (completed.includes('normalize_jobs') && !completed.includes('rank_jobs')) {
        iconClass = 'fa-cog fa-spin';
      } else if (completed.includes('rank_jobs') && !completed.includes('send_notifications')) {
        iconClass = 'fa-sort-amount-down';
      }
      return { iconClass, text: stage, badgeClass: 'processing', errorMessage: null };
    }

    if (statusData?.status === 'pending') {
      const text = statusData.dag_run_id ? 'Waiting for tasks...' : 'Starting...';
      return { iconClass: 'fa-spinner fa-spin', text, badgeClass: 'processing', errorMessage: null };
    }

    if (statusData?.status === 'success') {
      return { iconClass: 'fa-check-circle', text: 'Complete', badgeClass: 'done', errorMessage: null };
    }

    if (statusData?.status === 'error') {
      const failed = statusData.failed_tasks || [];
      const errorMessage = failed.length > 0 ? `Failed: ${failed.join(', ')}` : statusData.message || 'Pipeline error occurred';
      return { iconClass: 'fa-exclamation-circle', text: 'Error', badgeClass: 'error', errorMessage };
    }

    const derivedStatus = campaignDataExtended?.derived_run_status?.status;
    if (derivedStatus === 'running') {
      return { iconClass: 'fa-cog fa-spin', text: 'Running', badgeClass: 'processing', errorMessage: null };
    }
    if (derivedStatus === 'pending') {
      return { iconClass: 'fa-spinner fa-spin', text: 'Pending', badgeClass: 'processing', errorMessage: null };
    }
    if (derivedStatus === 'error') {
      return { iconClass: 'fa-exclamation-circle', text: 'Error', badgeClass: 'error', errorMessage: null };
    }

    if (findJobsStatus === 'pending') {
      return { iconClass: 'fa-spinner fa-spin', text: 'Starting...', badgeClass: 'processing', errorMessage: null };
    }

    if (campaign?.is_active) {
      return { iconClass: 'fa-play', text: 'Active', badgeClass: 'processing', errorMessage: null };
    }

    return { iconClass: 'fa-pause', text: 'Paused', badgeClass: 'paused', errorMessage: null };
  }, [campaign, campaignDataExtended, findJobsStatus, statusData, statusOverride]);

  if (campaignLoading) return <div>Loading...</div>;
  if (campaignError) return <div>Error loading campaign</div>;

  if (!campaign) return <div>Campaign not found</div>;

  const formatCooldownTime = (totalSeconds: number) => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds
      .toString()
      .padStart(2, '0')}`;
  };

  return (
    <div>
      <div className="page-header">
        <Link to="/campaigns" className="back-link">
          ← Back to Campaigns
        </Link>
        <h1>{campaign.campaign_name}</h1>
      </div>

      <div className="card mb-4">
        <div className="toggle-container" style={{ marginBottom: 0, border: 'none', padding: 0, width: '100%', justifyContent: 'space-between', display: 'flex', alignItems: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span className="toggle-label" style={{ fontSize: 'var(--font-size-lg)', fontWeight: 'bold' }}>Campaign Active</span>
            <small className="form-hint" style={{ marginTop: 0 }}>Toggle whether this campaign is used for job extraction and ranking.</small>
          </div>
          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={campaign.is_active}
              onChange={() => toggleActiveMutation.mutate()}
              disabled={toggleActiveMutation.isPending}
            />
            <span className="toggle-slider"></span>
          </label>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid campaign-details-stats-grid">
        <div className="stat-card-item">
          <div className="stat-label">Status</div>
          <div className="status-with-button">
            <div className="status-badge-container">
              <div className={`status-badge ${statusDisplay.badgeClass}`} id="campaignStatus">
                <i className={`fas ${statusDisplay.iconClass}`}></i> {statusDisplay.text}
              </div>
              <button
                type="button"
                className="btn btn-success find-jobs-btn"
                id="findJobsBtn"
                onClick={() => {
                  if (findJobsStatus === 'running' || findJobsStatus === 'pending' || findJobsStatus === 'cooldown') {
                    return;
                  }
                  setPendingState(campaignId);
                  lastDagWasForcedRef.current = false;
                  jobsAlreadyRefreshedRef.current = false;
                  pendingRunRef.current = true;
                  activeDagRunIdRef.current = null;
                  lastTriggerTimestampRef.current = Date.now();
                  setStatusData(null);
                  setLastDagRunId(null);
                  setStatusOverride({
                    iconClass: 'fa-spinner fa-spin',
                    text: 'Starting...',
                    badgeClass: 'processing',
                    errorMessage: null,
                  });
                  setFindJobsStatus('pending');
                  triggerCampaignMutation.mutate(false);
                }}
                disabled={
                  triggerCampaignMutation.isPending ||
                  findJobsStatus === 'running' ||
                  findJobsStatus === 'pending' ||
                  findJobsStatus === 'cooldown'
                }
              >
                {findJobsStatus === 'running' && (
                  <>
                    <i className="fas fa-spinner fa-spin"></i> Running...
                  </>
                )}
                {findJobsStatus === 'pending' && (
                  <>
                    <i className="fas fa-spinner fa-spin"></i>{' '}
                    {statusData?.status === 'pending' && !statusData.dag_run_id ? 'Starting...' : 'Pending...'}
                  </>
                )}
                {findJobsStatus === 'cooldown' && (
                  <>
                    <i className="fas fa-clock"></i> Cooldown: {formatCooldownTime(cooldownSeconds)}
                  </>
                )}
                {findJobsStatus === 'idle' && (
                  <>
                    <i className="fas fa-search"></i> Find Jobs
                  </>
                )}
              </button>
              {isAdmin && findJobsStatus === 'cooldown' && (
                <button
                  type="button"
                  className="btn btn-warning find-jobs-btn"
                  id="forceStartBtn"
                  title="Force start (bypass cooldown)"
                  onClick={() => {
                    setPendingState(campaignId, true);
                    lastDagWasForcedRef.current = true;
                    jobsAlreadyRefreshedRef.current = false;
                    pendingRunRef.current = true;
                    activeDagRunIdRef.current = null;
                    lastTriggerTimestampRef.current = Date.now();
                    setStatusData(null);
                    setLastDagRunId(null);
                    setStatusOverride({
                      iconClass: 'fa-spinner fa-spin',
                      text: 'Starting...',
                      badgeClass: 'processing',
                      errorMessage: null,
                    });
                    setFindJobsStatus('pending');
                    triggerCampaignMutation.mutate(true);
                  }}
                >
                  <i className="fas fa-bolt"></i> Force Start
                </button>
              )}
              {triggerCampaignMutation.isError && (
                <div className="error-message" style={{ marginTop: 'var(--spacing-sm)' }}>
                  Failed to trigger jobs. Please try again.
                </div>
              )}
              {statusDisplay.errorMessage && (
                <div className="error-message" style={{ marginTop: 'var(--spacing-sm)' }}>
                  {statusDisplay.errorMessage}
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="stat-card-item">
          <div className="stat-label">Jobs Processed</div>
          <div className="stat-value">
            {stats.appliedJobsCount} / {stats.totalJobs}
          </div>
        </div>
        <div className="stat-card-item">
          <div className="stat-label">Last Update</div>
          <div className="stat-value stat-value-small">
            {campaignDataExtended?.last_run_at
              ? new Date(campaignDataExtended.last_run_at).toLocaleString('en-US', {
                  year: 'numeric',
                  month: '2-digit',
                  day: '2-digit',
                  hour: '2-digit',
                  minute: '2-digit',
                })
              : 'Never'}
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="table-header-bar">
        <input
          type="text"
          className="search-input"
          id="jobSearch"
          placeholder="Search jobs or companies..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <div className="header-controls">
          <select id="sortFilter" value={sortFilter} onChange={(e) => setSortFilter(e.target.value)}>
            <option value="">Sort</option>
            <option value="date-newest">Date (Newest)</option>
            <option value="date-oldest">Date (Oldest)</option>
            <option value="company-az">Company A-Z</option>
            <option value="company-za">Company Z-A</option>
            <option value="location-az">Location A-Z</option>
            <option value="location-za">Location Z-A</option>
            <option value="status-az">Status A-Z</option>
            <option value="status-za">Status Z-A</option>
            <option value="title-az">Title A-Z</option>
            <option value="title-za">Title Z-A</option>
            <option value="fit-score">Fit (High first)</option>
            <option value="fit-score-asc">Fit (Low first)</option>
          </select>
          <div className="multi-select-dropdown" id="statusFilterDropdown">
            <button
              className="multi-select-button"
              type="button"
              id="statusFilterButton"
              aria-haspopup="true"
              aria-expanded={statusMenuOpen}
              aria-label="Filter jobs by status"
              onClick={() => setStatusMenuOpen(!statusMenuOpen)}
            >
              <span id="statusFilterText">{getStatusFilterText()}</span>
              <i className="fas fa-chevron-down"></i>
            </button>
            <div
              className="multi-select-menu"
              id="statusFilterMenu"
              role="listbox"
              aria-label="Status filter options"
              style={{ display: statusMenuOpen ? 'block' : 'none' }}
            >
              <div className="multi-select-item">
                <label className="multi-select-label">
                  <input
                    type="checkbox"
                    className="status-checkbox"
                    value="all"
                    id="statusAll"
                    checked={selectedStatuses.size === VALID_STATUSES.length}
                    onChange={() => handleStatusToggle('all')}
                  />
                  <span>All Statuses</span>
                </label>
              </div>
              <div className="multi-select-divider"></div>
              {VALID_STATUSES.map((status) => (
                <div key={status} className="multi-select-item">
                  <label className="multi-select-label">
                    <input
                      type="checkbox"
                      className="status-checkbox"
                      value={status}
                      checked={selectedStatuses.has(status)}
                      onChange={() => handleStatusToggle(status)}
                    />
                    <span>{status.charAt(0).toUpperCase() + status.slice(1)}</span>
                  </label>
                </div>
              ))}
            </div>
          </div>
          <button className="refresh-btn btn btn-secondary" onClick={() => refetchJobs()} aria-label="Refresh">
            <i className="fas fa-sync-alt"></i> Refresh
          </button>
        </div>
      </div>

      {/* Jobs Table/Cards */}
      <div className="jobs-table-wrapper">
        {jobsLoading ? (
          <div>Loading jobs...</div>
        ) : jobsError ? (
          <div>Error loading jobs</div>
        ) : paginatedJobs.length === 0 ? (
          <div className="card">
            <div className="empty-state">
              <div className="empty-state-icon">
                <i className="fas fa-briefcase"></i>
              </div>
              <h2 className="empty-state-title">No Jobs Found</h2>
              <p className="empty-state-message">
                This campaign hasn't found any jobs yet. Click "Find Jobs" to start searching for matching positions
                based on your campaign criteria.
              </p>
              <button
                type="button"
                className="btn btn-primary"
                id="findJobsBtnEmpty"
                onClick={() => {
                  alert('Find Jobs functionality will be implemented with Airflow DAG trigger API');
                }}
              >
                <i className="fas fa-search"></i> Find Jobs
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Desktop Table View */}
            <table className="jobs-table">
              <thead>
                <tr>
                  <th
                    className="sortable"
                    data-sort="company"
                    role="button"
                    tabIndex={0}
                    onClick={() => handleSortByColumn('company')}
                    onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSortByColumn('company');
                    }
                  }}
                    aria-sort={
                      sortFilter === 'company-az' ? 'ascending' : sortFilter === 'company-za' ? 'descending' : undefined
                    }
                  >
                    Company Name
                  </th>
                  <th
                    className="sortable"
                    data-sort="location"
                    role="button"
                    tabIndex={0}
                    onClick={() => handleSortByColumn('location')}
                    onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSortByColumn('location');
                    }
                  }}
                    aria-sort={
                      sortFilter === 'location-az' ? 'ascending' : sortFilter === 'location-za' ? 'descending' : undefined
                    }
                  >
                    Job Location
                  </th>
                  <th
                    className="sortable"
                    data-sort="status"
                    role="button"
                    tabIndex={0}
                    onClick={() => handleSortByColumn('status')}
                    onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSortByColumn('status');
                    }
                  }}
                    aria-sort={
                      sortFilter === 'status-az' ? 'ascending' : sortFilter === 'status-za' ? 'descending' : undefined
                    }
                  >
                    Status
                  </th>
                  <th
                    className="sortable"
                    data-sort="date"
                    role="button"
                    tabIndex={0}
                    onClick={() => handleSortByColumn('date')}
                    onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSortByColumn('date');
                    }
                  }}
                    aria-sort={
                      sortFilter === 'date-newest' ? 'descending' : sortFilter === 'date-oldest' ? 'ascending' : undefined
                    }
                  >
                    Posted At
                  </th>
                  <th
                    className="sortable"
                    data-sort="title"
                    role="button"
                    tabIndex={0}
                    onClick={() => handleSortByColumn('title')}
                    onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSortByColumn('title');
                    }
                  }}
                    aria-sort={
                      sortFilter === 'title-az' ? 'ascending' : sortFilter === 'title-za' ? 'descending' : undefined
                    }
                  >
                    Job Posting
                  </th>
                  <th
                    className="sortable"
                    data-sort="fit"
                    role="button"
                    tabIndex={0}
                    onClick={() => handleSortByColumn('fit')}
                    onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSortByColumn('fit');
                    }
                  }}
                    aria-sort={
                      sortFilter === 'fit-score' ? 'descending' : sortFilter === 'fit-score-asc' ? 'ascending' : undefined
                    }
                  >
                    Fit
                  </th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {paginatedJobs.map((job) => {
                  const jobData = job as Job & {
                    company_logo?: string;
                    ranked_at?: string;
                    job_posted_at_datetime_utc?: string;
                    rank_score?: number;
                    rank_explain?: Record<string, unknown>;
                  };
                  const status = job.job_status || 'waiting';
                  const score = jobData.rank_score || 0;
                  const scoreInt = Math.round(score);
                  return (
                    <tr key={job.jsearch_job_id} data-job-id={job.jsearch_job_id}>
                      <td>
                        <div className="table-company-name">
                          {jobData.company_logo && (
                            <img
                              src={jobData.company_logo}
                              alt={job.company_name || 'Unknown'}
                              className="table-company-logo"
                              loading="lazy"
                            />
                          )}
                          <span>{job.company_name || 'Unknown'}</span>
                        </div>
                      </td>
                      <td>
                        <span className="table-job-location">
                          {(job as { job_location?: string }).job_location || '-'}
                        </span>
                      </td>
                      <td>
                        <span className={`table-status-badge ${status}`}>
                          <i
                            className={`fas ${
                              status === 'applied'
                                ? 'fa-check-circle'
                                : status === 'approved'
                                  ? 'fa-thumbs-up'
                                  : status === 'interview'
                                    ? 'fa-calendar-check'
                                    : status === 'offer'
                                      ? 'fa-hand-holding-usd'
                                      : status === 'rejected'
                                        ? 'fa-times-circle'
                                        : 'fa-clock'
                            }`}
                          ></i>{' '}
                          {status.charAt(0).toUpperCase() + status.slice(1)}
                        </span>
                      </td>
                      <td>
                        {jobData.job_posted_at_datetime_utc
                          ? (() => {
                              const postedDate = new Date(jobData.job_posted_at_datetime_utc);
                              const now = new Date();
                              const daysAgo = Math.floor((now.getTime() - postedDate.getTime()) / (1000 * 60 * 60 * 24));
                              if (daysAgo === 0) return 'Today';
                              if (daysAgo === 1) return '1 day ago';
                              if (daysAgo < 7) return `${daysAgo} days ago`;
                              if (daysAgo < 14) return '1 week ago';
                              return `${Math.floor(daysAgo / 7)} weeks ago`;
                            })()
                          : '-'}
                      </td>
                      <td>
                        <Link to={`/jobs/${job.jsearch_job_id}`}>{job.job_title || 'Unknown Title'}</Link>
                      </td>
                      <td>
                        <div className="fit-badge-wrapper">
                          {scoreInt >= 80 ? (
                            <span className="fit-badge perfect-fit">
                              {scoreInt} Perfect
                            </span>
                          ) : scoreInt >= 60 ? (
                            <span className="fit-badge good-fit">
                              {scoreInt} Good
                            </span>
                          ) : (
                            <span className="fit-badge moderate-fit">
                              {scoreInt} Moderate
                            </span>
                          )}
                          {jobData.rank_explain && (
                            <button
                              type="button"
                              className="fit-info-icon"
                              title="View ranking breakdown"
                              onClick={() => openRankingModal(jobData)}
                            >
                              <i className="fas fa-info-circle"></i>
                            </button>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="table-action-buttons">
                          {status === 'waiting' && (
                            <>
                              <button
                                type="button"
                                className="btn btn-success btn-small"
                                onClick={() => handleStatusUpdate(job.jsearch_job_id, 'approved')}
                                disabled={updateJobStatusMutation.isPending}
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                className="btn btn-danger btn-small"
                                onClick={() => handleStatusUpdate(job.jsearch_job_id, 'rejected')}
                                disabled={updateJobStatusMutation.isPending}
                              >
                                Reject
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Mobile Card View */}
            <div className="cards-container job-cards-container">
              {paginatedJobs.map((job) => {
                const jobData = job as Job & {
                  company_logo?: string;
                  ranked_at?: string;
                  job_posted_at_datetime_utc?: string;
                  rank_score?: number;
                  rank_explain?: Record<string, unknown>;
                };
                const status = job.job_status || 'waiting';
                const score = jobData.rank_score || 0;
                const scoreInt = Math.round(score);
                return (
                  <div key={job.jsearch_job_id} className="job-card" data-job-id={job.jsearch_job_id}>
                    <div className="job-card-header">
                      <h3 className="job-card-title">
                        <Link to={`/jobs/${job.jsearch_job_id}`}>{job.job_title || 'Unknown Title'}</Link>
                      </h3>
                      <div className="fit-badge-wrapper">
                        {scoreInt >= 80 ? (
                          <span className="fit-badge perfect-fit">
                            {scoreInt} Perfect
                          </span>
                        ) : scoreInt >= 60 ? (
                          <span className="fit-badge good-fit">
                            {scoreInt} Good
                          </span>
                        ) : (
                          <span className="fit-badge moderate-fit">
                            {scoreInt} Moderate
                          </span>
                        )}
                      {jobData.rank_explain && (
                        <button
                          type="button"
                          className="fit-info-icon"
                          title="View ranking breakdown"
                          onClick={() => openRankingModal(jobData)}
                        >
                          <i className="fas fa-info-circle"></i>
                        </button>
                      )}
                      </div>
                    </div>
                    <div className="job-card-meta">
                      <div className="job-card-meta-item">
                        <span className="job-card-meta-label">Company:</span>
                        <span>{job.company_name || 'Unknown'}</span>
                      </div>
                      <div className="job-card-meta-item">
                        <span className="job-card-meta-label">Location:</span>
                        <span>{(job as { job_location?: string }).job_location || '-'}</span>
                      </div>
                      <div className="job-card-meta-item">
                        <span className="job-card-meta-label">Status:</span>
                        <span className={`table-status-badge ${status}`}>
                          <i
                            className={`fas ${
                              status === 'applied'
                                ? 'fa-check-circle'
                                : status === 'approved'
                                  ? 'fa-thumbs-up'
                                  : status === 'interview'
                                    ? 'fa-calendar-check'
                                    : status === 'offer'
                                      ? 'fa-hand-holding-usd'
                                      : status === 'rejected'
                                        ? 'fa-times-circle'
                                        : 'fa-clock'
                            }`}
                          ></i>{' '}
                          {status.charAt(0).toUpperCase() + status.slice(1)}
                        </span>
                      </div>
                      <div className="job-card-meta-item">
                        <span className="job-card-meta-label">Posted:</span>
                        <span>
                          {jobData.job_posted_at_datetime_utc
                            ? (() => {
                                const postedDate = new Date(jobData.job_posted_at_datetime_utc);
                                const now = new Date();
                                const daysAgo = Math.floor((now.getTime() - postedDate.getTime()) / (1000 * 60 * 60 * 24));
                                if (daysAgo === 0) return 'Today';
                                if (daysAgo === 1) return '1 day ago';
                                if (daysAgo < 7) return `${daysAgo} days ago`;
                                if (daysAgo < 14) return '1 week ago';
                                return `${Math.floor(daysAgo / 7)} weeks ago`;
                              })()
                            : '-'}
                        </span>
                      </div>
                    </div>
                    <div className="job-card-actions">
                      {status === 'waiting' && (
                        <>
                          <button
                            type="button"
                            className="btn btn-success btn-small"
                            onClick={() => handleStatusUpdate(job.jsearch_job_id, 'approved')}
                            disabled={updateJobStatusMutation.isPending}
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-small"
                            onClick={() => handleStatusUpdate(job.jsearch_job_id, 'rejected')}
                            disabled={updateJobStatusMutation.isPending}
                          >
                            Reject
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      {/* Pagination */}
      {filteredAndSortedJobs.length > 0 && (
        <div className="pagination">
          <button
            className="pagination-btn"
            id="prevPageBtn"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
          >
            ←
          </button>
          <span className="pagination-info" id="paginationInfo">
            {currentPage} of {totalPages}
          </span>
          <button
            className="pagination-btn"
            id="nextPageBtn"
            disabled={currentPage >= totalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
          >
            →
          </button>
        </div>
      )}

      {rankingModalOpen && selectedRankingJob && (
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
                <strong>{selectedRankingJob.company_name || 'Unknown Company'}</strong> -{' '}
                <span>{selectedRankingJob.job_title || 'Unknown Title'}</span>
              </div>
              <div className="ranking-score">
                Score: <span>{Math.round(Number(selectedRankingJob.rank_score ?? 0))}</span>
              </div>
              <div className="ranking-breakdown">
                <h4>Match Explanation</h4>
                <p>
                  {Math.round(Number(selectedRankingJob.rank_score ?? 0)) >= 80
                    ? 'Perfect Match'
                    : Math.round(Number(selectedRankingJob.rank_score ?? 0)) >= 60
                      ? 'Good Match'
                      : 'Moderate Match'}
                </p>
              </div>
              <div className="ranking-breakdown">
                <h4>Ranking Breakdown</h4>
                {renderRankingBreakdown(
                  selectedRankingJob.rank_explain as Record<string, unknown> | undefined
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
