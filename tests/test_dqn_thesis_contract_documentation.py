from pathlib import Path


DOC_PATH = Path("docs/architecture/DQN_SESSION_RERANKER_CONTRACT.md")


def test_dqn_thesis_contract_document_exists() -> None:
    assert DOC_PATH.exists(), "DQN thesis contract document must exist"


def test_dqn_thesis_contract_declares_session_rerank_as_canonical_objective() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "session_rerank" in text
    assert "dqn_session_score" in text
    assert "session_events" in text


def test_dqn_thesis_contract_rejects_learning_path_as_active_dqn_behavior() -> None:
    text = DOC_PATH.read_text(encoding="utf-8").lower()

    assert "not a learning-path generator" in text
    assert "not active dqn behavior" in text
    assert "/api/learning-path" in text
    assert "410 gone" in text


def test_dqn_thesis_contract_assigns_final_score_to_stage_5() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "DQN must not expose or own the final recommendation score" in text
    assert "final_score = alpha*sbert_score + beta*ncf_score + gamma*dqn_session_score" in text
    assert "Stage 5" in text


def test_dqn_thesis_contract_documents_cold_start_gamma_zero() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "gamma = 0.00" in text
    assert "cold-start" in text.lower()