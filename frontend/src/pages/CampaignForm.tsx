import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../services/api';

interface FormSectionProps {
  title: string;
  icon: string;
  defaultExpanded?: boolean;
  children: React.ReactNode;
}

const FormSection: React.FC<FormSectionProps> = ({ title, icon, defaultExpanded = true, children }) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="form-section">
      <div className="form-section-header" onClick={() => setIsExpanded(!isExpanded)} aria-expanded={isExpanded}>
        <h3>
          <i className={`fas ${icon} section-icon`}></i>
          {title}
        </h3>
        <i className={`fas fa-chevron-down toggle-icon ${isExpanded ? 'active' : ''}`}></i>
      </div>
      <div className={`form-section-content ${isExpanded ? 'active' : ''}`}>{children}</div>
    </div>
  );
};

interface CheckboxGroupProps {
  name: string;
  label: string;
  options: Array<{ value: string; label: string }>;
  selected: string[];
  onChange: (selected: string[]) => void;
}

const CheckboxGroup: React.FC<CheckboxGroupProps> = ({ name, label, options, selected, onChange }) => {
  const handleChange = (value: string, checked: boolean) => {
    if (checked) {
      onChange([...selected, value]);
    } else {
      onChange(selected.filter((v) => v !== value));
    }
  };

  return (
    <div className="form-group">
      <label className="checkbox-group-label">{label}</label>
      <div className="checkbox-group">
        {options.map((option) => (
          <label key={option.value} className="checkbox-option">
            <input
              type="checkbox"
              name={name}
              value={option.value}
              checked={selected.includes(option.value)}
              onChange={(e) => handleChange(option.value, e.target.checked)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </div>
  );
};

export const CampaignForm: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const campaignId = id ? parseInt(id, 10) : 0;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState<string | null>(null);

  const { data: campaignData } = useQuery({
    queryKey: ['campaign', campaignId],
    queryFn: () => apiClient.getCampaign(campaignId),
    enabled: isEdit,
  });

  const campaign = campaignData
    ? ((campaignData as { campaign: unknown }).campaign as Record<string, unknown>)
    : null;

  // Parse arrays from campaign data (they come as comma-separated strings or arrays)
  const parseArray = (value: unknown): string[] => {
    if (Array.isArray(value)) return value;
    if (typeof value === 'string' && value) return value.split(',').map((v) => v.trim());
    return [];
  };

  const [formData, setFormData] = useState({
    campaign_name: (campaign?.campaign_name as string) || '',
    query: (campaign?.query as string) || '',
    location: (campaign?.location as string) || '',
    country: (campaign?.country as string) || '',
    date_window: (campaign?.date_window as string) || 'week',
    email: (campaign?.email as string) || '',
    skills: (campaign?.skills as string) || '',
    min_salary: (campaign?.min_salary as number) || undefined,
    max_salary: (campaign?.max_salary as number) || undefined,
    currency: (campaign?.currency as string) || '',
    remote_preference: parseArray(campaign?.remote_preference),
    seniority: parseArray(campaign?.seniority),
    company_size_preference: parseArray(campaign?.company_size_preference),
    employment_type_preference: parseArray(campaign?.employment_type_preference),
    is_active: (campaign?.is_active as boolean) ?? true,
    ranking_weights: (campaign?.ranking_weights as Record<string, number>) || {},
  });

  // Update form data when campaign loads
  useEffect(() => {
    if (campaign) {
      setFormData({
        campaign_name: (campaign.campaign_name as string) || '',
        query: (campaign.query as string) || '',
        location: (campaign.location as string) || '',
        country: (campaign.country as string) || '',
        date_window: (campaign.date_window as string) || 'week',
        email: (campaign.email as string) || '',
        skills: (campaign.skills as string) || '',
        min_salary: (campaign.min_salary as number) || undefined,
        max_salary: (campaign.max_salary as number) || undefined,
        currency: (campaign.currency as string) || '',
        remote_preference: parseArray(campaign.remote_preference),
        seniority: parseArray(campaign.seniority),
        company_size_preference: parseArray(campaign.company_size_preference),
        employment_type_preference: parseArray(campaign.employment_type_preference),
        is_active: (campaign.is_active as boolean) ?? true,
        ranking_weights: (campaign.ranking_weights as Record<string, number>) || {},
      });
    }
  }, [campaign]);

  const [rankingWeightTotal, setRankingWeightTotal] = useState(0);
  const [rankingWeightWarning, setRankingWeightWarning] = useState(false);

  useEffect(() => {
    const total = Object.values(formData.ranking_weights).reduce((sum, val) => sum + (val || 0), 0);
    setRankingWeightTotal(total);
    const hasAnyValue = Object.values(formData.ranking_weights).some((val) => val && val > 0);
    setRankingWeightWarning(hasAnyValue && Math.abs(total - 100) > 0.1);
  }, [formData.ranking_weights]);

  const clearFieldError = (field: string) => {
    setFormErrors((prev) => {
      if (!prev[field]) return prev;
      const next = { ...prev };
      delete next[field];
      return next;
    });
  };

  const getErrorMessage = (error: unknown): string => {
    if (error instanceof Error) return error.message;
    if (typeof error === 'string') return error;
    if (error && typeof error === 'object' && 'response' in error) {
      const response = (error as { response?: { data?: { error?: string; message?: string } } }).response;
      return response?.data?.error || response?.data?.message || 'Request failed. Please try again.';
    }
    return 'Request failed. Please try again.';
  };

  const handleSuccess = (message: string, destination: string) => {
    setSubmitSuccess(message);
    window.setTimeout(() => {
      navigate(destination);
    }, 800);
  };

  const createMutation = useMutation({
    mutationFn: (data: unknown) => apiClient.createCampaign(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      handleSuccess('Campaign created successfully. Redirecting...', '/campaigns');
    },
    onError: (error: unknown) => {
      setSubmitError(getErrorMessage(error));
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: unknown) => apiClient.updateCampaign(campaignId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      queryClient.invalidateQueries({ queryKey: ['campaign', campaignId] });
      handleSuccess('Campaign updated successfully. Redirecting...', `/campaigns/${campaignId}`);
    },
    onError: (error: unknown) => {
      setSubmitError(getErrorMessage(error));
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(null);
    createMutation.reset();
    updateMutation.reset();

    const nextErrors: Record<string, string> = {};
    if (!formData.campaign_name.trim()) {
      nextErrors.campaign_name = 'Campaign name is required.';
    }
    if (!formData.query.trim()) {
      nextErrors.query = 'Search query is required.';
    }
    if (!formData.country.trim()) {
      nextErrors.country = 'Country code is required.';
    } else if (!/^[a-z]{2}$/.test(formData.country.trim())) {
      nextErrors.country = 'Use a two-letter lowercase country code (e.g., ca, us).';
    }

    if (Object.keys(nextErrors).length > 0) {
      setFormErrors(nextErrors);
      return;
    }

    // Validate ranking weights if any are provided
    if (rankingWeightWarning) {
      alert(`Ranking weights must sum to 100%. Current total: ${rankingWeightTotal.toFixed(1)}%`);
      return;
    }

    // Prepare data for API
    const submitData: Record<string, unknown> = {
      campaign_name: formData.campaign_name,
      query: formData.query,
      country: formData.country.toLowerCase(),
      location: formData.location || null,
      date_window: formData.date_window,
      email: formData.email || null,
      skills: formData.skills || null,
      min_salary: formData.min_salary || null,
      max_salary: formData.max_salary || null,
      currency: formData.currency || null,
      remote_preference: formData.remote_preference.length > 0 ? formData.remote_preference : null,
      seniority: formData.seniority.length > 0 ? formData.seniority : null,
      company_size_preference:
        formData.company_size_preference.length > 0 ? formData.company_size_preference : null,
      employment_type_preference:
        formData.employment_type_preference.length > 0 ? formData.employment_type_preference : null,
      is_active: formData.is_active,
    };

    // Add ranking weights if any are provided
    const hasRankingWeights = Object.values(formData.ranking_weights).some((val) => val && val > 0);
    if (hasRankingWeights) {
      submitData.ranking_weights = formData.ranking_weights;
    }

    if (isEdit) {
      updateMutation.mutate(submitData);
    } else {
      createMutation.mutate(submitData);
    }
  };

  const updateRankingWeight = (key: string, value: number) => {
    setFormData({
      ...formData,
      ranking_weights: {
        ...formData.ranking_weights,
        [key]: value || 0,
      },
    });
  };

  return (
    <div>
      <div className="page-header">
        <h1>{isEdit ? 'Edit Campaign' : 'Create Campaign'}</h1>
      </div>

      <div className="card">
        <form onSubmit={handleSubmit} noValidate>
          {(submitError || createMutation.isError || updateMutation.isError) && (
            <div className="form-error" role="alert">
              {submitError ||
                (createMutation.isError
                  ? getErrorMessage(createMutation.error)
                  : null) ||
                (updateMutation.isError
                  ? getErrorMessage(updateMutation.error)
                  : null)}
            </div>
          )}
          {submitSuccess && (
            <div className="form-success" role="status">
              {submitSuccess}
            </div>
          )}
          <FormSection title="Basic Information" icon="fa-info-circle" defaultExpanded={true}>
            <div className={`form-group ${formErrors.campaign_name ? 'error' : ''}`}>
              <label htmlFor="campaign_name" className="required">
                Campaign Name
              </label>
              <input
                type="text"
                id="campaign_name"
                value={formData.campaign_name}
                onChange={(e) => {
                  setFormData({ ...formData, campaign_name: e.target.value });
                  clearFieldError('campaign_name');
                }}
                aria-invalid={Boolean(formErrors.campaign_name)}
                aria-describedby={formErrors.campaign_name ? 'campaign_name_error' : undefined}
                required
              />
              <div className="form-error-message" id="campaign_name_error">
                {formErrors.campaign_name}
              </div>
            </div>

            <div className={`form-group ${formErrors.query ? 'error' : ''}`}>
              <label htmlFor="query" className="required">
                Search Query
              </label>
              <input
                type="text"
                id="query"
                value={formData.query}
                onChange={(e) => {
                  setFormData({ ...formData, query: e.target.value });
                  clearFieldError('query');
                }}
                aria-invalid={Boolean(formErrors.query)}
                aria-describedby={formErrors.query ? 'query_error' : undefined}
                placeholder="e.g., BI Developer, Data Engineer"
                required
              />
              <div className="form-error-message" id="query_error">
                {formErrors.query}
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="location">Location</label>
              <input
                type="text"
                id="location"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                placeholder="e.g., Toronto, Vancouver"
              />
            </div>

            <div className={`form-group ${formErrors.country ? 'error' : ''}`}>
              <label htmlFor="country" className="required">
                Country Code
              </label>
              <input
                type="text"
                id="country"
                value={formData.country}
                onChange={(e) => {
                  setFormData({ ...formData, country: e.target.value.toLowerCase() });
                  clearFieldError('country');
                }}
                aria-invalid={Boolean(formErrors.country)}
                aria-describedby={formErrors.country ? 'country_error' : undefined}
                placeholder="e.g., ca, us, gb"
                pattern="[a-z]{2}"
                style={{ textTransform: 'lowercase' }}
                required
              />
              <div className="form-error-message" id="country_error">
                {formErrors.country}
              </div>
              <small className="form-hint">Two-letter country code (lowercase), e.g., ca, us, gb</small>
            </div>

            <div className="form-group">
              <label htmlFor="date_window">Date Window</label>
              <select
                id="date_window"
                value={formData.date_window}
                onChange={(e) => setFormData({ ...formData, date_window: e.target.value })}
              >
                <option value="anytime">Anytime</option>
                <option value="today">Today</option>
                <option value="3days">Last 3 Days</option>
                <option value="week">Last Week</option>
                <option value="month">Last Month</option>
              </select>
            </div>
          </FormSection>

          <FormSection title="Contact & Skills" icon="fa-envelope" defaultExpanded={true}>
            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <input
                type="email"
                id="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="your.email@example.com"
              />
              <small className="form-hint">Required for email notifications</small>
            </div>

            <div className="form-group">
              <label htmlFor="skills">Skills</label>
              <input
                type="text"
                id="skills"
                value={formData.skills}
                onChange={(e) => setFormData({ ...formData, skills: e.target.value })}
                placeholder="e.g., Python, DBT, Looker, SQL"
              />
            </div>
          </FormSection>

          <FormSection title="Salary Preferences" icon="fa-dollar-sign" defaultExpanded={true}>
            <div className="grid-3">
              <div className="form-group">
                <label htmlFor="min_salary">Min Salary</label>
                <input
                  type="number"
                  id="min_salary"
                  value={formData.min_salary || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      min_salary: e.target.value ? parseFloat(e.target.value) : undefined,
                    })
                  }
                  placeholder="e.g., 80000"
                  step="1000"
                />
              </div>

              <div className="form-group">
                <label htmlFor="max_salary">Max Salary</label>
                <input
                  type="number"
                  id="max_salary"
                  value={formData.max_salary || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      max_salary: e.target.value ? parseFloat(e.target.value) : undefined,
                    })
                  }
                  placeholder="e.g., 120000"
                  step="1000"
                />
              </div>

              <div className="form-group">
                <label htmlFor="currency">Currency</label>
                <select
                  id="currency"
                  value={formData.currency}
                  onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                >
                  <option value="">USD (Default)</option>
                  <option value="USD">USD</option>
                  <option value="CAD">CAD</option>
                  <option value="EUR">EUR</option>
                  <option value="GBP">GBP</option>
                  <option value="AUD">AUD</option>
                </select>
                <small style={{ color: '#6c757d' }}>Currency for salary preferences</small>
              </div>
            </div>
          </FormSection>

          <FormSection title="Job Preferences" icon="fa-briefcase" defaultExpanded={true}>
            <CheckboxGroup
              name="remote_preference"
              label="Remote Preference"
              options={[
                { value: 'remote', label: 'Remote Only' },
                { value: 'hybrid', label: 'Hybrid' },
                { value: 'onsite', label: 'On-site Only' },
              ]}
              selected={formData.remote_preference}
              onChange={(selected) => setFormData({ ...formData, remote_preference: selected })}
            />

            <CheckboxGroup
              name="seniority"
              label="Seniority Level"
              options={[
                { value: 'entry', label: 'Entry Level' },
                { value: 'mid', label: 'Mid Level' },
                { value: 'senior', label: 'Senior' },
                { value: 'lead', label: 'Lead' },
              ]}
              selected={formData.seniority}
              onChange={(selected) => setFormData({ ...formData, seniority: selected })}
            />

            <CheckboxGroup
              name="company_size_preference"
              label="Company Size"
              options={[
                { value: '1-50', label: '1-50 employees' },
                { value: '51-200', label: '51-200 employees' },
                { value: '201-500', label: '201-500 employees' },
                { value: '501-1000', label: '501-1000 employees' },
                { value: '1001-5000', label: '1001-5000 employees' },
                { value: '5001-10000', label: '5001-10000 employees' },
                { value: '10000+', label: '10000+ employees' },
              ]}
              selected={formData.company_size_preference}
              onChange={(selected) => setFormData({ ...formData, company_size_preference: selected })}
            />

            <CheckboxGroup
              name="employment_type_preference"
              label="Employment Type"
              options={[
                { value: 'FULLTIME', label: 'Full-time' },
                { value: 'PARTTIME', label: 'Part-time' },
                { value: 'CONTRACTOR', label: 'Contractor' },
                { value: 'TEMPORARY', label: 'Temporary' },
                { value: 'INTERN', label: 'Intern' },
              ]}
              selected={formData.employment_type_preference}
              onChange={(selected) => setFormData({ ...formData, employment_type_preference: selected })}
            />
          </FormSection>

          <FormSection title="Campaign Settings" icon="fa-cog" defaultExpanded={true}>
            <div className="form-group">
              <label>
                <input
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                />
                Active (campaign will be used for job extraction)
              </label>
            </div>
          </FormSection>

          <FormSection title="Ranking Weights (Optional)" icon="fa-chart-line" defaultExpanded={false}>
            <p style={{ color: '#6c757d', marginBottom: '1rem' }}>
              Customize how jobs are ranked for this campaign. Weights are percentages and should sum to 100%. If not
              set, default weights from configuration will be used.
            </p>
            <div className="grid-2">
              <div className="form-group">
                <label htmlFor="ranking_weight_location_match">Location Match (%)</label>
                <input
                  type="number"
                  id="ranking_weight_location_match"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.ranking_weights.location_match || ''}
                  onChange={(e) =>
                    updateRankingWeight('location_match', e.target.value ? parseFloat(e.target.value) : 0)
                  }
                  className="ranking-weight-input"
                />
              </div>
              <div className="form-group">
                <label htmlFor="ranking_weight_salary_match">Salary Match (%)</label>
                <input
                  type="number"
                  id="ranking_weight_salary_match"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.ranking_weights.salary_match || ''}
                  onChange={(e) =>
                    updateRankingWeight('salary_match', e.target.value ? parseFloat(e.target.value) : 0)
                  }
                  className="ranking-weight-input"
                />
              </div>
              <div className="form-group">
                <label htmlFor="ranking_weight_company_size_match">Company Size Match (%)</label>
                <input
                  type="number"
                  id="ranking_weight_company_size_match"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.ranking_weights.company_size_match || ''}
                  onChange={(e) =>
                    updateRankingWeight('company_size_match', e.target.value ? parseFloat(e.target.value) : 0)
                  }
                  className="ranking-weight-input"
                />
              </div>
              <div className="form-group">
                <label htmlFor="ranking_weight_skills_match">Skills Match (%)</label>
                <input
                  type="number"
                  id="ranking_weight_skills_match"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.ranking_weights.skills_match || ''}
                  onChange={(e) =>
                    updateRankingWeight('skills_match', e.target.value ? parseFloat(e.target.value) : 0)
                  }
                  className="ranking-weight-input"
                />
              </div>
              <div className="form-group">
                <label htmlFor="ranking_weight_keyword_match">Keyword Match (%)</label>
                <input
                  type="number"
                  id="ranking_weight_keyword_match"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.ranking_weights.keyword_match || ''}
                  onChange={(e) =>
                    updateRankingWeight('keyword_match', e.target.value ? parseFloat(e.target.value) : 0)
                  }
                  className="ranking-weight-input"
                />
              </div>
              <div className="form-group">
                <label htmlFor="ranking_weight_employment_type_match">Employment Type Match (%)</label>
                <input
                  type="number"
                  id="ranking_weight_employment_type_match"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.ranking_weights.employment_type_match || ''}
                  onChange={(e) =>
                    updateRankingWeight('employment_type_match', e.target.value ? parseFloat(e.target.value) : 0)
                  }
                  className="ranking-weight-input"
                />
              </div>
              <div className="form-group">
                <label htmlFor="ranking_weight_seniority_match">Seniority Match (%)</label>
                <input
                  type="number"
                  id="ranking_weight_seniority_match"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.ranking_weights.seniority_match || ''}
                  onChange={(e) =>
                    updateRankingWeight('seniority_match', e.target.value ? parseFloat(e.target.value) : 0)
                  }
                  className="ranking-weight-input"
                />
              </div>
              <div className="form-group">
                <label htmlFor="ranking_weight_remote_type_match">Remote Type Match (%)</label>
                <input
                  type="number"
                  id="ranking_weight_remote_type_match"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.ranking_weights.remote_type_match || ''}
                  onChange={(e) =>
                    updateRankingWeight('remote_type_match', e.target.value ? parseFloat(e.target.value) : 0)
                  }
                  className="ranking-weight-input"
                />
              </div>
              <div className="form-group">
                <label htmlFor="ranking_weight_recency">Recency (%)</label>
                <input
                  type="number"
                  id="ranking_weight_recency"
                  min="0"
                  max="100"
                  step="0.1"
                  value={formData.ranking_weights.recency || ''}
                  onChange={(e) =>
                    updateRankingWeight('recency', e.target.value ? parseFloat(e.target.value) : 0)
                  }
                  className="ranking-weight-input"
                />
              </div>
            </div>
            <div className="weight-total">
              <strong>
                Total: <span className={rankingWeightWarning ? 'weight-invalid' : 'weight-valid'}>{rankingWeightTotal.toFixed(1)}</span>%
              </strong>
              {rankingWeightWarning && (
                <span style={{ color: '#dc3545', marginLeft: '1rem' }}>⚠ Weights should sum to 100%</span>
              )}
            </div>
          </FormSection>

          <div className="form-actions">
            <button
              type="submit"
              className="btn btn-primary"
              id="submit-btn"
              disabled={createMutation.isPending || updateMutation.isPending || rankingWeightWarning}
            >
              {createMutation.isPending || updateMutation.isPending
                ? 'Saving...'
                : `${isEdit ? 'Update' : 'Create'} Campaign`}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate(isEdit ? `/campaigns/${campaignId}` : '/campaigns')}
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
