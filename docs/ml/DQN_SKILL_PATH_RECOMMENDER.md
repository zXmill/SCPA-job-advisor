# DQN Skill Path Recommender

## Purpose
The DQN service is framed as a skill and career milestone policy. It may still
emit a compatibility rerank signal for the hybrid job pipeline, but its action
space is not job postings.

## MDP Contract
- State: user profile, current skills, missing skills for the target role, and market demand per missing skill.
- Action: the next skill, course, certificate, or career milestone.
- Reward: `skill_gap_reduction + job_match_lift`.

## Serving Contract
- `POST /learning-path` returns `policy_objective: skill_path`, the MDP state,
  the action space description, and reward components for each step.
- `POST /rank` keeps the existing job compatibility response shape, but each
  DQN action now carries `policy_objective: skill_path`, an `action_type`, and
  skill-gap reward components.
- Pipeline stage 4 forwards target-role context and preserves the skill-path
  action metadata as `dqn_*` fields for downstream aggregation and explanation.

## Training Contract
The lightweight DQN training smoke uses synthetic skill-path states:
mastered-skill flags, missing-skill flags, market-demand features, and target
role one-hot features. Its metrics include the MDP contract and compare the
learned policy reward against a random-action reward baseline.

## Compatibility Notes
The hybrid aggregator still consumes `dqn_score` as a numeric signal. That
score should be interpreted as a skill-path job-match lift estimate, not a
direct recommendation that the DQN selected the job posting as an action.
