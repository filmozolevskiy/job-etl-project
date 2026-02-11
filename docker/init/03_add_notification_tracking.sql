-- Migration: Add last_notification_sent_at to marts.job_campaigns
-- Issue: JOB-47

ALTER TABLE marts.job_campaigns ADD COLUMN IF NOT EXISTS last_notification_sent_at timestamp;

COMMENT ON COLUMN marts.job_campaigns.last_notification_sent_at IS 'Timestamp of the last time a notification was successfully sent for this campaign.';
