-- What the CI job sends with a review, apart from its token, which is never stored.
ALTER TABLE reviews ADD COLUMN default_branch TEXT NOT NULL DEFAULT 'main';
ALTER TABLE reviews ADD COLUMN title TEXT NOT NULL DEFAULT '';
ALTER TABLE reviews ADD COLUMN body TEXT NOT NULL DEFAULT '';
ALTER TABLE reviews ADD COLUMN event TEXT NOT NULL DEFAULT 'manual'
    CHECK (event IN ('opened', 'synchronize', 'reopened', 'manual'));
-- Whether the request brought a token (never the token itself): after a restart such a
-- review cannot run, because its token lived only in the old process's memory.
ALTER TABLE reviews ADD COLUMN has_token INTEGER NOT NULL DEFAULT 0 CHECK (has_token IN (0, 1));
-- A newer push of the same PR supersedes the review (decision D-010). A queued review
-- is then stored as failed and never runs; a running one is stopped by the pipeline
-- between steps. The API reports both as superseded, with the newer review's id.
ALTER TABLE reviews ADD COLUMN superseded_by INTEGER REFERENCES reviews (id);
-- A CI job run again for the same commit finds its review instead of starting another.
CREATE INDEX reviews_by_commit ON reviews (repo, pr, head_sha);
