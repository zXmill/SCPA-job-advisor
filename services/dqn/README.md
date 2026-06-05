# SCPA Online DQN Reranker

This service is an online DQN ranker. It uses a PyTorch `QNetwork`, replay
buffer, epsilon-greedy action selection, target network soft updates, and
checkpointed policy weights while the system is running.

## How It Learns

- Scraped jobs arrive through `POST /jobs/upsert`.
- `POST /rank` scores candidates using SBERT score, NCF score, job embedding,
  interaction context, and the learned QNetwork.
- `POST /reward` / `POST /feedback` applies a temporal-difference update.
- Replay summaries and metadata are persisted to `weights/online_dqn.json`.
- Policy and target `state_dict` weights are persisted to `weights/online_dqn.pt`.

## State And Features

The feature vector contains:

- projected job embedding
- SBERT score
- NCF score
- interaction history count
- user interaction count
- text length
- bias term

This lets the reranker learn from observed behavior instead of hard-coded major
rules.

## DQN Components

- `QNetwork`: feed-forward policy network over the feature vector.
- `ReplayBuffer`: bounded transition store with state, action, reward,
  next_state, done, TD error, and policy provenance.
- `target_net`: soft-updated target network used for bootstrapped TD targets.
- `epsilon`: decayed exploration rate for action selection.

## Rewards

- `click`: `+1.0`
- `apply`: `+1.0`
- `view`, `view_10s`, `long_view`: `+0.5`
- `skip`, `immediate_skip`, `skip_immediately`: `-0.5`
- confirmed mismatch: `-1.0`

If a learned intent classifier or explicit feedback marks a candidate as a
complete mismatch, the reward can be multiplied by `0.2`.

## Endpoints

- `GET /health`
- `POST /jobs/upsert`
- `POST /rank`
- `POST /rerank`
- `POST /reward`
- `POST /feedback`
- `POST /train`
- `GET /model/status`
