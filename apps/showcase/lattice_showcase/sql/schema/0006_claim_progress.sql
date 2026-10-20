-- When each claim was assigned to a surveyor, inspected and settled, for the timelines
-- (ADR 0014). Claims before this migration have none; `lattice reset` reseeds them.

ALTER TABLE showcase.claim
  ADD COLUMN assigned_at  timestamp,
  ADD COLUMN inspected_at timestamp,
  ADD COLUMN settled_at   timestamp;
