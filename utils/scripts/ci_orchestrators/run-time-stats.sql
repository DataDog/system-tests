WITH samples AS (
  SELECT
    REPLACE(REPLACE("@ci.step.name", 'Run ', ''), ' scenario', '') AS scenario,
    SPLIT_PART(SPLIT_PART("@ci.job.name", '(', 2), ',', 1) AS library,
    REGEXP_REPLACE(SPLIT_PART("@ci.job.name", ' / ', 3), ' [0-9]+$', '') AS weblog,
    CAST("@duration" AS DECIMAL) / 1000000000 AS duration_seconds
  FROM dd.ci_pipelines(
    columns => ARRAY['@ci.step.name', '@ci.job.name', '@duration'],
    event_type => 'step',
    filter => '@git.repository.id_v2:"github.com/datadog/system-tests" @git.is_default_branch:true @ci.status:success @ci.pipeline.name:Nightly @ci.step.name:Run\ *\ scenario'
  ) AS (
    "@ci.step.name" VARCHAR,
    "@ci.job.name" VARCHAR,
    "@duration" BIGINT
  )
  WHERE REGEXP_LIKE("@ci.job.name", '^nightly .* / End-to-end #[0-9]+ / .+ [0-9]+$')
),
ranked AS (
  SELECT
    scenario,
    library,
    weblog,
    duration_seconds,
    ROW_NUMBER() OVER (
      PARTITION BY scenario, library, weblog
      ORDER BY duration_seconds
    ) AS sample_rank,
    COUNT(*) OVER (
      PARTITION BY scenario, library, weblog
    ) AS sample_count,
    MIN(duration_seconds) OVER (
      PARTITION BY scenario, library, weblog
    ) AS minimum,
    MAX(duration_seconds) OVER (
      PARTITION BY scenario, library, weblog
    ) AS maximum
  FROM samples
),
percentile_50 AS (
  SELECT * FROM ranked WHERE sample_rank = CEIL(sample_count * 0.50)
),
percentile_75 AS (
  SELECT * FROM ranked WHERE sample_rank = CEIL(sample_count * 0.75)
),
percentile_95 AS (
  SELECT * FROM ranked WHERE sample_rank = CEIL(sample_count * 0.95)
)
SELECT
  percentile_75.scenario,
  percentile_75.library,
  percentile_75.weblog,
  percentile_75.sample_count,
  percentile_75.minimum,
  percentile_50.duration_seconds AS median,
  percentile_75.duration_seconds AS p75,
  percentile_95.duration_seconds AS p95,
  percentile_75.maximum
FROM percentile_75
JOIN percentile_50 ON
  percentile_50.scenario = percentile_75.scenario AND
  percentile_50.library = percentile_75.library AND
  percentile_50.weblog = percentile_75.weblog
JOIN percentile_95 ON
  percentile_95.scenario = percentile_75.scenario AND
  percentile_95.library = percentile_75.library AND
  percentile_95.weblog = percentile_75.weblog
ORDER BY percentile_75.scenario, percentile_75.library, percentile_75.weblog
LIMIT 10000
